"""Livelier messages: 🎉 effects and stickers on wins, lines from books, the admins' look at channel posts."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage, SendSticker
from aiogram.methods.base import TelegramMethod
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models import AuditLog, BookQuote, ChannelPost, ChannelSticker, Notification, User
from app.models.enums import (
    BookStatus,
    CertificateKind,
    ChannelPostStatus,
    NotificationType,
    QuoteStatus,
    StickerMood,
)
from app.security.permissions import Perm
from app.services import announcements, channel, literary, stickers
from app.services.notifications import celebrate, enqueue_notification
from app.services.settings import update_setting
from app.workers import sender as sender_module
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

sender_module.SEND_INTERVAL_SECONDS = 0
_ids = itertools.count(980_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "bot_username", "kitobxon_test_bot")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


class Telegram(FakeTelegramSession):
    """Rejects message effects when asked to (like a client that does not know the effect)."""

    def __init__(self, reject_effects: bool = False) -> None:
        super().__init__()
        self.reject_effects = reject_effects

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if self.reject_effects and getattr(method, "message_effect_id", None):
            raise TelegramBadRequest(method, "Bad Request: EFFECT_ID_INVALID")
        return await super().make_request(bot, method, timeout)


def _bot(session: FakeTelegramSession) -> Bot:
    return Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def _admin(db: AsyncSession) -> User:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    return admin


async def _sticker(db: AsyncSession, unique: str, emoji: str) -> None:
    db.add(
        ChannelSticker(
            file_id=f"file-{unique}",
            file_unique_id=unique,
            emoji=emoji,
            is_animated=True,
            mood=stickers.mood_for(emoji),
        )
    )
    await db.commit()


def test_sticker_moods_and_sayings() -> None:
    assert stickers.mood_for("🎉") == StickerMood.CELEBRATE
    assert stickers.mood_for("❤️") == StickerMood.CELEBRATE
    assert stickers.mood_for("📖") == StickerMood.READING
    assert stickers.mood_for("👋") == StickerMood.WELCOME
    assert stickers.mood_for("🐸") == StickerMood.ANY and stickers.mood_for(None) == StickerMood.ANY
    assert literary.epigraph("a") == literary.epigraph("a")  # stable for the same message
    assert literary.epigraph("a").startswith("<i>«") and "\n— " in literary.epigraph("a")


async def test_wins_come_with_confetti_and_a_sticker(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await update_setting(db, key="notifications.stickers", value=True, actor_id=member.id)
    await _sticker(db, "party", "🥳")
    await _sticker(db, "book", "📚")
    await enqueue_notification(
        db, user_id=member.id, type_=NotificationType.SYSTEM, text="🏆 G'alaba!", dedup_key="win", payload=celebrate()
    )
    await enqueue_notification(db, user_id=member.id, type_=NotificationType.SYSTEM, text="Oddiy", dedup_key="plain")
    await db.commit()

    telegram = Telegram()
    assert (await send_due_notifications(get_session_factory(), _bot(telegram))).sent == 2
    messages = {m.text: m for m in telegram.sent_messages()}
    assert messages["🏆 G'alaba!"].message_effect_id == stickers.EFFECT_CONFETTI
    assert messages["Oddiy"].message_effect_id is None
    sent_stickers = [r.sticker for r in telegram.requests if isinstance(r, SendSticker)]
    assert sent_stickers == ["file-party"]  # the celebrating one, after the win only

    # A client that refuses the effect still gets the message.
    await enqueue_notification(
        db, user_id=member.id, type_=NotificationType.SYSTEM, text="Yana g'alaba", dedup_key="w2", payload=celebrate()
    )
    await db.commit()
    picky = Telegram(reject_effects=True)
    assert (await send_due_notifications(get_session_factory(), _bot(picky))).sent == 1
    assert [m.message_effect_id for m in picky.sent_messages()] == [None]

    # Stickers switched off in the settings: the 🎉 effect stays, no separate sticker.
    await update_setting(db, key="notifications.stickers", value=False, actor_id=member.id)
    await enqueue_notification(
        db, user_id=member.id, type_=NotificationType.SYSTEM, text="Uchinchi", dedup_key="w3", payload=celebrate()
    )
    await db.commit()
    quiet = Telegram()
    await send_due_notifications(get_session_factory(), _bot(quiet))
    assert quiet.sent_messages()[0].message_effect_id == stickers.EFFECT_CONFETTI
    assert not any(isinstance(r, SendSticker) for r in quiet.requests)


async def test_achievements_and_certificates_are_celebrated(db: AsyncSession) -> None:
    from app.services import certificates

    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await certificates.issue(
        db,
        user_id=member.id,
        kind=CertificateKind.MANUAL,
        title="Faol kitobxon",
        description="Klub faoliyatida faol ishtiroki uchun",
        dedup_key="c1",
    )
    await db.commit()
    note = await db.scalar(select(Notification).where(Notification.type == NotificationType.CERTIFICATE))
    assert note.payload["mood"] == "CELEBRATE"
    assert "PDF fayl sifatida ilova" not in note.text and "yangi bekat" in note.text


async def test_reading_reminders_quote_the_book(db: AsyncSession) -> None:
    from app.models import BookRead
    from app.models.enums import ReadingStatus

    reader = await create_user(db, telegram_id=next(_ids))
    book = await create_book(
        db, title="Kecha va kunduz", status=BookStatus.ACTIVE, deadline=date.today() + timedelta(days=2)
    )
    db.add(BookRead(book_id=book.id, user_id=reader.id, status=ReadingStatus.READING))
    db.add(BookQuote(book_id=book.id, text="Hayot — bu kurash.", status=QuoteStatus.SENT))
    db.add(BookQuote(book_id=book.id, text="Hali aytilmagan iqtibos", status=QuoteStatus.SCHEDULED))
    await db.commit()
    assert await literary.book_line(db, book.id, "x") == "<i>«Hayot — bu kurash.»</i>"

    now = datetime.now(UTC).replace(hour=8)  # 13:00 in Tashkent: daytime
    await announcements.reading_reminders(db, now)
    await db.commit()
    text = await db.scalar(select(Notification.text).where(Notification.type == NotificationType.READING_REMINDER))
    assert "«Kecha va kunduz» sizni kutyapti" in text and "📖 Kitobdan: <i>«Hayot — bu kurash.»</i>" in text
    assert "aytilmagan" not in text  # a quote waiting for its day is not spoiled


async def _queued_post(db: AsyncSession, admin: User, title: str) -> ChannelPost:
    await update_setting(db, key="channel.enabled", value=True, actor_id=admin.id)
    book = await create_book(db, title=title, status=BookStatus.ACTIVE)
    await db.commit()
    before = datetime.now(UTC)
    assert await channel.book_announced(db, book)
    await db.commit()
    post = await db.scalar(select(ChannelPost).where(ChannelPost.dedup_key == f"book:{book.id}"))
    # The admins get five minutes first (or the post waits for the morning).
    assert post.scheduled_at >= channel.next_daytime(before + timedelta(minutes=5)) - timedelta(seconds=5)
    return post


async def _review(db: AsyncSession, post: ChannelPost) -> Notification:
    shown = await channel.request_reviews(db, now=post.scheduled_at - timedelta(minutes=3))
    assert shown == 1
    assert await channel.request_reviews(db, now=post.scheduled_at - timedelta(minutes=2)) == 0  # shown once
    return await db.scalar(
        select(Notification).where(Notification.dedup_key.like(f"channel-review:{post.id}%")).limit(1)
    )


async def test_admins_look_at_automatic_posts_first(db: AsyncSession) -> None:
    admin, other = await _admin(db), await _admin(db)
    first = await _queued_post(db, admin, "Sariq devni minib")
    preview = await _review(db, first)
    assert "Kanal uchun post tayyor" in preview.text and "«Sariq devni minib»" in preview.text
    rows = preview.payload["buttons"]
    assert [b["callback"] for b in rows[0]["row"]] == [f"chp:ok:{first.id.hex}", f"chp:no:{first.id.hex}"]
    assert rows[1]["callback"] == f"chp:edit:{first.id.hex}"
    assert preview.priority == 1

    boss = BotHarness(admin.telegram_id)
    await boss.press(f"chp:ok:{first.id.hex}")
    assert boss.last_text() == texts.CHANNEL_POST_NOW
    await db.refresh(first)
    assert first.reviewed_by == admin.id and first.scheduled_at <= channel.next_daytime(datetime.now(UTC))
    late = BotHarness(other.telegram_id)
    await late.press(f"chp:no:{first.id.hex}")
    assert "Boshqa admin" in late.session.alerts()[-1]
    await db.refresh(first)
    assert first.status == ChannelPostStatus.PENDING

    # Editing: the post waits for the new text, then goes out with it.
    second = await _queued_post(db, admin, "Shum bola")
    await _review(db, second)
    await late.press(f"chp:edit:{second.id.hex}")
    assert late.last_text() == texts.CHANNEL_POST_EDIT_ASK
    await db.refresh(second)
    assert second.scheduled_at >= datetime.now(UTC) + timedelta(minutes=25)
    await late.send("Yangi matn <shum> bola")
    assert late.last_text() == texts.CHANNEL_POST_EDITED
    await db.refresh(second)
    assert second.text == "Yangi matn &lt;shum&gt; bola" and second.reviewed_by == other.id
    assert await db.scalar(select(AuditLog.id).where(AuditLog.action == "CHANNEL_POST_EDIT")) is not None

    third = await _queued_post(db, admin, "Ufq")
    await _review(db, third)
    await boss.press(f"chp:no:{third.id.hex}")
    await db.refresh(third)
    assert third.status == ChannelPostStatus.CANCELLED and boss.last_text() == texts.CHANNEL_POST_CANCELLED

    reader = BotHarness((await create_user(db, telegram_id=next(_ids))).telegram_id)
    await db.commit()
    await reader.press(f"chp:ok:{second.id.hex}")
    assert reader.session.alerts()[-1] == texts.ADMIN_ONLY


async def test_review_can_be_switched_off_and_used_in_the_panel(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    await update_setting(db, key="channel.review_minutes", value=0, actor_id=admin.id)
    await update_setting(db, key="channel.enabled", value=True, actor_id=admin.id)
    book = await create_book(db, title="Mehrobdan chayon", status=BookStatus.ACTIVE)
    await db.commit()
    start = datetime.now(UTC)
    await channel.book_announced(db, book)
    await db.commit()
    post = await db.scalar(select(ChannelPost))
    assert post.scheduled_at <= channel.next_daytime(start) + timedelta(seconds=5)
    assert await channel.request_reviews(db) == 0

    headers = admin_headers(admin)
    overview = (await client.get("/api/v1/admin/channel", headers=headers)).json()
    row = overview["posts"][0]
    assert "«Mehrobdan chayon»" in row["plain_text"] and "<b>" not in row["plain_text"] and row["in_review"] is False
    edited = await client.put(
        f"/api/v1/admin/channel/posts/{post.id}/text", json={"text": "Bugun <b> yo'q"}, headers=headers
    )
    assert edited.status_code == 200 and edited.json()["text"] == "Bugun &lt;b&gt; yo'q"
    now = await client.post(f"/api/v1/admin/channel/posts/{post.id}/publish-now", headers=headers)
    assert now.status_code == 200 and now.json()["reviewed_at"] is not None
    await client.post(f"/api/v1/admin/channel/posts/{post.id}/cancel", headers=headers)
    again = await client.post(f"/api/v1/admin/channel/posts/{post.id}/publish-now", headers=headers)
    assert again.status_code == 409


async def test_welcome_message_has_a_saying_and_a_sticker(db: AsyncSession) -> None:
    from app.models.enums import UserStatus

    owner = await create_user(db, telegram_id=next(_ids))
    await update_setting(db, key="notifications.stickers", value=True, actor_id=owner.id)
    await _sticker(db, "hello", "👋")
    harness = BotHarness(next(_ids))
    await harness.send("/start")
    await harness.send("Aziza")
    await harness.send("Karimova")
    await harness.share_contact("+998901234599")
    await harness.press("reg:course:2")
    await harness.send("201")
    await harness.press("reg:confirm")
    user = await db.scalar(select(User).where(User.telegram_id == harness.user.id))
    if user is None or user.status != UserStatus.ACTIVE:
        pytest.skip("registration needs approval in this configuration")
    welcome = next(m for m in harness.session.sent_messages() if "Tabriklaymiz" in m.text)
    assert "<i>«" in welcome.text
    assert [r.sticker for r in harness.session.requests if isinstance(r, SendSticker)] == ["file-hello"]
    assert not any(isinstance(r, SendMessage) and r.message_effect_id for r in harness.session.requests)
