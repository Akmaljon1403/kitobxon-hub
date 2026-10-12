"""Round F3: the new study year also moves group numbers and asks the last course «Bitirdingizmi?»,
the yearly personal summary, planned announcements and the night-time quiet hours."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, time, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.database import get_session_factory
from app.models import BookRead, Notification, Season
from app.models.enums import (
    NotificationStatus,
    NotificationType,
    ReadingStatus,
    ScoreCategory,
    SeasonStatus,
    UserStatus,
)
from app.security.permissions import Perm
from app.services import documents, lifecycle
from app.services.notifications import enqueue_notification
from app.services.scoring import award_points
from app.services.settings import update_setting
from app.utils.timezone import local_tz
from app.workers import sender
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(2_000_000)
NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


async def test_new_year_moves_courses_only_and_asks_the_last_course(db: AsyncSession) -> None:
    second = await create_user(db, course=2, group_name="201")
    named = await create_user(db, course=2, group_name="DI-21")
    last = await create_user(db, course=6, group_name="601", telegram_id=next(_ids))
    alumni = await create_user(db, course=6, group_name="602", graduated_at=NOW - timedelta(days=300))
    await db.commit()
    await update_setting(db, key="academic.current_year", value=2025, actor_id=None)

    assert await lifecycle.new_study_year(db, NOW) == 2
    for user in (second, named, last, alumni):
        await db.refresh(user)
    assert (second.course, second.group_name) == (3, "201")  # only the course moves; the group stays
    assert (named.course, named.group_name) == (3, "DI-21")
    assert (last.course, last.group_name) == (6, "601")
    asked = set(
        await db.scalars(select(Notification.user_id).where(Notification.dedup_key.like("graduate-question:%")))
    )
    assert asked == {last.id}  # the alumni was not asked again

    harness = BotHarness(last.telegram_id)
    await harness.press("grad:yes")
    assert harness.last_text() == texts.GRADUATED
    await db.refresh(last)
    assert last.graduated_at is not None
    await harness.press("grad:no")
    await db.refresh(last)
    assert last.graduated_at is None and harness.last_text() == texts.STILL_STUDYING


async def test_graduates_in_the_profile_admin_panel_and_documents(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, course=6)
    current = await create_user(db, course=6)
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.USER_VIEW, Perm.USER_MANAGE)
    changed = await client.patch(
        f"/api/v1/admin/users/{member.id}", json={"graduated": True}, headers=admin_headers(admin)
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["graduated_at"] is not None
    assert (await client.get("/api/v1/me", headers=member_headers(member))).json()["graduated"] is True
    members, _ = await documents._activity(db, documents.Params(course=6))
    assert [user.id for user, _ in members] == [current.id]  # a course means its current students


async def test_the_yearly_summary(db: AsyncSession) -> None:
    reader = await create_user(db)
    idle = await create_user(db)
    await create_user(db, referred_by=reader.id)  # a friend this year
    db.add(
        Season(
            name="2026–2027 o'quv yili",
            starts_on=NOW.date(),
            ends_on=NOW.date(),
            status=SeasonStatus.ACTIVE,
            is_current=True,
        )
    )
    await db.flush()
    book = await create_book(db)
    db.add(BookRead(book_id=book.id, user_id=reader.id, status=ReadingStatus.COMPLETED, completed_at=datetime.now(UTC)))
    await award_points(db, user_id=reader.id, amount=40, category=ScoreCategory.TEST, idempotency_key=f"t:{reader.id}")
    await db.commit()
    today = datetime.now(UTC)
    local_day = today.astimezone(local_tz()).strftime("%m-%d")
    await update_setting(db, key="academic.summary_day", value=local_day, actor_id=None)

    assert await lifecycle.year_summaries(db, today) >= 1
    summary = await db.scalar(select(Notification).where(Notification.dedup_key.like(f"year-summary:%:{reader.id}")))
    assert summary is not None and summary.type == NotificationType.DIGEST
    assert "O'qilgan kitoblar: <b>1</b>" in summary.text and "<b>40</b>" in summary.text
    assert "1-o'rin" in summary.text and "do'stlar: <b>1</b>" in summary.text
    assert await db.scalar(select(func.count()).where(Notification.dedup_key.like(f"year-summary:%:{idle.id}"))) == 0
    await lifecycle.year_summaries(db, today)  # again the same day: nothing doubles
    mine = select(func.count()).where(Notification.dedup_key.like(f"year-summary:%:{reader.id}"))
    assert await db.scalar(mine) == 1
    assert await lifecycle.year_summaries(db, today + timedelta(days=1)) == 0  # another day


async def test_planned_announcements(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db)
    await create_user(db)
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    headers = admin_headers(admin)
    later = datetime.now(UTC) + timedelta(days=2)
    sent = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"message": "Ertaga tadbir bor!", "scheduled_at": later.isoformat()},
        headers=headers,
    )
    assert sent.status_code == 200 and sent.json()["recipients"] == 3
    planned = list(await db.scalars(select(Notification).where(Notification.dedup_key.like("broadcast:%"))))
    assert planned and all(item.scheduled_at > datetime.now(UTC) + timedelta(days=1) for item in planned)
    history = (await client.get("/api/v1/admin/notifications/summary", headers=headers)).json()["recent_broadcasts"]
    assert history[0]["waiting"] == 3 and history[0]["scheduled_at"] is not None
    cancelled = await client.post(
        f"/api/v1/admin/notifications/broadcast/{history[0]['broadcast_id']}/cancel", headers=headers
    )
    assert cancelled.json() == {"cancelled": 3}
    statuses = set(await db.scalars(select(Notification.status).where(Notification.dedup_key.like("broadcast:%"))))
    assert statuses == {NotificationStatus.CANCELLED}

    too_far = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"message": "Uzoq kelajak", "scheduled_at": (datetime.now(UTC) + timedelta(days=120)).isoformat()},
        headers=headers,
    )
    assert too_far.status_code == 400
    past = await client.post(
        "/api/v1/admin/notifications/broadcast",
        json={"message": "Darhol", "scheduled_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
        headers=headers,
    )
    assert past.status_code == 200  # a time in the past simply means «now»


@pytest.mark.quiet_hours
async def test_quiet_hours_window(db: AsyncSession) -> None:
    tz = local_tz()
    night = datetime.combine(NOW.date(), time(23, 30), tzinfo=tz)
    morning = datetime.combine(NOW.date(), time(7, 0), tzinfo=tz)
    day = datetime.combine(NOW.date(), time(13, 0), tzinfo=tz)
    end = await sender.quiet_until(db, night)
    assert end == datetime.combine(NOW.date() + timedelta(days=1), time(8, 0), tzinfo=tz)
    assert await sender.quiet_until(db, morning) == datetime.combine(NOW.date(), time(8, 0), tzinfo=tz)
    assert await sender.quiet_until(db, day) is None
    await update_setting(db, key="notifications.quiet_hours", value="13:00-15:00", actor_id=None)
    assert await sender.quiet_until(db, day) == datetime.combine(NOW.date(), time(15, 0), tzinfo=tz)
    await update_setting(db, key="notifications.quiet_hours", value="", actor_id=None)
    assert await sender.quiet_until(db, night) is None


@pytest.mark.quiet_hours
async def test_mass_messages_wait_for_the_morning(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    tz = local_tz()
    local = datetime.now(UTC).astimezone(tz)
    start = (local - timedelta(hours=1)).strftime("%H:%M")
    end = (local + timedelta(hours=1)).strftime("%H:%M")
    if start >= end:  # around midnight the window wraps; any window that contains «now» will do
        start, end = (local - timedelta(minutes=5)).strftime("%H:%M"), (local + timedelta(minutes=5)).strftime("%H:%M")
    await update_setting(db, key="notifications.quiet_hours", value=f"{start}-{end}", actor_id=None)
    await enqueue_notification(
        db, user_id=member.id, type_=NotificationType.ADMIN_MESSAGE, text="E'lon", dedup_key="quiet:mass", priority=3
    )
    await enqueue_notification(
        db,
        user_id=member.id,
        type_=NotificationType.SYSTEM,
        text="To'lov tasdiqlandi",
        dedup_key="quiet:urgent",
        priority=2,
    )
    await db.commit()
    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    report = await sender.send_due_notifications(get_session_factory(), bot)
    assert report.sent == 1
    held: Any = await db.scalar(select(Notification).where(Notification.dedup_key == "quiet:mass"))
    await db.refresh(held)
    assert held.status == NotificationStatus.PENDING and held.scheduled_at > datetime.now(UTC)


async def test_the_morning_digest_for_the_owners(db: AsyncSession) -> None:
    from app.services import admin_digest
    from tests.factories import create_event

    owner = await create_user(db)
    await create_user(db, status=UserStatus.PENDING)
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    now = datetime.now(UTC)
    local = now.astimezone(local_tz())
    starts = datetime.combine(local.date(), time(23, 0), tzinfo=local_tz())
    await create_event(db, title="Navoiy kechasi", starts_at=starts)
    await db.commit()

    assert await admin_digest.send(db, now) == 1
    note = await db.scalar(select(Notification).where(Notification.dedup_key.like(f"admin-digest:%:{owner.id}")))
    assert note is not None
    assert "Tasdiq kutayotgan a'zolar: <b>1</b>" in note.text and "23:00 — Navoiy kechasi" in note.text
    await update_setting(db, key="admin.morning_digest", value=False, actor_id=None)
    assert await admin_digest.send(db, now) == 0


async def test_premium_emoji_in_the_admin_panel(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aiogram.methods import SendMessage

    from app.services import custom_emoji

    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.runtime_bot", lambda: bot)
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.SETTINGS_MANAGE)
    headers = admin_headers(admin)
    try:
        await custom_emoji.save(
            db, actor_id=admin.id, pairs=[("❤", "5368324170671202286", "❤️"), ("📚", "5373123633415723713", "📚")]
        )
        listed = (await client.get("/api/v1/admin/custom-emoji", headers=headers)).json()
        assert [item["emoji"] for item in listed["items"]] == ["❤", "📚"] and not listed["paused"]
        sample = await client.post("/api/v1/admin/custom-emoji/test", headers=headers)
        assert sample.json() == {"sent": True, "premium_shown": True}
        message = next(request for request in telegram.requests if isinstance(request, SendMessage))
        assert message.chat_id == admin.telegram_id and 'emoji-id="5368324170671202286"' in message.text
        removed = await client.delete("/api/v1/admin/custom-emoji", params={"emoji": "❤️"}, headers=headers)
        assert removed.status_code == 204
        assert [
            item["emoji"] for item in (await client.get("/api/v1/admin/custom-emoji", headers=headers)).json()["items"]
        ] == ["📚"]
        await client.delete("/api/v1/admin/custom-emoji", headers=headers)
        assert (await client.get("/api/v1/admin/custom-emoji", headers=headers)).json()["items"] == []
        member = await create_user(db)
        await db.commit()
        assert (await client.get("/api/v1/admin/custom-emoji", headers=member_headers(member))).status_code == 403
    finally:
        custom_emoji.use({})  # the replacement table is per process: leave it empty for other tests
