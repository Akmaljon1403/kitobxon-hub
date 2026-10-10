"""«✉️ Adminga yozish»: members write to the club; administrators answer from the bot.

These handlers wait for free text, so their router is registered after the menu sections:
pressing a menu button while writing simply opens that section instead.
"""

from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.access import gate, has_permission
from app.bot.filters import ActiveMember
from app.bot.states import SupportCompose, SupportReply
from app.models import User
from app.security.permissions import Perm
from app.services import support as support_service

router = Router(name="support")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


@router.callback_query(F.data.in_({"sup:new", "sup:new:pay"}))
async def start_message(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    payment = callback.data == "sup:new:pay"  # a payment question also goes to the payments chat
    if not payment and await gate(callback, db, member, "support"):
        return
    await state.set_state(SupportCompose.waiting)
    await state.update_data(topic="payment" if payment else None)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.SUPPORT_ASK_PAYMENT if payment else texts.SUPPORT_ASK)


@router.message(StateFilter(SupportCompose.waiting), F.text, ~F.text.startswith("/"))
@router.message(StateFilter(SupportCompose.waiting), F.photo)
async def member_message(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    photo = message.photo[-1].file_id if message.photo else None
    topic = (await state.get_data()).get("topic")
    await support_service.member_message(
        db, user=member, text=message.text or message.caption, photo_file_id=photo, topic=topic
    )
    await db.commit()
    await state.clear()
    await message.answer(texts.SUPPORT_SENT)


@router.message(StateFilter(SupportCompose.waiting), ~F.text.startswith("/"))
async def member_message_unsupported(message: Message) -> None:
    await message.answer(texts.SUPPORT_ONLY_TEXT)


# ---------------------------------------------------------------------------- administrators


@router.callback_query(F.data.startswith("sup:ans:"))
async def start_reply(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    if not await has_permission(db, member, Perm.SUPPORT_MANAGE):
        await callback.answer(texts.SUPPORT_NO_PERMISSION, show_alert=True)
        return
    try:
        ticket_id = uuid.UUID((callback.data or "").removeprefix("sup:ans:"))
    except ValueError:
        await callback.answer()
        return
    await support_service.get_ticket(db, ticket_id)
    if isinstance(callback.message, Message) and callback.message.chat.type == "private":
        await state.set_state(SupportReply.waiting)
        await state.update_data(ticket_id=str(ticket_id))
        await callback.answer()
        await callback.message.answer(texts.SUPPORT_REPLY_ASK)
        return
    # Pressed in the payments group: the answer is typed in the admin's private chat with the bot.
    assert callback.bot is not None
    private = FSMContext(
        storage=state.storage,
        key=StorageKey(bot_id=callback.bot.id, chat_id=callback.from_user.id, user_id=callback.from_user.id),
    )
    try:
        await callback.bot.send_message(callback.from_user.id, texts.SUPPORT_REPLY_ASK)
    except Exception:
        await callback.answer(texts.CARD_DM_FIRST, show_alert=True)
        return
    await private.set_state(SupportReply.waiting)
    await private.update_data(ticket_id=str(ticket_id))
    await callback.answer("✍️")


@router.message(StateFilter(SupportReply.waiting), F.text, ~F.text.startswith("/"))
async def admin_reply(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    if not await has_permission(db, member, Perm.SUPPORT_MANAGE):
        await state.clear()
        await message.answer(texts.SUPPORT_NO_PERMISSION)
        return
    data = await state.get_data()
    await support_service.admin_reply(
        db, actor_id=member.id, ticket_id=uuid.UUID(data["ticket_id"]), text=message.text or ""
    )
    await state.clear()
    await message.answer(texts.SUPPORT_REPLY_SENT)
