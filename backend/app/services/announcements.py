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
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError
from app.models import (
    AttendanceRecord,
    Book,
    BookQuote,
    BookRead,
    ChannelPost,
    Event,
    EventRegistration,
    EventShift,
    Notification,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    BookStatus,
    ChannelPostStatus,
    EventStatus,
    NotificationStatus,
    NotificationType,
    QuoteStatus,
    ReadingStatus,
    RegistrationStatus,
    TestStatus,
    UserStatus,
)
from app.services import channel, event_times, literary
from app.services.audit import record_audit
from app.services.members import normalize_group
from app.services.notifications import (
    app_button,
    celebrate,
    enqueue_for_members,
    enqueue_notification,
    render,
)
from app.services.settings import get_setting
from app.utils.timezone import format_human, format_human_date, local_tz

# No reading reminders or quotes at night (club time zone).
DAYTIME = (time(8, 0), time(21, 30))


def _members(*conditions: Any) -> Select[tuple[Any]]:
    """Active members matching the extra conditions (a SELECT of user ids)."""
    return select(User.id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), *conditions)


def _registered_for(event_id: Any, shift: EventShift | None = None) -> Select[tuple[Any]]:
    """Members registered for the event (for a shift: that shift, plus those who chose none for the first)."""
    conditions = [EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED]
    if shift is not None:
        conditions.append(
            or_(
                EventRegistration.shift_id == shift.id,
                and_(EventRegistration.shift_id.is_(None), shift.position == 1),
            )
        )
    registered = select(EventRegistration.user_id).where(*conditions)
    return _members(User.id.in_(registered))


def _involved(event_id: Any) -> Select[tuple[Any]]:
    """Registered members and everyone whose attendance was recorded."""
    registered = select(EventRegistration.user_id).where(
        EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED
    )
    attended = select(AttendanceRecord.user_id).where(
        AttendanceRecord.event_id == event_id,
        AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
    )
    return _members(or_(User.id.in_(registered), User.id.in_(attended)))


async def _shifts(session: AsyncSession, event_id: Any) -> list[EventShift]:
    return list(
        await session.scalars(select(EventShift).where(EventShift.event_id == event_id).order_by(EventShift.position))
    )


def _daytime(now: datetime) -> bool:
    local = now.astimezone(local_tz()).time()
    return DAYTIME[0] <= local <= DAYTIME[1]


# ---------------------------------------------------------------------------- business events


async def event_published(session: AsyncSession, event: Event) -> int:
    if event.status != EventStatus.PUBLISHED or event.starts_at <= datetime.now(UTC):
        return 0
    await channel.event_announced(session, event)
    from app.services.events import shifts_of

    shifts = await shifts_of(session, event.id)
    text = await render(
        session,
        NotificationType.EVENT_CREATED,
        event_title=event.title,
        # Shift-aware: «...: 1-smena 10:00–11:30, 2-smena 14:00–15:30» instead of a single time.
        starts_at=event_times.when_text(event, shifts),
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


async def attendance_opened(session: AsyncSession, event: Event, shift: EventShift | None = None) -> int:
    """Registered members (of this shift) learn that they can check in now."""
    text = await render(session, NotificationType.ATTENDANCE_OPEN, event_title=event.title)
    if text is None:
        return 0
    if shift is not None:
        text = f"{text}\n🕒 {event_times.shift_text(shift)}"
    return await enqueue_for_members(
        session,
        type_=NotificationType.ATTENDANCE_OPEN,
        text=text,
        dedup_prefix=f"attendance_open:{event.id}" + (f":{shift.position}" if shift else ""),
        members=_registered_for(event.id, shift),
        payload=app_button(f"events/{event.id}", "✅ Davomatni belgilash"),
        priority=2,
    )


async def _release_keys(session: AsyncSession, event: Event) -> None:
    """The event moved: reminders already queued or sent for the old time give way to new ones."""
    suffix = "~" + event_times.stamp(datetime.now(UTC))
    for prefix in (f"event_reminder:{event.id}:", f"attendance_open:{event.id}"):
        await session.execute(
            update(Notification)
            .where(Notification.dedup_key.like(f"{prefix}%"), ~Notification.dedup_key.contains("~"))
            .values(
                dedup_key=Notification.dedup_key + suffix,
                status=func.coalesce(
                    func.nullif(Notification.status, NotificationStatus.PENDING.value),
                    NotificationStatus.SKIPPED.value,
                ),
            )
        )
    await session.execute(
        update(ChannelPost)
        .where(ChannelPost.dedup_key.like(f"event_reminder:{event.id}:%"), ~ChannelPost.dedup_key.contains("~"))
        .values(
            dedup_key=ChannelPost.dedup_key + suffix,
            status=func.coalesce(
                func.nullif(ChannelPost.status, ChannelPostStatus.PENDING.value), ChannelPostStatus.CANCELLED.value
            ),
        )
    )


async def event_changed(session: AsyncSession, event: Event, shifts: list[EventShift]) -> int:
    """New time or place of a published event: posts and reminders follow, registered members are told."""
    await _release_keys(session, event)
    await channel.event_changed(session, event, shifts)
    place = f"\n📍 {html.escape(event.location)}" if event.location else ""
    message = (
        f"🔔 <b>O'zgarish!</b> «{html.escape(event.title)}» tadbiri endi:\n"
        f"🗓 {event_times.when_text(event, shifts)}{place}\n\n"
        "Ro'yxatingiz saqlanib qoldi — eslatmani yangi vaqtga yuboramiz."
    )
    return await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_prefix=f"event_change:{event.id}:{event_times.stamp(event.starts_at)}",
        members=_registered_for(event.id),
        payload=app_button(f"events/{event.id}"),
        priority=2,
    )


