"""«✉️ Adminga yozish»: members write to the club; administrators answer from the bot.

These handlers wait for free text, so their router is registered after the menu sections:
pressing a menu button while writing simply opens that section instead.
"""

from __future__ import annotations

import uuid

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.bot.access import gate, has_permission
from app.bot.filters import ActiveMember, CanWriteToAdmins
from app.bot.states import SupportCompose, SupportReply
from app.core.errors import AppError
from app.models import User
from app.models.enums import SupportTicketStatus, UserStatus
from app.security.permissions import Perm
from app.services import support as support_service

router = Router(name="support")
# Members write to the club even when their account is blocked or waits for approval.
router.message.filter(CanWriteToAdmins())
router.callback_query.filter(CanWriteToAdmins())


@router.callback_query(F.data.in_({"sup:new", "sup:new:pay"}))
async def start_message(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    payment = callback.data == "sup:new:pay"  # a payment question also goes to the payments chat
    active = member.status == UserStatus.ACTIVE
    if active and not payment and await gate(callback, db, member, "support"):
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


async def _may_answer(db: AsyncSession, member: User | None, payment: bool) -> bool:
    """Money questions: the super admins and those given «💳 To'lov savollari» (PAYMENT_SUPPORT);
    the others: «Murojaatlar» (SUPPORT_MANAGE)."""
    return await has_permission(db, member, Perm.PAYMENT_SUPPORT if payment else Perm.SUPPORT_MANAGE)


@router.callback_query(F.data.startswith("sup:ans:") | F.data.startswith("sup:pay:"), ActiveMember())
async def start_reply(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    """«✍️ Javob yozish». In the bot: the next message is the answer. In the payments channel or group:
    the admin answers right there with a «Reply», and everybody sees who took the question."""
    payment = (callback.data or "").startswith("sup:pay:")
    if not await _may_answer(db, member, payment):
        await callback.answer(
            texts.SUPPORT_PAYMENT_NO_RIGHT if payment else texts.SUPPORT_NO_PERMISSION, show_alert=True
        )
        return
    try:
        ticket_id = uuid.UUID((callback.data or "")[len("sup:ans:") :])
    except ValueError:
        await callback.answer()
        return
    await support_service.get_ticket(db, ticket_id)
    message = callback.message if isinstance(callback.message, Message) else None
    if message is not None and message.chat.type == "private":
        await state.set_state(SupportReply.waiting)
        await state.update_data(ticket_id=str(ticket_id), payment=payment)
        await callback.answer()
        await message.answer(texts.SUPPORT_REPLY_ASK)
        return
    if message is not None:  # the payments channel or group: answer right here
        await support_service.claim(
            db, actor_id=member.id, ticket_id=ticket_id, chat_id=message.chat.id, message_id=message.message_id
        )
    await callback.answer(texts.SUPPORT_REPLY_CHANNEL_HINT, show_alert=True)


@router.message(StateFilter(SupportReply.waiting), F.text, ~F.text.startswith("/"), ActiveMember())
async def admin_reply(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    data = await state.get_data()
    payment = bool(data.get("payment"))
    if not await _may_answer(db, member, payment):
        await state.clear()
        await message.answer(texts.SUPPORT_PAYMENT_NO_RIGHT if payment else texts.SUPPORT_NO_PERMISSION)
        return
    await support_service.admin_reply(
        db, actor_id=member.id, ticket_id=uuid.UUID(data["ticket_id"]), text=message.text or "", payment=payment
    )
    await state.clear()
    await message.answer(texts.SUPPORT_REPLY_SENT)


@router.callback_query(F.data.startswith("sup:full:"), ActiveMember())
async def full_thread(callback: CallbackQuery, db: AsyncSession, member: User, bot: Bot) -> None:
    """«📄 Batafsil»: the whole conversation (every message, whole, with the photos) — right where pressed."""
    rest = (callback.data or "").removeprefix("sup:full:")
    payment = rest.startswith("p:")
    if not await _may_answer(db, member, payment):
        await callback.answer(
            texts.SUPPORT_PAYMENT_NO_RIGHT if payment else texts.SUPPORT_NO_PERMISSION, show_alert=True
        )
        return
    try:
        ticket_id = uuid.UUID(rest.removeprefix("p:"))
        chunks, photos = await support_service.thread_text(db, ticket_id)
    except (ValueError, AppError):
        await callback.answer(texts.SUPPORT_TICKET_GONE, show_alert=True)
        return
    await callback.answer()
    message = callback.message if isinstance(callback.message, Message) else None
    chat_id = message.chat.id if message else callback.from_user.id
    reply_to = message.message_id if message and message.chat.type != "private" else None
    ticket = await support_service.get_ticket(db, ticket_id)
    for index, chunk in enumerate(chunks):
        sent = await bot.send_message(
            chat_id, chunk, reply_to_message_id=reply_to if index == 0 else None, disable_web_page_preview=True
        )
        if reply_to is not None:  # a «Reply» to the conversation in the channel reaches the member too
            from app.services import payments_chat

            await payments_chat.remember(db, sent, ("ticket", ticket_id, ticket.user_id))
    for file_id in photos[-5:]:
        await bot.send_photo(chat_id, file_id, caption=texts.SUPPORT_THREAD_PHOTO)


@router.callback_query(F.data.startswith("sup:close:"), ActiveMember())
async def close_ticket(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    """«🔒 Yopish»: answered elsewhere or needs no answer — every copy shows it closed."""
    try:
        ticket_id = uuid.UUID((callback.data or "").removeprefix("sup:close:"))
    except ValueError:
        await callback.answer()
        return
    payment = await support_service._is_payment(db, ticket_id)
    if not await _may_answer(db, member, payment):
        await callback.answer(texts.SUPPORT_NO_PERMISSION, show_alert=True)
        return
    await support_service.set_status(db, actor_id=member.id, ticket_id=ticket_id, status=SupportTicketStatus.CLOSED)
    await callback.answer(texts.SUPPORT_CLOSED)
