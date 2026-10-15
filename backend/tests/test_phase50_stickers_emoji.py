"""Round I2: stickers and premium emoji taught by any admin with the right (the one with Telegram
Premium), honest answers when Telegram refuses premium emoji, and refusals kept to the chat that
refused."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage, SendSticker
from aiogram.methods.base import TelegramMethod
from aiogram.types import Message, MessageEntity, Sticker, Update
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.emoji import CustomEmojiMiddleware
from app.models import ChannelSticker
from app.security.permissions import Perm
from app.services import custom_emoji, stickers
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(995_000)


@pytest.fixture(autouse=True)
def _fresh_emoji(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)
    custom_emoji.use({})
    custom_emoji.reset()
    yield
    custom_emoji.use({})
    custom_emoji.reset()


class RefusingSession(FakeTelegramSession):
    """Telegram as it answers a bot whose owner has no Premium: no premium emoji, anywhere."""

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, SendMessage) and "tg-emoji" in (method.text or ""):
            raise TelegramBadRequest(method=method, message="Bad Request: can't use custom emoji")
        return await super().make_request(bot, method, timeout)


def _refusing(harness: BotHarness) -> None:
    harness.session = RefusingSession()
    harness.bot = Bot(token=BOT_TOKEN, session=harness.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def _emoji_message(harness: BotHarness, text: str, entities: list[MessageEntity], caption: bool = False) -> Update:
    fields: dict[str, Any] = (
        {"caption": text, "caption_entities": entities, "photo": None}
        if caption
        else {"text": text, "entities": entities}
    )
    fields = {key: value for key, value in fields.items() if value is not None}
    message = Message(
        message_id=next(_ids), date=datetime.now(UTC), chat=harness.chat, from_user=harness.user, **fields
    )
    return Update(update_id=next(_ids), message=message)


def _sticker_update(harness: BotHarness, unique: str, emoji: str = "🎉") -> Update:
    sticker = Sticker(
        file_id=f"file-{unique}",
        file_unique_id=unique,
        type="regular",
        width=512,
        height=512,
        is_animated=True,
        is_video=False,
        emoji=emoji,
        set_name="PremiumPack",
    )
    message = Message(
        message_id=next(_ids), date=datetime.now(UTC), chat=harness.chat, from_user=harness.user, sticker=sticker
    )
    return Update(update_id=next(_ids), message=message)


async def _admin(db: AsyncSession, role: str) -> Any:
    user = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, user, role)
    return user


async def test_premium_admin_saves_emoji_and_learns_why_telegram_refuses(db: AsyncSession) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    harness = BotHarness(admin.telegram_id)
    _refusing(harness)

    await harness.send("/emoji")
    assert "Premium emojilar" in harness.last_text() and "hali tekshirilmagan" in harness.last_text()
    entity = MessageEntity(type="custom_emoji", offset=4, length=2, custom_emoji_id="5368324170671202286")
    await harness.dispatcher.feed_update(harness.bot, _emoji_message(harness, "📚 = 📖", [entity]))

    sent = [message.text for message in harness.session.sent_messages()]
    assert "Saqlandi: 📚 (1 ta)" in sent[-2]  # the confirmation always arrives (no premium emoji in it)
    assert "bot egasida" in sent[-1] and "Transfer Ownership" in sent[-1]  # the real reason and the way out
    assert [(row.emoji, row.custom_emoji_id) for row in await custom_emoji.list_all(db)] == [
        ("📚", "5368324170671202286")
    ]
    assert custom_emoji.status()["state"] == "refused" and custom_emoji.paused()

    await harness.send("/emoji")
    assert "rad etdi" in harness.last_text() and "📚" in harness.last_text()
    markup = harness.session.sent_messages()[-1].reply_markup
    assert [row[0].callback_data for row in markup.inline_keyboard] == ["emj:test", "emj:list", "emj:clear"]

    # The owner bought Premium: the check works and the bot uses premium emoji again at once.
    harness.session.__class__ = FakeTelegramSession
    await harness.press("emj:test")
    assert 'emoji-id="5368324170671202286"' in harness.session.sent_messages()[-2].text
    assert harness.last_text() == texts.EMOJI_STATUS_WORKING
    assert custom_emoji.status()["state"] == "working" and not custom_emoji.paused()


async def test_emoji_in_a_caption_and_stickers_in_both_modes(db: AsyncSession) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    harness = BotHarness(admin.telegram_id)

    await harness.send("/emoji")
    caption = [MessageEntity(type="custom_emoji", offset=0, length=1, custom_emoji_id="777")]
    message = Message(
        message_id=next(_ids),
        date=datetime.now(UTC),
        chat=harness.chat,
        from_user=harness.user,
        caption="⭐",
        caption_entities=caption,
        photo=[{"file_id": "p", "file_unique_id": "pu", "width": 10, "height": 10}],
    )
    await harness.dispatcher.feed_update(harness.bot, Update(update_id=next(_ids), message=message))
    assert any(row.custom_emoji_id == "777" for row in await custom_emoji.list_all(db))

    await harness.dispatcher.feed_update(harness.bot, _sticker_update(harness, "s-1"))  # a sticker in /emoji mode
    assert "stikerlar ro'yxatiga qo'shildi" in harness.last_text()
    await harness.send("/tayyor")

    await harness.send("/stiker")
    entity = [MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="888")]
    await harness.dispatcher.feed_update(harness.bot, _emoji_message(harness, "🔥", entity))  # emoji in /stiker mode
    assert any("premium emojilar ham saqlandi" in m.text for m in harness.session.sent_messages())
    assert any(row.custom_emoji_id == "888" for row in await custom_emoji.list_all(db))
    await harness.dispatcher.feed_update(harness.bot, _sticker_update(harness, "s-2", "📚"))
    assert "Saqlandi (📚 kitob mavzusida)" in harness.last_text()
    assert await db.scalar(select(func.count()).select_from(ChannelSticker)) == 2


async def test_outside_the_modes_the_admin_is_offered_to_save(db: AsyncSession) -> None:
    admin = await _admin(db, "ADMIN")  # an ordinary admin with Premium and the messaging right
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND)
    harness = BotHarness(admin.telegram_id)
    await harness.dispatcher.feed_update(harness.bot, _sticker_update(harness, "s-3", "👋"))
    assert harness.last_text() == texts.DECOR_OFFER_STICKER
    await harness.press("dec:save")
    assert "Stiker saqlandi (👋 salomlashish uchun)" in harness.last_text()
    await harness.press("dec:save")
    assert harness.last_text() == texts.DECOR_EXPIRED

    entity = [MessageEntity(type="custom_emoji", offset=0, length=1, custom_emoji_id="999")]
    await harness.dispatcher.feed_update(harness.bot, _emoji_message(harness, "❤", entity))
    assert harness.last_text() == texts.DECOR_OFFER_EMOJI.format(count=1)
    await harness.press("dec:skip")
    assert harness.last_text() == texts.DECOR_SKIPPED and await custom_emoji.list_all(db) == []


async def test_members_and_admins_without_the_right(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.dispatcher.feed_update(harness.bot, _sticker_update(harness, "s-4"))
    assert texts.DECOR_OFFER_STICKER not in harness.all_text()  # a member's sticker is not offered for saving
    await harness.send("/stiker")
    assert harness.last_text() == texts.ADMIN_ONLY

    viewer = await _admin(db, "ADMIN")  # an admin without the right
    harness = BotHarness(viewer.telegram_id)
    await harness.send("/emoji")
    assert harness.last_text() == texts.DECOR_NO_RIGHT


async def test_a_refusal_in_a_channel_stays_in_that_channel() -> None:
    custom_emoji.use({"✋": ("111", "✋")})
    custom_emoji._loaded_at = float("inf")  # no database reload in this test

    class ChannelRefuses(FakeTelegramSession):
        def __init__(self) -> None:
            super().__init__()
            self.texts: list[tuple[int, str]] = []

        async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
            if isinstance(method, SendMessage):
                self.texts.append((method.chat_id, method.text))
                if method.chat_id < 0 and "tg-emoji" in method.text:
                    raise TelegramBadRequest(method=method, message="Bad Request: custom emoji not allowed")
            return await super().make_request(bot, method, timeout)

    session = ChannelRefuses()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(CustomEmojiMiddleware())
    await bot.send_message(-1001234, "Kanal ✋")
    await bot.send_message(-1001234, "Yana ✋")  # this channel: ordinary emoji straight away
    await bot.send_message(42, "Salom ✋")  # private chats keep premium emoji
    assert session.texts == [
        (-1001234, 'Kanal <tg-emoji emoji-id="111">✋</tg-emoji>'),
        (-1001234, "Kanal ✋"),
        (-1001234, "Yana ✋"),
        (42, 'Salom <tg-emoji emoji-id="111">✋</tg-emoji>'),
    ]
    assert not custom_emoji.paused() and custom_emoji.status()["state"] == "working"


async def test_stickers_follow_congratulations_by_default(db: AsyncSession) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    harness = BotHarness(admin.telegram_id)
    await harness.send("/stiker")
    await harness.dispatcher.feed_update(harness.bot, _sticker_update(harness, "s-5", "🎉"))
    assert await stickers.enabled(db)
    assert await stickers.pick(db, "CELEBRATE") == "file-s-5"


async def test_admin_panel_check_reports_what_telegram_said(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    await custom_emoji.save(db, actor_id=admin.id, pairs=[("📚", "123", "📖")])
    session = RefusingSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)

    result = (await client.post("/api/v1/admin/custom-emoji/test", headers=admin_headers(admin))).json()
    assert result == {"sent": True, "premium_shown": False}
    assert session.sent_messages()[-1].text.endswith("📚")  # the sample still arrives, with ordinary emoji
    listing = (await client.get("/api/v1/admin/custom-emoji", headers=admin_headers(admin))).json()
    assert listing["state"] == "refused" and listing["paused"] is True

    session.__class__ = FakeTelegramSession
    result = (await client.post("/api/v1/admin/custom-emoji/test", headers=admin_headers(admin))).json()
    assert result == {"sent": True, "premium_shown": True}
    listing = (await client.get("/api/v1/admin/custom-emoji", headers=admin_headers(admin))).json()
    assert listing["state"] == "working" and listing["paused"] is False
    assert not any(isinstance(request, SendSticker) for request in session.requests)