async def event_cancelled(session: AsyncSession, event: Event) -> int:
    await channel.event_cancelled(session, event)
    await _release_keys(session, event)
    message = (
        f"❌ «{html.escape(event.title)}» tadbiri bekor qilindi. "
        "Noqulaylik uchun uzr — yangi uchrashuvni albatta e'lon qilamiz."
    )
    return await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_prefix=f"event_cancel:{event.id}",
        members=_registered_for(event.id),
        priority=2,
    )


async def event_finished(session: AsyncSession, event: Event) -> int:
    """The event is over: the super admins are reminded about the report; when ratings are switched
    off, the members who came get a thank-you (otherwise the rating request thanks them)."""
    from app.services import features
    from app.services.rbac import super_admins

    attended = int(
        await session.scalar(
            select(func.count())
            .select_from(AttendanceRecord)
            .where(
                AttendanceRecord.event_id == event.id,
                AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
            )
        )
        or 0
    )
    message = (
        f"🏁 <b>«{html.escape(event.title)}» tadbiri yakunlandi</b>\n\nQatnashdi: {attended} nafar a'zo.\n"
        "Hisobotini tayyorlab qo'yamizmi? Rasmlarni yuklasangiz, kanalga chiroyli post ham chiqadi 📸"
    )
    queued = await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=message,
        dedup_prefix=f"event_done:{event.id}",
        members=super_admins(),
        payload={"buttons": [{"text": "📝 Hisobot tayyorlash", "admin_route": f"reports?event={event.id}"}]},
        priority=3,
    )
    if attended and await features.recipients(session, "event_feedback") is None:
        thanks = (
            f"✅ Siz «{html.escape(event.title)}» tadbirida qatnashdingiz! Ballaringiz hisobga olindi. "
            "Keyingi uchrashuvda ko'rishguncha — mutolaa davom etsin 📚"
        )
        attendees = select(AttendanceRecord.user_id).where(
            AttendanceRecord.event_id == event.id,
            AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
        )
        queued += await enqueue_for_members(
            session,
            type_=NotificationType.SYSTEM,
            text=await render(session, NotificationType.SYSTEM, message=thanks) or thanks,
            dedup_prefix=f"event_thanks:{event.id}",
            members=_members(User.id.in_(attendees)),
            priority=6,
        )
    return queued


