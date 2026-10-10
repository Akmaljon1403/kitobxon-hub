"""Events, round two: shifts, moved events, the end of an event, links from the channel, the report post
and the worker waking up for the next due moment."""

from __future__ import annotations

import io
import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMediaGroup, SendMessage
from aiogram.methods.base import TelegramMethod
from aiogram.types import Chat, Message
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import (
    AttendanceSession,
    ChannelPost,
    Event,
    EventFeedback,
    EventRegistration,
    Notification,
    ReportPhoto,
)
from app.models.enums import ChannelPostKind, ChannelPostStatus, EventStatus, NotificationStatus
from app.security.permissions import Perm
from app.services import attendance, channel
from app.services import events as event_service
from app.services.settings import update_setting
from app.services.storage import get_storage
from app.workers.channel_sender import send_channel_posts
from app.workers.timing import next_due
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(1_200_000)
EVENT_PERMS = (Perm.EVENT_VIEW, Perm.EVENT_CREATE, Perm.EVENT_EDIT, Perm.ATTENDANCE_VIEW, Perm.ATTENDANCE_MANAGE)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "bot_username", "kitobxon_test_bot")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _admin(db: AsyncSession, *roles: str) -> Any:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    for role in roles:
        await grant_role(db, admin, role)
    await grant_permissions(db, admin, *EVENT_PERMS, Perm.REPORT_VIEW, Perm.REPORT_CREATE, Perm.REPORT_APPROVE)
    return admin


def _iso(value: datetime) -> str:
    return value.isoformat()


class ChannelTelegram(FakeTelegramSession):
    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, SendMediaGroup):
            self.requests.append(method)
            chat = Chat(id=-1001, type="channel")
            return [
                Message(message_id=10 + index, date=datetime.now(UTC), chat=chat) for index in range(len(method.media))
            ]
        if isinstance(getattr(method, "chat_id", None), str):
            self.requests.append(method)
            return Message(message_id=len(self.requests), date=datetime.now(UTC), chat=Chat(id=-1001, type="channel"))
        return await super().make_request(bot, method, timeout)


async def test_two_shifts_open_attendance_twice_but_count_once(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    headers = admin_headers(admin)
    day = datetime.now(UTC).replace(microsecond=0) + timedelta(days=2)
    body = {
        "title": "Ikki smenali muhokama",
        "status": "PUBLISHED",
        "starts_at": _iso(day),
        "ends_at": _iso(day + timedelta(hours=6)),
        "shifts": [
            {"starts_at": _iso(day + timedelta(hours=4)), "ends_at": _iso(day + timedelta(hours=5, minutes=30))},
            {"starts_at": _iso(day), "ends_at": _iso(day + timedelta(hours=1, minutes=30))},
        ],
    }
    created = await client.post("/api/v1/admin/events", json=body, headers=headers)
    assert created.status_code == 201, created.text
    event = created.json()
    assert [shift["position"] for shift in event["shifts"]] == [1, 2]
    first, second = event["shifts"]
    assert first["starts_at"].startswith(day.isoformat()[:16]) and event["starts_at"] == first["starts_at"]
    assert event["ends_at"] == second["ends_at"]

    overlap = dict(
        body,
        shifts=[
            body["shifts"][1],
            {"starts_at": _iso(day + timedelta(hours=1)), "ends_at": _iso(day + timedelta(hours=2))},
        ],
    )
    assert (await client.post("/api/v1/admin/events", json=overlap, headers=headers)).status_code == 400

    morning, evening = await create_user(db), await create_user(db)
    await db.commit()
    url = f"/api/v1/events/{event['id']}/register"
    need = await client.post(url, headers=member_headers(morning))
    assert need.status_code == 400 and need.json()["error"]["code"] == "SHIFT_REQUIRED"
    await client.post(url, json={"shift_id": first["id"]}, headers=member_headers(morning))
    joined = await client.post(url, json={"shift_id": second["id"]}, headers=member_headers(evening))
    assert joined.json()["my_shift_id"] == second["id"] and joined.json()["is_registered"] is True
    # Switching to the other shift keeps one registration.
    await client.post(url, json={"shift_id": first["id"]}, headers=member_headers(evening))
    await client.post(url, json={"shift_id": second["id"]}, headers=member_headers(evening))
    assert await db.scalar(select(func.count()).select_from(EventRegistration)) == 2

    event_id = uuid.UUID(event["id"])
    opens_first = datetime.fromisoformat(first["attendance_opens_at"])
    assert await attendance.open_scheduled_sessions(db, now=opens_first + timedelta(minutes=1)) == 1
    assert await attendance.open_scheduled_sessions(db, now=opens_first + timedelta(minutes=2)) == 0
    notes = list(
        await db.scalars(select(Notification).where(Notification.dedup_key.like(f"attendance_open:{event_id}:1:%")))
    )
    assert [n.user_id for n in notes] == [morning.id] and "1-smena" in notes[0].text

    opens_second = datetime.fromisoformat(second["attendance_opens_at"])
    assert await attendance.open_scheduled_sessions(db, now=opens_second + timedelta(minutes=1)) == 1
    sessions = list(await db.scalars(select(AttendanceSession).where(AttendanceSession.event_id == event_id)))
    assert len(sessions) == 2 and len({s.shift_id for s in sessions}) == 2
    assert sum(1 for s in sessions if s.status.value == "OPEN") == 1
    assert (
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.dedup_key.like(f"attendance_open:{event_id}:2:%"))
        )
        == 1
    )


