"""The bot's posts in the club's Telegram channel: automatic posts, the sender, admin tools, /stiker."""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage, SendPhoto, SendSticker
from aiogram.methods.base import TelegramMethod
from aiogram.types import Chat, Message, Sticker, Update
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import BookQuote, ChannelPost, ChannelSticker, Notification, ScoreTransaction, User
from app.models.enums import (
    BookStatus,
    ChannelPostKind,
    ChannelPostStatus,
    NotificationType,
    QuoteStatus,
    ScoreCategory,
)
from app.security.permissions import Perm
from app.services import announcements, channel
from app.services.settings import update_setting
from app.services.storage import get_storage
from app.utils.timezone import local_tz
from app.workers.channel_sender import send_channel_posts
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_event, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "bot_username", "kitobxon_test_bot")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _admin(db: AsyncSession, **user: Any) -> User:
    admin = await create_user(db, **user)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    return admin


async def _switch_on(db: AsyncSession, actor: User) -> None:
    await update_setting(db, key="channel.enabled", value=True, actor_id=actor.id)


def _local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=local_tz())


async def _posts(db: AsyncSession) -> list[ChannelPost]:
    return list(await db.scalars(select(ChannelPost).order_by(ChannelPost.created_at)))


def test_chat_address_and_night_hours() -> None:
    assert channel.normalize_chat_id("https://t.me/FJSTIMutolaaxona") == "@FJSTIMutolaaxona"
    assert channel.normalize_chat_id("t.me/FJSTIMutolaaxona/") == "@FJSTIMutolaaxona"
    assert channel.normalize_chat_id("@FJSTIMutolaaxona") == "@FJSTIMutolaaxona"
    assert channel.normalize_chat_id("-1001234567890") == -1001234567890
    assert channel.normalize_chat_id("bad name!") is None and channel.normalize_chat_id("") is None
    day = date(2026, 10, 7)
    assert channel.next_daytime(_local(day, 14)) == _local(day, 14)
    assert channel.next_daytime(_local(day, 23, 10)) == _local(day + timedelta(days=1), 9)
    assert channel.next_daytime(_local(day, 6)) == _local(day, 9)


async def test_new_event_and_book_posts(db: AsyncSession) -> None:
    admin = await _admin(db)
    book = await create_book(
        db, title="O'tkan kunlar", cover_key="covers/otkan.jpg", deadline=date(2030, 1, 1), status=BookStatus.ACTIVE
    )
    event = await create_event(
        db, title="Kitob kechasi", book_id=book.id, starts_at=datetime.now(UTC) + timedelta(days=3)
    )
    await db.commit()

    await announcements.event_published(db, event)
    assert await _posts(db) == []  # the channel is switched off by default

    await _switch_on(db, admin)
    await announcements.event_published(db, event)
    await announcements.event_published(db, event)  # republishing does not post twice
    await announcements.book_published(db, book)
    await db.commit()
    posts = await _posts(db)
    assert [post.kind for post in posts] == [ChannelPostKind.EVENT, ChannelPostKind.BOOK]
    event_post, book_post = posts
    assert "«Kitob kechasi»" in event_post.text
    assert "«O'tkan kunlar» — Abdulla Qodiriy" in event_post.text and "Davomat" in event_post.text
    assert event_post.photo_key == "covers/otkan.jpg" and event_post.buttons == [channel.event_button(event)]
    assert event_post.scheduled_at.astimezone(local_tz()).time() >= channel.DAYTIME[0]
    assert "O'qish muddati" in book_post.text

    # Switching one kind off stops only that kind.
    await update_setting(db, key="channel.post_books", value=False, actor_id=admin.id)
    other = await create_book(db, title="Boshqa kitob", status=BookStatus.ACTIVE)
    await announcements.book_published(db, other)
    assert len(await _posts(db)) == 2