async def event_stopped(session: AsyncSession, event: Event) -> int:
    """The super admin stopped the event early: everyone involved is told it is over."""
    message = (
        f"⏹ «{html.escape(event.title)}» tadbiri yakunlandi. Kelganingiz uchun rahmat — keyingi uchrashuvgacha! 📚"
    )
    return await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=await render(session, NotificationType.SYSTEM, message=message) or message,
        dedup_prefix=f"event_stopped:{event.id}",
        members=_involved(event.id),
        priority=2,
    )


async def book_published(session: AsyncSession, book: Book) -> int:
    if book.status != BookStatus.ACTIVE or book.deleted_at is not None:
        return 0
    await channel.book_announced(session, book)
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
    """After a test closes: every participant gets their best score (and place, if any).

    ``standings`` may carry ``official_place`` (a test of an event: only members who attended take
    prize places); a strong result without attendance gets a kind note instead of a place."""
    official = [
        {**row, "place": row.get("official_place", row["place"])}
        for row in standings
        if row.get("official_place", row["place"]) is not None
    ]
    await channel.test_winners(session, test, official)
    places = {row["user_id"]: row["place"] for row in official}
    missed = {row["user_id"] for row in standings if row.get("attended") is False and row["place"] <= 3}
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
        elif user_id in missed:
            text += (
                "\n👏 Natijangiz sovrinli o'rinlar darajasida! Ammo tadbirda davomat qilinmagani uchun o'rinlar "
                "hisobiga kirmadi — keyingi safar tadbirga keling, sovg'a sizni kutadi."
            )
        text += "\n\nTo'g'ri javoblarni ilovada ko'rishingiz mumkin."
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.TEST_RESULT,
            text=text,
            dedup_key=f"test_result:{test.id}:{user_id}",
            payload=(celebrate if place is not None and place <= 3 else dict)(
                app_button(f"tests/{test.id}", "📖 Javoblarni ko'rish")
            ),
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
                Event.ends_at > now,  # a later shift may still be ahead
                Event.starts_at <= horizon,
            )
        )
    )
    queued = 0
    for event in events:
        shifts = await _shifts(session, event.id)
        sessions: list[EventShift | None] = list(shifts) or [None]
        for shift in sessions:
            starts_at = shift.starts_at if shift else event.starts_at
            for minutes in offsets:
                due = starts_at - timedelta(minutes=minutes)
                if not (due <= now < due + reminder_window(minutes)) or starts_at <= now:
                    continue
                text = await render(
                    session,
                    NotificationType.EVENT_REMINDER,
                    event_title=event.title,
                    starts_at=format_human(starts_at),
                    location=event.location or "—",
                )
                if text is None:
                    return queued
                if shift is not None:
                    text = f"{text}\n🕒 Sizning smenangiz: {event_times.shift_text(shift)}"
                queued += await enqueue_for_members(
                    session,
                    type_=NotificationType.EVENT_REMINDER,
                    text=text,
                    dedup_prefix=f"event_reminder:{event.id}:" + (f"{shift.position}:" if shift else "") + f"{minutes}",
                    members=_registered_for(event.id, shift),
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
        line = await literary.book_line(session, book.id, f"reminder:{book.id}:{book.deadline}")
        if line:
            text += f"\n\n📖 Kitobdan: {line}"
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
    await channel.quote_posted(session, quote, author)
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


MAX_BUTTONS = 8
_BUTTON_URL = re.compile(r"^(https?://\S+|tg://\S+)$", re.IGNORECASE)


def parse_buttons(text: str | None) -> list[dict[str, str]]:
    """«Matn | https://havola» lines → link buttons (the admin writes them under the message)."""
    buttons: list[dict[str, str]] = []
    for number, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        title, separator, url = line.partition("|")
        title, url = title.strip(), url.strip()
        if url and not url.lower().startswith(("http://", "https://", "tg://")) and url.lower().startswith("t.me/"):
            url = f"https://{url}"
        if not separator or not title or not _BUTTON_URL.match(url):
            raise BadRequestError(
                "BUTTON_INVALID", f"{number}-qator: tugma «Matn | https://havola» ko'rinishida bo'lsin."
            )
        if len(title) > 64:
            raise BadRequestError("BUTTON_INVALID", f"{number}-qator: tugma matni 64 belgidan oshmasin.")
        buttons.append({"text": title, "url": url})
    if len(buttons) > MAX_BUTTONS:
        raise BadRequestError("TOO_MANY_BUTTONS", f"Ko'pi bilan {MAX_BUTTONS} ta tugma qo'shish mumkin.")
    return buttons


async def broadcast_message(
    session: AsyncSession, *, message: str, buttons: str | None = None, with_app_button: bool = True
) -> tuple[str, dict[str, Any] | None]:
    """The text and buttons exactly as members will get them."""
    text = await render(session, NotificationType.ADMIN_MESSAGE, message=message.strip())
    if text is None:  # template switched off: send the admin's words as plain text
        text = html.escape(message.strip(), quote=False)
    specs: list[dict[str, Any]] = list(parse_buttons(buttons))
    if with_app_button:
        specs += app_button("")["buttons"]
    return text, ({"buttons": specs} if specs else None)


async def broadcast(
    session: AsyncSession,
    *,
    actor_id: Any,
    message: str,
    faculty_id: Any | None = None,
    course: int | None = None,
    group_name: str | None = None,
    with_app_button: bool = True,
    buttons: str | None = None,
    dry_run: bool = False,
    only_to: Any | None = None,
    scheduled_at: datetime | None = None,
) -> int:
    """An admin's message to all active members or a part of them. Returns the recipient count.
    ``only_to``: a test send to the admin themself (to see it in the bot before everybody);
    ``scheduled_at``: a planned announcement (it can be cancelled until then)."""
    conditions = []
    if faculty_id is not None:
        conditions.append(User.faculty_id == faculty_id)
    if course is not None:
        conditions.append(User.course == course)
    if group_name:
        conditions.append(User.group_name == normalize_group(group_name))
    members = _members(*conditions)
    text, payload = await broadcast_message(
        session, message=message, buttons=buttons, with_app_button=with_app_button
    )  # checks the buttons even for a count
    if dry_run:
        return int(await session.scalar(select(func.count()).select_from(members.subquery())) or 0)
    broadcast_id = uuid.uuid4()
    if only_to is not None:
        await enqueue_notification(
            session,
            user_id=only_to,
            type_=NotificationType.ADMIN_MESSAGE,
            text="🧪 <b>Sinov</b> — a'zolar xabarni shunday ko'radi:\n\n" + text,
            dedup_key=f"broadcast-test:{broadcast_id}",
            payload=payload,
            priority=1,
        )
        await session.commit()
        return 1
    count = await enqueue_for_members(
        session,
        type_=NotificationType.ADMIN_MESSAGE,
        text=text,
        dedup_prefix=f"broadcast:{broadcast_id}",
        members=members,
        payload=payload,
        priority=3,
        scheduled_at=scheduled_at,
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
            "broadcast_id": str(broadcast_id),
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "faculty_id": str(faculty_id) if faculty_id else None,
            "course": course,
            "group_name": group_name,
        },
    )
    await session.commit()
    return count


async def cancel_broadcast(session: AsyncSession, *, actor_id: Any, broadcast_id: uuid.UUID) -> int:
    """Stop a planned announcement: the messages not sent yet are cancelled. Returns how many."""
    result = await session.execute(
        update(Notification)
        .where(
            Notification.dedup_key.like(f"broadcast:{broadcast_id}:%"),
            Notification.status == NotificationStatus.PENDING,
        )
        .values(status=NotificationStatus.CANCELLED, last_error="cancelled by an administrator")
    )
    cancelled = int(result.rowcount or 0)
    record_audit(
        session,
        actor_id=actor_id,
        action="NOTIFICATION_BROADCAST_CANCEL",
        entity_type="notification",
        entity_id=str(broadcast_id),
        after={"cancelled": cancelled},
    )
    await session.commit()
    return cancelled


async def broadcast_pending(session: AsyncSession, broadcast_id: str) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.dedup_key.like(f"broadcast:{broadcast_id}:%"),
                Notification.status == NotificationStatus.PENDING,
            )
        )
        or 0
    )
