"""Admin Panel: the club's premium emoji («✨ Premium emojilar»). They are taught in the bot with /emoji;
here the administrator sees them, removes some and sends a sample to themself."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Annotated

from aiogram.exceptions import TelegramBadRequest
from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.security.permissions import Perm
from app.services import custom_emoji, delivery

router = APIRouter(prefix="/admin/custom-emoji", tags=["admin: premium emoji"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))]
SAMPLE = "Assalomu alaykum! Bot xabarlari endi shunday ko'rinadi:"


class EmojiOut(BaseModel):
    emoji: str
    custom_emoji_id: str
    fallback: str
    created_at: datetime


class EmojiListOut(BaseModel):
    items: list[EmojiOut]
    paused: bool  # Telegram refused premium emoji recently: ordinary ones for an hour
    state: str = Field(
        description="What Telegram said last time: unknown, working, refused (the bot owner has no Telegram "
        "Premium and the bot has no Fragment username) or group_refused (refused in a channel or group only)"
    )
    checked_at: datetime | None


class SampleOut(BaseModel):
    sent: bool
    premium_shown: bool


@router.get("", response_model=EmojiListOut, summary="The premium emoji that replace ordinary ones in bot messages")
async def list_emoji(_: Manager, db: DbSession) -> EmojiListOut:
    rows = await custom_emoji.list_all(db)
    return EmojiListOut(
        items=[
            EmojiOut(
                emoji=row.emoji, custom_emoji_id=row.custom_emoji_id, fallback=row.fallback, created_at=row.created_at
            )
            for row in rows
        ],
        paused=custom_emoji.paused(),
        state=str(custom_emoji.status()["state"]),
        checked_at=custom_emoji.status()["at"],
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Remove one (?emoji=❤️) or all of them")
async def delete_emoji(
    _: Manager, db: DbSession, emoji: Annotated[str | None, Query(max_length=16)] = None
) -> Response:
    await custom_emoji.clear(db, emoji)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=SampleOut, summary="The bot sends me a sample with every saved emoji")
async def send_sample(current: Manager, db: DbSession) -> SampleOut:
    """A real check: the sample carries the premium emoji themselves, so Telegram's answer tells whether
    members see them (and the bot starts using them again at once when it does)."""
    rows = await custom_emoji.list_all(db)
    bot = delivery.runtime_bot()
    chat_id = current.user.telegram_id
    if not rows:
        await delivery.explain_failures(bot.send_message(chat_id, f"{SAMPLE}\n\n📚 ❤️ 🎉"))
        return SampleOut(sent=True, premium_shown=False)
    sample = " ".join(
        f'<tg-emoji emoji-id="{html.escape(row.custom_emoji_id)}">{html.escape(row.fallback)}</tg-emoji>'
        for row in rows[:30]
    )
    try:
        await bot.send_message(chat_id, f"{SAMPLE}\n\n{sample}")
    except TelegramBadRequest:
        custom_emoji.report_refusal(chat_id)
        plain = " ".join(row.emoji for row in rows[:30])
        await delivery.explain_failures(bot.send_message(chat_id, f"{SAMPLE}\n\n{plain}"))
        return SampleOut(sent=True, premium_shown=False)
    custom_emoji.resume()
    custom_emoji.report_success(chat_id)
    return SampleOut(sent=True, premium_shown=True)