async def test_scheduled_posts(db: AsyncSession) -> None:
    admin = await _admin(db)
    await _switch_on(db, admin)
    monday = date(2026, 11, 2)  # a Monday, the first week of November
    now = _local(monday, 11)
    book = await create_book(db, title="Alkimyogar", deadline=monday + timedelta(days=2), status=BookStatus.ACTIVE)
    long_book = await create_book(
        db,
        title="Sariq devni minib",
        start_date=monday - timedelta(days=10),
        deadline=monday + timedelta(days=10),
        status=BookStatus.ACTIVE,
    )
    tomorrow = await create_event(db, title="Ertangi suhbat", book_id=book.id, starts_at=now + timedelta(hours=24))
    today = await create_event(db, title="Bugungi kecha", starts_at=now + timedelta(hours=2, minutes=50))
    member = await create_user(db, first_name="Laylo", last_name="Karimova")
    db.add(
        ScoreTransaction(
            user_id=member.id,
            amount=50,
            category=ScoreCategory.ATTENDANCE,
            idempotency_key="october",
            created_at=_local(date(2026, 10, 20), 12),
        )
    )
    await db.commit()

    created = await channel.scheduled_posts(db, now=now)
    await db.commit()
    keys = {post.dedup_key: post for post in await _posts(db)}
    assert created == len(keys) == 6
    assert "Ertaga soat" in keys[f"event_reminder:{tomorrow.id}:day"].text or "ertaga soat" in (
        keys[f"event_reminder:{tomorrow.id}:day"].text
    )
    assert "«Alkimyogar»" in keys[f"event_reminder:{tomorrow.id}:day"].text
    assert f"event_reminder:{today.id}:today" in keys
    assert "2 kun qoldi" in keys[f"nudge:{book.id}:end"].text or "«Alkimyogar»" in keys[f"nudge:{book.id}:end"].text
    assert f"nudge:{long_book.id}:middle" in keys
    assert "invite:2026-W45" in keys
    leaders = keys["monthly:2026-10"].text
    assert "Oktabr oyining eng faol kitobxonlari" in leaders and "Laylo K. — 50 ball" in leaders

    # Running again changes nothing; a switched-off channel posts nothing at all.
    assert await channel.scheduled_posts(db, now=now) == 0
    await update_setting(db, key="channel.enabled", value=False, actor_id=admin.id)
    assert await channel.scheduled_posts(db, now=now + timedelta(days=7)) == 0


async def test_quote_and_results_posts(db: AsyncSession) -> None:
    admin = await _admin(db)
    await _switch_on(db, admin)
    today = datetime.now(local_tz()).date()
    quote = BookQuote(text="Kitob — aql chirog'i.", author="Navoiy", status=QuoteStatus.SCHEDULED, scheduled_date=today)
    db.add(quote)
    await db.commit()
    await announcements.quote_of_day(db, now=_local(today, 10))
    await db.commit()
    post = await db.scalar(select(ChannelPost).where(ChannelPost.kind == ChannelPostKind.QUOTE))
    assert "<i>«Kitob — aql chirog'i.»</i>" in post.text and "— Navoiy" in post.text

    from app.models import Test

    winner = await create_user(db, first_name="Jasur", last_name="Olimov")
    test = Test(
        title="Navoiy hayoti",
        starts_at=datetime.now(UTC) - timedelta(days=1),
        ends_at=datetime.now(UTC),
        duration_minutes=10,
        max_score=20,
        passing_score=10,
    )
    db.add(test)
    await db.flush()
    await channel.test_winners(db, test, [{"place": 1, "user_id": winner.id, "score": 19}])
    await db.commit()
    results = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == f"test:{test.id}"))
    assert "🥇 Jasur O. — 19/20 ball" in results.text


class ChannelTelegram(FakeTelegramSession):
    def __init__(self, fail: str | None = None) -> None:
        super().__init__()
        self.fail = fail

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if self.fail and isinstance(method, (SendMessage, SendPhoto)):
            self.requests.append(method)
            raise TelegramBadRequest(method=method, message=self.fail)
        if isinstance(getattr(method, "chat_id", None), str):  # a channel address such as "@name"
            self.requests.append(method)
            return Message(message_id=len(self.requests), date=datetime.now(UTC), chat=Chat(id=-1001, type="channel"))
        return await super().make_request(bot, method, timeout)


async def _make_due(db: AsyncSession, *keys: str) -> None:
    """Automatic posts wait for the daytime (and for the admins' review); in tests they are due now."""
    await db.execute(update(ChannelPost).where(ChannelPost.dedup_key.in_(keys)).values(scheduled_at=datetime.now(UTC)))
    await db.commit()


