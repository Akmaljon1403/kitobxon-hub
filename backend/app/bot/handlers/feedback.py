"""⭐ Event feedback: the stars under the bot's question, then an optional comment."""

from __future__ import annotations

import uuid

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.bot.filters import ActiveMember
from app.bot.states import FeedbackComment
from app.core.errors import AppError
from app.models import User
from app.services import feedback as feedback_service

router = Router(name="feedback")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


@router.callback_query(F.data.regexp(r"^fb:[0-9a-f]{32}:[1-5]$"))
async def rate(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    _, event_hex, rating = (callback.data or "").split(":")
    try:
        await feedback_service.rate(db, user=member, event_id=uuid.UUID(hex=event_hex), rating=int(rating))
    except AppError as exc:
        await callback.answer(exc.message or texts.FEEDBACK_NOT_ALLOWED, show_alert=True)
        return
    await callback.answer(texts.FEEDBACK_THANKS.format(stars="⭐" * int(rating), rating=rating))
    if isinstance(callback.message, Message):
        # Replace the stars with the answer, and offer to write a comment.
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{texts.FEEDBACK_THANKS.format(stars='⭐' * int(rating), rating=rating)}\n"
            f"{texts.FEEDBACK_ASK_COMMENT}",
            reply_markup=keyboards.feedback_comment(event_hex),
        )


@router.callback_query(F.data.regexp(r"^fbc:[0-9a-f]{32}$"))
async def ask_comment(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(FeedbackComment.waiting)
    await state.update_data(event_id=(callback.data or "").removeprefix("fbc:"))
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.FEEDBACK_ASK_COMMENT)


@router.message(StateFilter(FeedbackComment.waiting), F.text, ~F.text.startswith("/"))
async def save_comment(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        await feedback_service.add_comment(
            db, user=member, event_id=uuid.UUID(hex=data["event_id"]), comment=message.text or ""
        )
    except (AppError, KeyError, ValueError):
        await message.answer(texts.FEEDBACK_NOT_ALLOWED)
        return
    await message.answer(texts.FEEDBACK_COMMENT_SAVED)
    if await _may_share(db, member, data["event_id"]):
        await message.answer(
            texts.COMMUNITY_EVENT_OFFER, reply_markup=keyboards.community_event_offer(data["event_id"])
        )


async def _may_share(db: AsyncSession, member: User, event_hex: str) -> bool:
    """A good comment (4–5 ⭐) may go to «💬 A'zolar fikrlari» — if the club asks and the member agrees."""
    from sqlalchemy import select

    from app.models import EventFeedback
    from app.services import community, features
    from app.services.settings import get_setting

    if not await get_setting(db, "community.ask_after_event"):
        return False
    if await features.allowed(db, member, "community") != "on":
        return False
    feedback = await db.scalar(
        select(EventFeedback).where(
            EventFeedback.event_id == uuid.UUID(hex=event_hex), EventFeedback.user_id == member.id
        )
    )
    return bool(feedback and feedback.rating >= 4 and len((feedback.comment or "").strip()) >= community.MIN_TEXT)
