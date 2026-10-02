"""«✉️ Adminga yozish»: members write to the club; administrators answer from the bot.

These handlers wait for free text, so their router is registered after the menu sections:
pressing a menu button while writing simply opens that section instead.
"""

from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.access import has_permission
from app.bot.filters import ActiveMember
from app.bot.states import SupportCompose, SupportReply
from app.models import User
from app.security.permissions import Perm
from app.services import support as support_service

router = Router(name="support")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


@router.callback_query(F.data == "sup:new")
async def start_message(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportCompose.waiting)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.SUPPORT_ASK)


@router.message(StateFilter(SupportCompose.waiting), F.text, ~F.text.startswith("/"))
@router.message(StateFilter(SupportCompose.waiting), F.photo)
async def member_message(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    photo = message.photo[-1].file_id if message.photo else None
    await support_service.member_message(db, user=member, text=message.text or message.caption, photo_file_id=photo)
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
    await state.set_state(SupportReply.waiting)
    await state.update_data(ticket_id=str(ticket_id))
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.SUPPORT_REPLY_ASK)


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