def _bot(session: FakeTelegramSession) -> Bot:
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def test_sender_publishes_and_reports_problems(db: AsyncSession) -> None:
    admin = await _admin(db)
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")
    admin_id = admin.id
    await _switch_on(db, admin)
    db.add(ChannelSticker(file_id="sticker-1", file_unique_id="s1", emoji="📚"))
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="JPEG")
    await get_storage().put("covers/test.jpg", buffer.getvalue(), "image/jpeg")
    await db.commit()
    await channel.queue(
        db, kind=ChannelPostKind.INVITE, text="<b>Qo'shiling!</b>", dedup_key="a", photo_key="covers/test.jpg"
    )
    await channel.queue(
        db,
        kind=ChannelPostKind.MANUAL,
        text="Kecha",
        automatic=False,
        scheduled_at=datetime.now(UTC) + timedelta(hours=1),
    )
    await db.commit()
    await _make_due(db, "a")

    telegram = ChannelTelegram()
    assert await send_channel_posts(get_session_factory(), _bot(telegram)) == 1
    photo = next(r for r in telegram.requests if isinstance(r, SendPhoto))
    assert photo.chat_id == "@FJSTIMutolaaxona" and photo.caption == "<b>Qo'shiling!</b>"
    assert photo.reply_markup.inline_keyboard[0][0].url == "https://t.me/kitobxon_test_bot?start=channel"
    assert any(isinstance(r, SendSticker) and r.sticker == "sticker-1" for r in telegram.requests)
    sent = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == "a"))
    await db.refresh(sent)
    assert sent.status == ChannelPostStatus.SENT and sent.message_id

    # The bot is not an admin of the channel: the post fails and the super admin hears about it.
    await channel.queue(db, kind=ChannelPostKind.INVITE, text="Yana", dedup_key="b")
    await db.commit()
    await _make_due(db, "b")
    broken = ChannelTelegram(fail="Bad Request: need administrator rights in the channel chat")
    assert await send_channel_posts(get_session_factory(), _bot(broken)) == 0
    failed = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == "b"))
    await db.refresh(failed)
    assert failed.status == ChannelPostStatus.FAILED and "administrator rights" in failed.last_error
    warning = await db.scalar(
        select(Notification.text).where(Notification.user_id == admin_id, Notification.type == NotificationType.SYSTEM)
    )
    assert "Kanalga (@FJSTIMutolaaxona) post joylab bo'lmadi" in warning


async def test_admin_channel_page(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    member = await create_user(db)
    await db.commit()
    headers = admin_headers(admin)
    assert (await client.get("/api/v1/admin/channel", headers=member_headers(member))).status_code == 403

    overview = (await client.get("/api/v1/admin/channel", headers=headers)).json()
    assert overview["enabled"] is False and overview["chat_id"] == "@FJSTIMutolaaxona"
    assert overview["link"] == "https://t.me/FJSTIMutolaaxona"

    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buffer, format="PNG")
    created = await client.post(
        "/api/v1/admin/channel/posts",
        data={"text": "Shanba kuni <b>soat 15:00</b> da uchrashamiz!", "with_button": "false"},
        files={"photo": ("poster.png", buffer.getvalue(), "image/png")},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    post = created.json()
    assert post["manual"] and post["has_photo"] and post["text"].startswith("Shanba kuni &lt;b&gt;")
    empty = await client.post("/api/v1/admin/channel/posts", data={"text": "  "}, headers=headers)
    assert empty.status_code == 400

    later = await client.post(
        "/api/v1/admin/channel/posts",
        data={"text": "Ertaga", "scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers=headers,
    )
    cancelled = await client.post(f"/api/v1/admin/channel/posts/{later.json()['id']}/cancel", headers=headers)
    assert cancelled.json()["status"] == "CANCELLED"
    assert (await client.post("/api/v1/admin/channel/test", headers=headers)).status_code == 200

    sticker = ChannelSticker(file_id="x", file_unique_id="ux", emoji="🔥")
    db.add(sticker)
    await db.commit()
    overview = (await client.get("/api/v1/admin/channel", headers=headers)).json()
    assert len(overview["posts"]) == 3 and overview["stickers"][0]["emoji"] == "🔥"
    deleted = await client.delete(f"/api/v1/admin/channel/stickers/{sticker.id}", headers=headers)
    assert deleted.status_code == 204


async def test_admin_saves_stickers_in_the_bot(db: AsyncSession) -> None:
    await _admin(db, telegram_id=9401)
    await create_user(db, telegram_id=9402)
    await db.commit()

    outsider = BotHarness(9402)
    await outsider.send("/stiker")
    assert "admin" in outsider.last_text().lower()

    harness = BotHarness(9401)
    await harness.send("/stiker")
    assert "Bot va kanal uchun stikerlar" in harness.last_text()

    async def send_sticker(unique: str) -> None:
        sticker = Sticker(
            file_id=f"file-{unique}",
            file_unique_id=unique,
            type="regular",
            width=512,
            height=512,
            is_animated=True,
            is_video=False,
            emoji="📖",
            set_name="BooksPack",
        )
        update = Update(update_id=1, message=harness._message(sticker=sticker))
        await harness.dispatcher.feed_update(harness.bot, update)

    await send_sticker("one")
    assert "Jami stikerlar: 1" in harness.last_text() and "kitob mavzusida" in harness.last_text()
    await send_sticker("one")
    assert "allaqachon saqlangan" in harness.last_text()
    await harness.send("salom")
    assert harness.last_text() == texts.STICKER_ONLY
    await harness.send("/tayyor")
    assert "Tayyor" in harness.last_text()
    saved = list(await db.scalars(select(ChannelSticker)))
    assert len(saved) == 1 and saved[0].is_animated and saved[0].set_name == "BooksPack"