async def test_a_moved_event_updates_posts_and_reminders(db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.enabled", value=True, actor_id=admin.id)
    starts = datetime.now(UTC) + timedelta(days=3)
    event = await event_service.create_event(
        db,
        actor_id=admin.id,
        data={
            "title": "Kecha va kunduz",
            "status": "PUBLISHED",
            "starts_at": starts,
            "ends_at": starts + timedelta(hours=2),
        },
    )
    member = await create_user(db)
    await db.commit()
    await event_service.register(db, user_id=member.id, event_id=event.id)
    post = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == f"event:{event.id}"))
    assert post.buttons == [{"text": "✅ Qatnashaman", "bot_start": f"ev_{event.id.hex}"}]
    assert "Qatnashaman" in post.text

    # Still waiting: the post itself gets the new time.
    later = starts + timedelta(days=1)
    await event_service.update_event(
        db, actor_id=admin.id, event_id=event.id, changes={"starts_at": later, "ends_at": later + timedelta(hours=2)}
    )
    await db.refresh(post)
    assert post.status == ChannelPostStatus.PENDING
    event = await db.get(Event, event.id)
    assert event.attendance_opens_at == later - timedelta(minutes=10)  # the window moved with the event
    told = await db.scalar(select(Notification.text).where(Notification.dedup_key.like(f"event_change:{event.id}:%")))
    assert "O'zgarish" in told

    # Already announced: a short update post; a reminder already sent gives way to a new one.
    await db.execute(update(ChannelPost).where(ChannelPost.id == post.id).values(status=ChannelPostStatus.SENT))
    db.add(
        Notification(
            user_id=member.id,
            type="EVENT_REMINDER",
            text="Eski eslatma",
            dedup_key=f"event_reminder:{event.id}:60:{member.id}",
            status=NotificationStatus.SENT,
        )
    )
    await db.commit()
    again = later + timedelta(hours=3)
    await event_service.update_event(
        db,
        actor_id=admin.id,
        event_id=event.id,
        changes={"starts_at": again, "ends_at": again + timedelta(hours=2), "location": "Aula"},
    )
    change = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key.like(f"event_change:{event.id}:%")))
    assert change is not None and "o'zgarish" in change.text.lower() and "Aula" in change.text
    old = await db.scalar(select(Notification).where(Notification.text == "Eski eslatma"))
    assert old.dedup_key.startswith(f"event_reminder:{event.id}:60:") and "~" in old.dedup_key

    await event_service.update_event(
        db, actor_id=admin.id, event_id=event.id, changes={"status": EventStatus.CANCELLED}
    )
    cancelled = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == f"event_cancel:{event.id}"))
    assert cancelled is not None and "bekor" in cancelled.text
    assert await db.scalar(
        select(Notification.id).where(Notification.dedup_key == f"event_cancel:{event.id}:{member.id}")
    )


