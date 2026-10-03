"""Which members get which Telegram message, and when.

Two kinds of triggers:
- business events, called from the services right before they commit (an event or book is
  published, attendance opens, a test closes);
- time-based checks, run by the scheduler every minute or so (``app.workers.jobs``).

Every message has a dedup key, so running a check again never sends a message twice.
Texts come from the admin-editable notification templates.
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Book,
    BookQuote,
    BookRead,
    Event,
    EventRegistration,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttemptStatus,
    BookStatus,
    EventStatus,
    NotificationType,
    QuoteStatus,
    ReadingStatus,
    RegistrationStatus,
    TestStatus,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.members import normalize_group
from app.services.notifications import app_button, enqueue_for_members, enqueue_notification, render
from app.services.settings import get_setting
from app.utils.timezone import format_human, format_human_date, local_tz

# No reading reminders or quotes at night (club time zone).
DAYTIME = (time(8, 0), time(21, 30))


def _members(*conditions: Any) -> Select[tuple[Any]]:
    """Active members matching the extra conditions (a SELECT of user ids)."""
    return select(User.id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), *conditions)


def _registered_for(event_id: Any) -> Select[tuple[Any]]:
    registered = select(EventRegistration.user_id).where(
        EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED
    )
    return _members(User.id.in_(registered))


def _daytime(now: datetime) -> bool:
    local = now.astimezone(local_tz()).time()
    return DAYTIME[0] <= local <= DAYTIME[1]


# ---------------------------------------------------------------------------- business events


async def event_published(session: AsyncSession, event: Event) -> int:
    if event.status != EventStatus.PUBLISHED or event.starts_at <= datetime.now(UTC):
        return 0
    text = await render(
        session,
        NotificationType.EVENT_CREATED,
        event_title=event.title,
        starts_at=format_human(event.starts_at),
        location=event.location or "—",
    )
    if text is None:
        return 0
    return await enqueue_for_members(
        session,
        type_=NotificationType.EVENT_CREATED,
        text=text,
        dedup_prefix=f"event_created:{event.id}",
        payload=app_button(f"events/{event.id}"),
    )


async def attendance_opened(session: AsyncSession, event: Event) -> int:
    text = await render(session, NotificationType.ATTENDANCE_OPEN, event_title=event.title)
    if text is None:
        return 0
    return await enqueue_for_members(
        session,
        type_=NotificationType.ATTENDANCE_OPEN,
        text=text,
        dedup_prefix=f"attendance_open:{event.id}",
        members=_registered_for(event.id),
        payload=app_button(f"events/{event.id}", "✅ Davomatni belgilash"),
        priority=2,
    )


async def book_published(session: AsyncSession, book: Book) -> int:
    if book.status != BookStatus.ACTIVE or book.deleted_at is not None:
        return 0
    text = await render(
        session,
        NotificationType.NEW_BOOK,
        book_title=book.title,
        book_author=book.author,
        deadline=format_human_date(book.deadline) if book.deadline else "belgilanmagan",
    )
    if text is None:
        return 0
    return await enqueue_for_members(
        session,
        type_=NotificationType.NEW_BOOK,
        text=text,
        dedup_prefix=f"new_book:{book.id}",
        payload=app_button(f"books/{book.id}"),
    )


async def test_results(session: AsyncSession, test: Test, standings: list[dict[str, Any]]) -> int:
    """After a test closes: every participant gets their best score (and place, if any)."""
    places = {row["user_id"]: row["place"] for row in standings}
    best: dict[Any, int] = {}
    for attempt in await session.scalars(
        select(TestAttempt).where(
            TestAttempt.test_id == test.id,
            TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
        )
    ):
        best[attempt.user_id] = max(best.get(attempt.user_id, 0), attempt.score or 0)
    bonuses: list[int] = await get_setting(session, "score.test_rank_bonus")
    queued = 0
    for user_id, score in best.items():
        text = await render(
            session, NotificationType.TEST_RESULT, test_title=test.title, score=score, max_score=test.max_score
        )
        if text is None:
            return 0
        place = places.get(user_id)
        if place is not None and place <= len(bonuses) and bonuses[place - 1] > 0:
            text += f"\n🏅 Siz {place}-o'rinni egalladingiz: +{bonuses[place - 1]} bonus ball!"
        text += "\n\nTo'g'ri javoblarni ilovada ko'rishingiz mumkin."
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.TEST_RESULT,
            text=text,
            dedup_key=f"test_result:{test.id}:{user_id}",
            payload=app_button(f"tests/{test.id}", "📖 Javoblarni ko'rish"),
            priority=3,
        )
        queued += 1
    return queued


# ---------------------------------------------------------------------------- time-based checks


def reminder_window(minutes: int) -> timedelta:
    """How long after "M minutes before" a reminder is still worth sending.

    Never shorter than the scheduler interval (plus a margin), so a check always falls inside it.
    """
    window = timedelta(minutes=min(max(minutes // 2, 10), 180))
    return max(window, timedelta(seconds=get_settings().worker_interval_seconds + 120))


async def event_reminders(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    offsets: list[int] = await get_setting(session, "notifications.event_reminder_minutes")
    if not offsets:
        return 0
    horizon = now + timedelta(minutes=max(offsets))
    events = list(
        await session.scalars(
            select(Event).where(
                Event.deleted_at.is_(None),
                Event.status == EventStatus.PUBLISHED,
                Event.starts_at > now,
                Event.starts_at <= horizon,
            )
        )
    )
    queued = 0
    for event in events:
        for minutes in offsets:
            due = event.starts_at - timedelta(minutes=minutes)
            if not (due <= now < due + reminder_window(minutes)):
                continue
            text = await render(
                session,
                NotificationType.EVENT_REMINDER,
                event_title=event.title,
                starts_at=format_human(event.starts_at),
                location=event.location or "—",
            )
            if text is None:
                return queued
            queued += await enqueue_for_members(
                session,
                type_=NotificationType.EVENT_REMINDER,
                text=text,
                dedup_prefix=f"event_reminder:{event.id}:{minutes}",
                members=_registered_for(event.id),
                payload=app_button(f"events/{event.id}"),
            )
    return queued


async def test_started(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    tests = list(
        await session.scalars(
            select(Test).where(
                Test.deleted_at.is_(None),
                Test.status == TestStatus.PUBLISHED,
                Test.starts_at <= now,
                Test.ends_at > now,
            )
        )
    )
    queued = 0
    for test in tests:
        text = await render(
            session,
            NotificationType.TEST_STARTED,
            test_title=test.title,
            ends_at=format_human(test.ends_at),
            duration=test.duration_minutes,
        )
        if text is None:
            return queued
        queued += await enqueue_for_members(
            session,
            type_=NotificationType.TEST_STARTED,
            text=text,
            dedup_prefix=f"test_started:{test.id}",
            payload=app_button(f"tests/{test.id}", "📝 Testni ochish"),
        )
    return queued


async def test_ending(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    minutes: int = await get_setting(session, "notifications.test_ending_minutes")
    if minutes <= 0:
        return 0
    tests = list(
        await session.scalars(
            select(Test).where(
                Test.deleted_at.is_(None),
                Test.status == TestStatus.PUBLISHED,
                Test.starts_at <= now,
                Test.ends_at > now,
                Test.ends_at <= now + timedelta(minutes=minutes),
            )
        )
    )
    queued = 0
    for test in tests:
        text = await render(
            session, NotificationType.TEST_ENDING, test_title=test.title, ends_at=format_human(test.ends_at)
        )
        if text is None:
            return queued
        finished = select(TestAttempt.user_id).where(
            TestAttempt.test_id == test.id,
            TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
        )
        queued += await enqueue_for_members(
            session,
            type_=NotificationType.TEST_ENDING,
            text=text,
            dedup_prefix=f"test_ending:{test.id}",
            members=_members(User.id.not_in(finished)),
            payload=app_button(f"tests/{test.id}", "📝 Testni ochish"),
        )
    return queued


async def reading_reminders(session: AsyncSession, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    days: int = await get_setting(session, "notifications.reading_reminder_days")
    if days <= 0 or not _daytime(now):
        return 0
    today = now.astimezone(local_tz()).date()
    books = list(
        await session.scalars(
            select(Book).where(
                Book.deleted_at.is_(None),
                Book.status == BookStatus.ACTIVE,
                Book.deadline.is_not(None),
                Book.deadline >= today,
                Book.deadline <= today + timedelta(days=days),
            )
        )
    )
    queued = 0
    for book in books:
        text = await render(
            session, NotificationType.READING_REMINDER, book_title=book.title, deadline=format_human_date(book.deadline)
        )
        if text is None:
            return queued
        readers = select(BookRead.user_id).where(
            and_(BookRead.book_id == book.id, BookRead.status == ReadingStatus.READING)
        )
        queued += await enqueue_for_members(
            session,
            type_=NotificationType.READING_REMINDER,
            text=text,
            dedup_prefix=f"reading_reminder:{book.id}",
            members=_members(User.id.in_(readers)),
            payload=app_button(f"books/{book.id}"),
        )
    return queued


async def quote_of_day(session: AsyncSession, now: datetime | None = None) -> int:
    """Sends today's scheduled quote once, at or after the configured time."""
    now = now or datetime.now(UTC)
    local = now.astimezone(local_tz())
    hour, minute = (int(part) for part in str(await get_setting(session, "notifications.quote_of_day_time")).split(":"))
    if local.time() < time(hour, minute) or local.time() > DAYTIME[1]:
        return 0
    quote = await session.scalar(
        select(BookQuote)
        .where(
            BookQuote.deleted_at.is_(None),
            BookQuote.status == QuoteStatus.SCHEDULED,
            BookQuote.scheduled_date == local.date(),
        )
        .with_for_update(skip_locked=True)
    )
    if quote is None:
        return 0
    from app.services import features

    members = await features.recipients(session, "quote_of_day")
    if members is None:
        return 0  # switched off: the quote stays scheduled and is sent if it is switched on today
    author = quote.author
    if not author and quote.book_id:
        book = await session.get(Book, quote.book_id)
        author = book.author if book else None
    text = await render(session, NotificationType.QUOTE_OF_DAY, quote_text=quote.text, quote_author=author or "—")
    quote.status = QuoteStatus.SENT
    quote.sent_at = now
    if text is None:
        return 0
    return await enqueue_for_members(
        session,
        type_=NotificationType.QUOTE_OF_DAY,
        text=text,
        dedup_prefix=f"quote:{quote.id}",
        members=members,
    )


