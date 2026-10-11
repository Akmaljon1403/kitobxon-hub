"""Stickers and animated effects that make congratulations feel like congratulations.

Admins save stickers with /stiker in the bot (any sticker, Premium ones included); each one gets a
mood from its emoji, so a celebrating sticker follows a win and a book-reading one follows a
reading reminder. Wins also get Telegram's 🎉 message effect (private chats only).

Stickers (Premium ones included) and message effects work for every bot, unlike premium emoji
*inside the text*, which need Telegram Premium on the bot owner's account (see custom_emoji).
"""

from __future__ import annotations

import logging
import random

from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChannelSticker
from app.models.enums import StickerMood
from app.services.settings import get_setting

logger = logging.getLogger(__name__)

# Telegram's built-in message effects (https://core.telegram.org/bots/api#sendmessage).
EFFECT_CONFETTI = "5046509860389126442"  # 🎉
EFFECTS = {StickerMood.CELEBRATE: EFFECT_CONFETTI}

_MOODS: dict[StickerMood, str] = {
    StickerMood.CELEBRATE: "🎉🥳🏆🥇🥈🥉👏🎊💪🔥🤩😍❤⭐🌟🎁💎✨😎🙌👍🏅🎖💯🚀",
    StickerMood.READING: "📚📖📕📗📘📙📓📔📒🤓🧐✍📝🔖🧠☕🤔💡🖋",
    StickerMood.WELCOME: "👋🤗😊🙂☺🌸🌷💐🤝😉🙋🌹🌼☀",
}


def mood_for(emoji: str | None) -> StickerMood:
    """The mood of a sticker from the emoji Telegram attaches to it."""
    if emoji:
        base = emoji.replace("️", "")
        for mood, symbols in _MOODS.items():
            if any(symbol in base for symbol in symbols if symbol):
                return mood
    return StickerMood.ANY


async def enabled(session: AsyncSession) -> bool:
    return bool(await get_setting(session, "notifications.stickers"))


async def pick(session: AsyncSession, mood: StickerMood | str | None) -> str | None:
    """A random saved sticker of this mood (or any sticker), None when there is none or it is off."""
    if not await enabled(session):
        return None
    wanted = StickerMood(mood) if mood else StickerMood.ANY
    rows = (await session.execute(select(ChannelSticker.mood, ChannelSticker.file_id))).all()
    exact = [file_id for row_mood, file_id in rows if row_mood == wanted]
    neutral = [file_id for row_mood, file_id in rows if row_mood == StickerMood.ANY]
    choices = exact or neutral
    return random.choice(choices) if choices else None  # noqa: S311 - decoration, not security


async def send(session: AsyncSession, message: Message, mood: StickerMood) -> None:
    """Send a fitting sticker after a bot reply; never fails the reply itself."""
    file_id = await pick(session, mood)
    if file_id is None:
        return
    try:
        await message.answer_sticker(file_id)
    except Exception:
        logger.info("A decoration sticker could not be sent")
