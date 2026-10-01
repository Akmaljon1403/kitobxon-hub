"""Phase 15: notification queue, sender, scheduled reminders, business-event messages, broadcasts."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.methods.base import TelegramMethod
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import (
    AuditLog,
    BookQuote,
    BookRead,
    EventRegistration,
    Faculty,
    Notification,
    NotificationTemplate,
    TestAttempt,
    TestOption,
    TestQuestion,
    User,
    UserNotificationSettings,
)
from app.models.enums import (
    AttemptStatus,
    BookStatus,
    NotificationStatus,
    NotificationType,
    QuoteStatus,
    ReadingStatus,
    RegistrationStatus,
    UserStatus,
)
from app.security.permissions import Perm
from app.services import announcements, quizzes
from app.services.notifications import enqueue_notification
from app.utils.timezone import local_tz
from app.workers import sender as sender_module
from app.workers.jobs import JOBS, run_scheduled_jobs
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, FakeTelegramSession
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

sender_module.SEND_INTERVAL_SECONDS = 0  # no throttling pause in tests


class ScriptedSession(FakeTelegramSession):
    """Fake Telegram that can fail for chosen chat ids."""

    def __init__(self, failures: dict[int, Exception] | None = None, delay: float = 0) -> None:
        super().__init__()
        self.failures = failures or {}
        self.delay = delay

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if self.delay:
            await asyncio.sleep(self.delay)
        chat_id = getattr(method, "chat_id", None)
        if chat_id in self.failures:
            raise self.failures[chat_id]
        return await super().make_request(bot, method, timeout)


def _bot(session: FakeTelegramSession) -> Bot:
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _queue(
    db: AsyncSession, user: User, type_: NotificationType = NotificationType.SYSTEM, **kwargs: Any
) -> None:
    await enqueue_notification(db, user_id=user.id, type_=type_, text=kwargs.pop("text", "Salom"), **kwargs)
    await db.commit()


async def _notifications(db: AsyncSession, type_: NotificationType | None = None) -> list[Notification]:
    statement = select(Notification).order_by(Notification.created_at).execution_options(populate_existing=True)
    if type_ is not None:
        statement = statement.where(Notification.type == type_)
    return list(await db.scalars(statement))


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


# ---------------------------------------------------------------------------- sender


async def test_sender_delivers_and_respects_status_and_preferences(db: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example")
    active = await create_user(db)
    blocked = await create_user(db, status=UserStatus.BLOCKED)
    opted_out = await create_user(db)
    db.add(UserNotificationSettings(user_id=opted_out.id, quote_of_day=False))
    await db.commit()
    await _queue(
        db, active, NotificationType.EVENT_CREATED, payload={"buttons": [{"text": "Ochish", "app_route": "events/1"}]}
    )
    await _queue(db, blocked, NotificationType.EVENT_CREATED, dedup_key="b")
    await _queue(db, opted_out, NotificationType.QUOTE_OF_DAY, dedup_key="q")
    await _queue(db, opted_out, NotificationType.ADMIN_MESSAGE, dedup_key="critical")  # critical: always sent

    telegram = ScriptedSession()
    report = await send_due_notifications(get_session_factory(), _bot(telegram))
    assert (report.sent, report.skipped) == (2, 2)
    chats = [message.chat_id for message in telegram.sent_messages()]
    assert sorted(chats) == sorted([active.telegram_id, opted_out.telegram_id])
    first = next(m for m in telegram.sent_messages() if m.chat_id == active.telegram_id)
    button = first.reply_markup.inline_keyboard[0][0]
    assert button.web_app is not None and button.web_app.url.endswith("/app/#/events/1")

    statuses = {n.dedup_key or "active": n.status for n in await _notifications(db)}
    assert statuses == {
        "active": NotificationStatus.SENT,
        "b": NotificationStatus.SKIPPED,
        "q": NotificationStatus.SKIPPED,
        "critical": NotificationStatus.SENT,
    }
    # Nothing is sent twice.
    assert (await send_due_notifications(get_session_factory(), _bot(telegram))).total == 0


async def test_sender_handles_telegram_errors(db: AsyncSession) -> None:
    blocked_bot, flaky, limited = await create_user(db), await create_user(db), await create_user(db)
    await db.commit()
    for user in (blocked_bot, flaky, limited):
        await _queue(db, user, dedup_key=str(user.telegram_id))
    method: Any = None
    telegram = ScriptedSession(
        failures={
            blocked_bot.telegram_id: TelegramForbiddenError(method, "Forbidden: bot was blocked by the user"),
            flaky.telegram_id: TelegramNetworkError(method, "connection reset"),
            limited.telegram_id: TelegramRetryAfter(method, "Too Many Requests", 30),
        }
    )
    await send_due_notifications(get_session_factory(), _bot(telegram))
    rows = {n.dedup_key: n for n in await _notifications(db)}
    assert rows[str(blocked_bot.telegram_id)].status == NotificationStatus.FAILED
    retried = rows[str(flaky.telegram_id)]
    assert retried.status == NotificationStatus.PENDING
    assert retried.attempts == 1
    assert retried.scheduled_at > datetime.now(UTC)
    rate_limited = rows[str(limited.telegram_id)]
    assert rate_limited.status == NotificationStatus.PENDING
    assert rate_limited.attempts == 0  # being rate-limited is not the message's fault
    assert rate_limited.scheduled_at > datetime.now(UTC) + timedelta(seconds=20)


async def test_sender_gives_up_after_max_attempts(db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    await _queue(db, user, dedup_key="x")
    await db.execute(update(Notification).values(attempts=sender_module.MAX_ATTEMPTS - 1))
    await db.commit()
    telegram = ScriptedSession(failures={user.telegram_id: TelegramNetworkError(None, "timeout")})  # type: ignore[arg-type]
    await send_due_notifications(get_session_factory(), _bot(telegram))
    assert (await _notifications(db))[0].status == NotificationStatus.FAILED


async def test_parallel_senders_never_send_twice(db: AsyncSession) -> None:
    users = [await create_user(db) for _ in range(12)]
    await db.commit()
    for user in users:
        await _queue(db, user, dedup_key=str(user.id))
    telegram = ScriptedSession(delay=0.01)
    factory = get_session_factory()
    reports = await asyncio.gather(*(send_due_notifications(factory, _bot(telegram), limit=5) for _ in range(4)))
    reports += [await send_due_notifications(factory, _bot(telegram)) for _ in range(2)]
    chats = [message.chat_id for message in telegram.sent_messages()]
    assert len(chats) == 12
    assert len(set(chats)) == 12
    assert sum(report.sent for report in reports) == 12


async def test_outdated_reminders_are_skipped(db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    await _queue(db, user, NotificationType.ATTENDANCE_OPEN, dedup_key="old")
    await db.execute(update(Notification).values(created_at=datetime.now(UTC) - timedelta(hours=2)))
    await db.commit()
    telegram = ScriptedSession()
    report = await send_due_notifications(get_session_factory(), _bot(telegram))
    assert report.skipped == 1
    assert telegram.sent_messages() == []


# ---------------------------------------------------------------------------- business events


async def test_publishing_an_event_announces_it_once(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.EVENT_VIEW, Perm.EVENT_CREATE, Perm.EVENT_EDIT)
    member = await create_user(db)
    await create_user(db, status=UserStatus.PENDING)
    await db.commit()
    start = datetime.now(UTC) + timedelta(days=2)
    created = await client.post(
        "/api/v1/admin/events",
        json={
            "title": "<b>Muhokama</b>",
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
            "status": "DRAFT",
        },
        headers=admin_headers(admin),
    )
    event_id = created.json()["id"]
    assert await _notifications(db, NotificationType.EVENT_CREATED) == []
    for title in ("<b>Muhokama</b>", "Yangi nom"):
        await client.patch(
            f"/api/v1/admin/events/{event_id}",
            json={"status": "PUBLISHED", "title": title},
            headers=admin_headers(admin),
        )
    queued = await _notifications(db, NotificationType.EVENT_CREATED)
    recipients = {n.user_id for n in queued}
    assert member.id in recipients and admin.id in recipients
    assert len(queued) == len(recipients) == 2  # the pending member gets nothing, nobody gets two
    assert "&lt;b&gt;Muhokama&lt;/b&gt;" in queued[0].text  # titles are escaped for HTML messages


async def test_activating_a_book_announces_it(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.BOOK_VIEW, Perm.BOOK_CREATE, Perm.BOOK_EDIT)
    created = await client.post(
        "/api/v1/admin/books",
        json={"title": "Kecha va kunduz", "author": "Cho'lpon", "status": "DRAFT"},
        headers=admin_headers(admin),
    )
    assert await _notifications(db, NotificationType.NEW_BOOK) == []
    await client.patch(
        f"/api/v1/admin/books/{created.json()['id']}", json={"status": "ACTIVE"}, headers=admin_headers(admin)
    )
    queued = await _notifications(db, NotificationType.NEW_BOOK)
    assert len(queued) == 1
    assert "Kecha va kunduz" in queued[0].text
    assert queued[0].payload["buttons"][0]["app_route"].startswith("books/")


async def test_opening_attendance_notifies_registered_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.EVENT_VIEW, Perm.ATTENDANCE_VIEW, Perm.ATTENDANCE_MANAGE)
    registered, other = await create_user(db), await create_user(db)
    event = await create_event(db)
    db.add(EventRegistration(event_id=event.id, user_id=registered.id, status=RegistrationStatus.REGISTERED))
    await db.commit()
    opened = await client.post(
        f"/api/v1/admin/events/{event.id}/attendance/open", json={}, headers=admin_headers(admin)
    )
    assert opened.status_code == 204
    queued = await _notifications(db, NotificationType.ATTENDANCE_OPEN)
    assert [n.user_id for n in queued] == [registered.id]
    assert other.id not in {n.user_id for n in queued}


async def test_closing_a_test_sends_results_with_places(db: AsyncSession) -> None:
    member = await create_user(db)
    test = await create_test(db, passing_score=0)
    await db.commit()
    question = TestQuestion(test_id=test.id, text="Savol", points=1)
    db.add(question)
    await db.flush()
    correct = TestOption(question_id=question.id, text="Ha", is_correct=True)
    db.add_all([correct, TestOption(question_id=question.id, text="Yo'q")])
    await db.commit()
    await quizzes.start_attempt(db, user=member, test_id=test.id)
    await quizzes.submit_attempt(db, user_id=member.id, test_id=test.id, answers=[(question.id, [correct.id])])
    await quizzes.close_test(db, actor_id=None, test_id=test.id)
    queued = await _notifications(db, NotificationType.TEST_RESULT)
    assert len(queued) == 1
    assert "20 / 20" in queued[0].text
    assert "1-o'rinni" in queued[0].text


# ---------------------------------------------------------------------------- scheduled checks


async def test_event_reminders_follow_the_configured_offsets(db: AsyncSession) -> None:
    member = await create_user(db)
    now = datetime.now(UTC)
    soon = await create_event(db, starts_at=now + timedelta(minutes=50))
    tomorrow = await create_event(db, starts_at=now + timedelta(hours=23))
    later_today = await create_event(db, starts_at=now + timedelta(hours=2))
    for event in (soon, tomorrow, later_today):
        db.add(EventRegistration(event_id=event.id, user_id=member.id, status=RegistrationStatus.REGISTERED))
    await db.commit()

    assert await announcements.event_reminders(db, now) == 2
    await db.commit()
    assert await announcements.event_reminders(db, now) == 0  # dedup: never twice
    keys = sorted(n.dedup_key for n in await _notifications(db, NotificationType.EVENT_REMINDER))
    assert keys == sorted(
        [f"event_reminder:{soon.id}:60:{member.id}", f"event_reminder:{tomorrow.id}:1440:{member.id}"]
    )


async def test_test_started_and_ending_reminders(db: AsyncSession) -> None:
    done, waiting = await create_user(db), await create_user(db)
    now = datetime.now(UTC)
    test = await create_test(db, starts_at=now - timedelta(hours=1), ends_at=now + timedelta(minutes=30))
    await db.flush()
    db.add(
        TestAttempt(
            test_id=test.id,
            user_id=done.id,
            status=AttemptStatus.SUBMITTED,
            started_at=now - timedelta(minutes=20),
            deadline_at=now - timedelta(minutes=5),
            submitted_at=now - timedelta(minutes=10),
            question_order=[],
            option_order={},
            score=10,
        )
    )
    await db.commit()
    assert await announcements.test_started(db, now) == 2
    assert await announcements.test_ending(db, now) == 1
    await db.commit()
    ending = await _notifications(db, NotificationType.TEST_ENDING)
    assert [n.user_id for n in ending] == [waiting.id]


async def test_reading_reminders_go_to_readers_in_daytime(db: AsyncSession) -> None:
    reader, finished = await create_user(db), await create_user(db)
    noon = datetime.now(local_tz()).replace(hour=12, minute=0)
    book = await create_book(db, status=BookStatus.ACTIVE, deadline=noon.date() + timedelta(days=1))
    db.add_all(
        [
            BookRead(book_id=book.id, user_id=reader.id, status=ReadingStatus.READING),
            BookRead(book_id=book.id, user_id=finished.id, status=ReadingStatus.COMPLETED),
        ]
    )
    await db.commit()
    night = noon.replace(hour=2)
    assert await announcements.reading_reminders(db, night) == 0
    assert await announcements.reading_reminders(db, noon) == 1
    await db.commit()
    assert [n.user_id for n in await _notifications(db, NotificationType.READING_REMINDER)] == [reader.id]


async def test_quote_of_the_day_is_sent_once_after_its_time(db: AsyncSession) -> None:
    await create_user(db)
    morning = datetime.now(local_tz()).replace(hour=7, minute=0)
    quote = BookQuote(
        text="Kitob — eng yaxshi do'st.",
        author="Xalq maqoli",
        scheduled_date=morning.date(),
        status=QuoteStatus.SCHEDULED,
    )
    db.add(quote)
    await db.commit()
    assert await announcements.quote_of_day(db, morning) == 0  # before 09:00
    ten = morning.replace(hour=10)
    assert await announcements.quote_of_day(db, ten) == 1
    await db.commit()
    assert await announcements.quote_of_day(db, ten) == 0
    await db.refresh(quote)
    assert quote.status == QuoteStatus.SENT
    message = (await _notifications(db, NotificationType.QUOTE_OF_DAY))[0]
    assert "Kitob — eng yaxshi do'st." in message.text and "Xalq maqoli" in message.text


async def test_switched_off_template_sends_nothing(db: AsyncSession) -> None:
    member = await create_user(db)
    event = await create_event(db, starts_at=datetime.now(UTC) + timedelta(minutes=50))
    db.add(EventRegistration(event_id=event.id, user_id=member.id, status=RegistrationStatus.REGISTERED))
    await db.execute(
        update(NotificationTemplate)
        .where(NotificationTemplate.type == NotificationType.EVENT_REMINDER)
        .values(is_active=False)
    )
    await db.commit()
    assert await announcements.event_reminders(db) == 0


async def test_scheduler_runs_every_job(db: AsyncSession) -> None:
    results = await run_scheduled_jobs(get_session_factory())
    assert set(results) == {name for name, _ in JOBS}


# ---------------------------------------------------------------------------- admin broadcast


async def test_broadcast_counts_queues_and_audits(client: httpx.AsyncClient, db: AsyncSession) -> None:
    sender = await _admin(db, Perm.NOTIFICATION_SEND)
    viewer = await _admin(db, Perm.USER_VIEW)
    faculty = Faculty(name="Pediatriya")
    db.add(faculty)
    await db.flush()
    in_faculty = await create_user(db, faculty_id=faculty.id, course=3)
    await create_user(db, faculty_id=faculty.id, course=1)
    await db.commit()
    body = {"message": "Ertaga soat 15:00 da yig'ilish bo'ladi.", "faculty_id": str(faculty.id), "course": 3}

    denied = await client.post("/api/v1/admin/notifications/broadcast", json=body, headers=admin_headers(viewer))
    assert denied.status_code == 403
    preview = await client.post(
        "/api/v1/admin/notifications/broadcast", json={**body, "dry_run": True}, headers=admin_headers(sender)
    )
    assert preview.json() == {"recipients": 1, "queued": False}
    assert await _notifications(db) == []

    sent = await client.post("/api/v1/admin/notifications/broadcast", json=body, headers=admin_headers(sender))
    assert sent.json() == {"recipients": 1, "queued": True}
    queued = await _notifications(db, NotificationType.ADMIN_MESSAGE)
    assert [n.user_id for n in queued] == [in_faculty.id]
    assert queued[0].text == "📢 Ertaga soat 15:00 da yig'ilish bo'ladi."
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "NOTIFICATION_BROADCAST"))
    assert audit.after["recipients"] == 1

    summary = await client.get("/api/v1/admin/notifications/summary", headers=admin_headers(sender))
    assert summary.status_code == 200
    assert summary.json()["pending"] == 1
    assert summary.json()["recent_broadcasts"][0]["recipients"] == 1


async def test_member_counts_helper_ignores_inactive(db: AsyncSession) -> None:
    await create_user(db)
    await create_user(db, status=UserStatus.BLOCKED)
    await db.commit()
    assert await announcements.broadcast(db, actor_id=None, message="Test xabar", dry_run=True) == 1
    assert await db.scalar(select(func.count()).select_from(Notification)) == 0


async def test_worker_loop_sends_and_stops(db: AsyncSession, monkeypatch) -> None:
    from types import SimpleNamespace

    from app.workers import runner

    member = await create_user(db)
    await db.commit()
    await _queue(db, member, dedup_key="loop")
    telegram = ScriptedSession()
    monkeypatch.setattr(runner, "get_bot_runtime", lambda: SimpleNamespace(bot=_bot(telegram)))
    stop = asyncio.Event()
    task = asyncio.create_task(runner.run_worker(stop))
    for _ in range(50):
        if telegram.sent_messages():
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=5)
    assert [m.chat_id for m in telegram.sent_messages()] == [member.telegram_id]