# ---------------------------------------------------------------------------- admin broadcast


async def broadcast(
    session: AsyncSession,
    *,
    actor_id: Any,
    message: str,
    faculty_id: Any | None = None,
    course: int | None = None,
    group_name: str | None = None,
    with_app_button: bool = True,
    dry_run: bool = False,
) -> int:
    """An admin's message to all active members or a part of them. Returns the recipient count."""
    conditions = []
    if faculty_id is not None:
        conditions.append(User.faculty_id == faculty_id)
    if course is not None:
        conditions.append(User.course == course)
    if group_name:
        conditions.append(User.group_name == normalize_group(group_name))
    members = _members(*conditions)
    if dry_run:
        return int(await session.scalar(select(func.count()).select_from(members.subquery())) or 0)
    text = await render(session, NotificationType.ADMIN_MESSAGE, message=message.strip())
    if text is None:  # template switched off: send the admin's words as plain text
        text = html.escape(message.strip(), quote=False)
    broadcast_id = uuid.uuid4()
    count = await enqueue_for_members(
        session,
        type_=NotificationType.ADMIN_MESSAGE,
        text=text,
        dedup_prefix=f"broadcast:{broadcast_id}",
        members=members,
        payload=app_button("") if with_app_button else None,
        priority=3,
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="NOTIFICATION_BROADCAST",
        entity_type="notification",
        entity_id=str(broadcast_id),
        after={
            "message": message.strip()[:1000],
            "recipients": count,
            "faculty_id": str(faculty_id) if faculty_id else None,
            "course": course,
            "group_name": group_name,
        },
    )
    await session.commit()
    return count
