"""Last router: anything not handled elsewhere."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.bot import texts
from app.models import User
from app.models.enums import UserStatus

router = Router(name="fallback")

_STATUS_TEXT = {
    UserStatus.PENDING: texts.ACCOUNT_PENDING,
    UserStatus.BLOCKED: texts.ACCOUNT_BLOCKED,
    UserStatus.INACTIVE: texts.ACCOUNT_INACTIVE,
}


def _reply_for(member: User | None) -> str:
    if member is None:
        return texts.NOT_REGISTERED
    return _STATUS_TEXT.get(member.status, texts.UNKNOWN_MESSAGE)


@router.message()
async def anything(message: Message, member: User | None) -> None:
    await message.answer(_reply_for(member))


@router.callback_query()
async def any_callback(callback: CallbackQuery, member: User | None) -> None:
    await callback.answer(_reply_for(member) if member is None or member.status != UserStatus.ACTIVE else None)