async def test_the_end_of_an_event(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _admin(db, "SUPER_ADMIN")
    admin = await _admin(db)
    member = await create_user(db)
    event = await create_event(db, title="Yakunlanadigan", starts_at=datetime.now(UTC) - timedelta(hours=1))
    await db.commit()
    await event_service.register(db, user_id=member.id, event_id=event.id)

    url = f"/api/v1/admin/events/{event.id}/finish"
    assert (await client.post(url, headers=admin_headers(admin))).status_code == 403
    finished = await client.post(url, headers=admin_headers(boss))
    assert finished.status_code == 200 and finished.json()["status"] == "COMPLETED"
    stopped = await db.scalar(
        select(Notification.text).where(Notification.dedup_key == f"event_stopped:{event.id}:{member.id}")
    )
    assert "yakunlandi" in stopped
    done = await db.scalar(select(Notification).where(Notification.dedup_key == f"event_done:{event.id}:{boss.id}"))
    assert "Hisobotini" in done.text and done.payload["buttons"][0]["admin_route"] == f"reports?event={event.id}"

    # The scheduler completes an event whose time is over (once).
    other = await create_event(db, title="O'tgan tadbir", starts_at=datetime.now(UTC) - timedelta(hours=3))
    await db.commit()
    assert await event_service.complete_finished(db) == 1
    await db.commit()
    assert (await db.get(Event, other.id)).status == EventStatus.COMPLETED
    assert await event_service.complete_finished(db) == 0
    future = await create_event(db, starts_at=datetime.now(UTC) + timedelta(days=1))
    await db.commit()
    assert (
        await client.post(f"/api/v1/admin/events/{future.id}/finish", headers=admin_headers(boss))
    ).status_code == 409


async def test_best_events_by_rating(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    good, weak = await create_event(db, title="Zo'r kecha"), await create_event(db, title="Oddiy kun")
    for index in range(4):
        member = await create_user(db)
        db.add(EventFeedback(event_id=good.id, user_id=member.id, rating=5 if index else 4))
        db.add(EventFeedback(event_id=weak.id, user_id=member.id, rating=3))
    await db.commit()
    top = (await client.get("/api/v1/admin/events/top-rated", headers=admin_headers(admin))).json()
    assert [row["title"] for row in top] == ["Zo'r kecha", "Oddiy kun"] and top[0]["average"] == 4.75
    listed = (await client.get("/api/v1/admin/events", headers=admin_headers(admin))).json()["items"]
    assert next(e for e in listed if e["title"] == "Zo'r kecha")["rating"] == 4.8


async def test_links_from_the_channel_open_the_event_and_the_book(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    event = await create_event(db, title="Ochiq muhokama", starts_at=datetime.now(UTC) + timedelta(days=1))
    book = await create_book(db, title="Sariq devni minib", status="ACTIVE")
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.send(f"/start ev_{event.id.hex}")
    assert "«Ochiq muhokama»" in harness.last_text() and texts.EVENT_WHY_REGISTER in harness.last_text()
    await harness.press(f"evr:{event.id.hex}:0")
    assert harness.session.alerts()[-1] == texts.EVENT_REGISTERED_ALERT
    assert await db.scalar(select(EventRegistration.id).where(EventRegistration.user_id == member.id))
    await harness.send(f"/start bk_{book.id.hex}")
    assert "«Sariq devni minib»" in harness.last_text()
    await harness.press(f"bkr:{book.id.hex}")
    assert harness.last_text() == texts.BOOK_STARTED

    # Someone new: registration first, then the event they came for.
    newcomer = BotHarness(next(_ids), first_name="Nodira")
    await newcomer.send(f"/start ev_{event.id.hex}")
    await newcomer.send("Nodira")
    await newcomer.send("Aliyeva")
    await newcomer.share_contact("+998901117788")
    await newcomer.press("reg:course:1")
    await newcomer.send("101")
    await newcomer.press("reg:confirm")
    assert "«Ochiq muhokama»" in newcomer.last_text()


async def test_approved_event_report_goes_to_the_channel_with_photos(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.enabled", value=True, actor_id=admin.id)
    await update_setting(db, key="channel.more_photos_url", value="https://t.me/fjsti_rasmlar", actor_id=admin.id)
    book = await create_book(db, title="O'tkan kunlar", author="Abdulla Qodiriy")
    event = await create_event(
        db, title="Davra suhbati", book_id=book.id, starts_at=datetime.now(UTC) - timedelta(days=1)
    )
    member = await create_user(db)
    await db.commit()
    await attendance.manual_check_in(
        db, actor_id=admin.id, event_id=event.id, user_id=member.id, note="Shaxsan ko'rildi"
    )
    headers = admin_headers(admin)
    report = (await client.post("/api/v1/admin/reports", json={"event_id": str(event.id)}, headers=headers)).json()
    for color in ("red", "green", "blue"):
        image = io.BytesIO()
        Image.new("RGB", (600, 400), color).save(image, format="JPEG")
        uploaded = await client.post(
            f"/api/v1/admin/reports/{report['id']}/photos",
            files={"file": ("p.jpg", image.getvalue(), "image/jpeg")},
            headers=headers,
        )
        assert uploaded.status_code == 201
    await client.post(f"/api/v1/admin/reports/{report['id']}/generate", json={"use_ai": False}, headers=headers)
    approved = await client.post(f"/api/v1/admin/reports/{report['id']}/approve", headers=headers)
    assert approved.status_code == 200, approved.text

    post = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == f"report:{event.id}"))
    assert post.kind == ChannelPostKind.REPORT and len(post.extra_photo_keys) == 2
    assert "«O'tkan kunlar» (Abdulla Qodiriy) asari bo'yicha davra suhbati" in post.text
    assert "munosib rag'batlantirildilar" in post.text and "t.me/FJSTIMutolaaxona" in post.text
    assert post.buttons == [{"text": "📸 Boshqa rasmlar", "url": "https://t.me/fjsti_rasmlar"}]
    ready = await db.scalar(select(Notification.text).where(Notification.dedup_key == f"report_ready:{report['id']}"))
    assert "muvaffaqiyatli yaratildi" in ready

    await db.execute(update(ChannelPost).where(ChannelPost.id == post.id).values(scheduled_at=datetime.now(UTC)))
    await db.commit()
    telegram = ChannelTelegram()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    assert await send_channel_posts(get_session_factory(), bot) == 1
    album = next(r for r in telegram.requests if isinstance(r, SendMediaGroup))
    assert len(album.media) == 3 and "davra suhbati" in album.media[0].caption
    follow = [r for r in telegram.requests if isinstance(r, SendMessage)][-1]
    assert follow.reply_markup.inline_keyboard[0][0].url == "https://t.me/fjsti_rasmlar"
    assert await db.scalar(select(func.count()).select_from(ReportPhoto)) == 3
    assert await get_storage().exists(post.photo_key)


async def test_the_worker_wakes_for_the_next_due_moment(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    assert await next_due(db, now) is not None  # at least the daily quote time
    await create_test(db, starts_at=now + timedelta(minutes=7))
    member = await create_user(db)
    db.add(Notification(user_id=member.id, type="SYSTEM", text="keyin", scheduled_at=now + timedelta(minutes=20)))
    await db.commit()
    due = await next_due(db, now)
    assert timedelta(minutes=6) < due - now <= timedelta(minutes=7)
    await create_event(db, starts_at=now + timedelta(minutes=30), attendance_opens_at=now + timedelta(minutes=3))
    await db.commit()
    assert (await next_due(db, now)) - now <= timedelta(minutes=3)
    post = await channel.queue(
        db, kind=ChannelPostKind.MANUAL, text="x", automatic=False, scheduled_at=now + timedelta(minutes=1)
    )
    await db.commit()
    assert post and (await next_due(db, now)) - now <= timedelta(minutes=1)
