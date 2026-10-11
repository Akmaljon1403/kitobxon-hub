"""Last router: anything not handled elsewhere."""

from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.bot import keyboards, texts
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
    if member is not None and member.status == UserStatus.LEFT:
        from app.bot.setup import resolve_bot_username

        username = await resolve_bot_username(message.bot)
        await message.answer(texts.LEFT_RESTRICTED, reply_markup=keyboards.left_member(username))
        return
    limited = member is not None and member.status in _STATUS_TEXT
    await message.answer(_reply_for(member), reply_markup=keyboards.limited_account() if limited else None)


@router.callback_query()
async def any_callback(callback: CallbackQuery, member: User | None) -> None:
    await callback.answer(_reply_for(member) if member is None or member.status != UserStatus.ACTIVE else None)
