"""Leaving the club and coming back: the bot was blocked, /start after leaving, restore requests."""

from __future__ import annotations

import html
import logging
import uuid

from aiogram import F, Router
from aiogram.filters import KICKED, ChatMemberUpdatedFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.models import User
from app.models.enums import UserStatus
from app.security.permissions import Perm
from app.services import membership

logger = logging.getLogger(__name__)
router = Router(name="membership")


@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def bot_blocked(update: ChatMemberUpdated, db: AsyncSession) -> None:
    """The member blocked the bot: they leave the club (the data waits 30 days for a return)."""
    if update.chat.type != "private":
        return
    if await membership.on_bot_blocked(db, update.chat.id):
        await db.commit()


async def offer_return(message: Message, db: AsyncSession, member: User) -> None:
    """/start from a member who left: restore by themselves, ask the admins, or start anew."""
    option = membership.restore_option(member)
    days = (membership._now() - member.left_at).days if member.left_at else 0
    fresh = InlineKeyboardButton(text=texts.BTN_START_FRESH, callback_data="mem:fresh")
    if option == "self":
        await message.answer(
            texts.LEFT_BACK_SELF.format(name=html.escape(member.first_name), days=days),
            reply_markup=keyboards.inline(
                [InlineKeyboardButton(text=texts.BTN_RESTORE, callback_data="mem:restore")], [fresh]
            ),
        )
    elif option == "request":
        if member.restore_requested_at is not None:
            await message.answer(texts.LEFT_REQUEST_WAITING, reply_markup=keyboards.inline([fresh]))
            return
        await message.answer(
            texts.LEFT_BACK_REQUEST.format(days=days),
            reply_markup=keyboards.inline(
                [InlineKeyboardButton(text=texts.BTN_REQUEST_RESTORE, callback_data="mem:request")], [fresh]
            ),
        )
    else:
        await message.answer(texts.FRESH_CONFIRM, reply_markup=keyboards.inline([fresh]))


def _left(member: User | None) -> bool:
    return member is not None and member.status == UserStatus.LEFT


@router.callback_query(F.data == "mem:restore")
async def restore_self(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _left(member) or not isinstance(callback.message, Message):
        return
    assert member is not None
    if membership.restore_option(member) != "self":
        await offer_return(callback.message, db, member)
        return
    await membership.restore(db, member)
    await callback.message.answer(
        texts.RESTORED.format(name=html.escape(member.first_name)), reply_markup=await access.menu(db, member)
    )


@router.callback_query(F.data == "mem:request")
async def restore_request(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if not _left(member) or not isinstance(callback.message, Message):
        return
    assert member is not None
    try:
        await membership.request_restore(db, member)
    except Exception as exc:
        await callback.message.answer(getattr(exc, "message", texts.FILE_FAILED))
        return
    await callback.message.answer(texts.LEFT_REQUEST_SENT)


@router.callback_query(F.data == "mem:fresh")
async def fresh_confirm(callback: CallbackQuery, member: User | None) -> None:
    await callback.answer()
    if _left(member) and isinstance(callback.message, Message):
        await callback.message.answer(
            texts.FRESH_CONFIRM,
            reply_markup=keyboards.inline(
                [InlineKeyboardButton(text=texts.BTN_FRESH_YES, callback_data="mem:fresh:yes")]
            ),
        )


@router.callback_query(F.data == "mem:fresh:yes")
async def fresh_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    from app.bot.handlers.registration import begin_registration

    await callback.answer()
    if not _left(member) or not isinstance(callback.message, Message):
        return
    assert member is not None
    await membership.erase(db, member, actor_id=None, reason="a'zo yangidan boshladi")
    await begin_registration(callback.message, state, db)


# ---------------------------------------------------------------------------- leaving by oneself


@router.callback_query(F.data == "mem:leave")
async def leave_confirm(callback: CallbackQuery, member: User | None) -> None:
    await callback.answer()
    if member is not None and member.status == UserStatus.ACTIVE and isinstance(callback.message, Message):
        await callback.message.answer(
            texts.LEAVE_CONFIRM,
            reply_markup=keyboards.inline(
                [InlineKeyboardButton(text=texts.BTN_LEAVE_YES, callback_data="mem:leave:yes")]
            ),
        )


@router.callback_query(F.data == "mem:leave:yes")
async def leave(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if member is None or member.status != UserStatus.ACTIVE or not isinstance(callback.message, Message):
        return
    if await access.is_admin(db, member):
        await callback.message.answer(texts.LEAVE_STAFF)
        return
    await state.clear()
    await membership.leave(db, member, reason="SELF")
    await db.commit()
    await callback.message.answer(texts.LEFT_DONE, reply_markup=keyboards.remove())


# ---------------------------------------------------------------------------- admins decide


async def _target(callback: CallbackQuery, db: AsyncSession, member: User | None, prefix: str) -> User | None:
    if not await access.has_permission(db, member, Perm.USER_MANAGE):
        await callback.answer(texts.RESTORE_ADMIN_ONLY, show_alert=True)
        return None
    try:
        user = await db.get(User, uuid.UUID(hex=(callback.data or "").removeprefix(prefix)))
    except ValueError:
        user = None
    if user is None or user.status != UserStatus.LEFT or user.erased_at is not None:
        await callback.answer(texts.RESTORE_DONE_ALREADY, show_alert=True)
        return None
    return user


@router.callback_query(F.data.startswith("mem:ok:"))
async def approve_restore(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    user = await _target(callback, db, member, "mem:ok:")
    if user is None:
        return
    assert member is not None
    name = f"{user.last_name} {user.first_name}"
    await membership.restore(db, user, actor_id=member.id)
    await callback.answer("✅")
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.RESTORE_APPROVED_ADMIN.format(name=html.escape(name)))


@router.callback_query(F.data.startswith("mem:no:"))
async def decline_restore(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    user = await _target(callback, db, member, "mem:no:")
    if user is None:
        return
    assert member is not None
    telegram_id = user.telegram_id
    await membership.decline_restore(db, user, actor_id=member.id)
    await callback.answer("❌")
    if callback.bot is not None:
        try:  # the account is erased now, so the message goes straight through the bot
            await callback.bot.send_message(telegram_id, texts.RESTORE_DECLINED_MEMBER)
        except Exception:
            logger.info("Could not tell a member that their restore request was declined")
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.RESTORE_DECLINED_ADMIN)
