"""Admin Panel: the club's premium emoji («✨ Premium emojilar»). They are taught in the bot with /emoji;
here the administrator sees them, removes some and sends a sample to themself."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel

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
    paused: bool  # Telegram refused premium emoji recently (no Fragment username): ordinary ones for an hour


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
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Remove one (?emoji=❤️) or all of them")
async def delete_emoji(
    _: Manager, db: DbSession, emoji: Annotated[str | None, Query(max_length=16)] = None
) -> Response:
    await custom_emoji.clear(db, emoji)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test", response_model=SampleOut, summary="The bot sends me a sample with every saved emoji")
async def send_sample(current: Manager, db: DbSession) -> SampleOut:
    rows = await custom_emoji.list_all(db)
    emoji = " ".join(row.emoji for row in rows) or "📚 ❤️ 🎉"
    bot = delivery.runtime_bot()
    await custom_emoji.refresh_if_stale()
    await delivery.explain_failures(bot.send_message(current.user.telegram_id, f"{SAMPLE}\n\n{emoji}"))
    return SampleOut(sent=True, premium_shown=bool(rows) and not custom_emoji.paused())
