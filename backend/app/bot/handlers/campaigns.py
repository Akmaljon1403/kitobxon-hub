"""«📖 Kitob tanlovlari» in the bot: members see the active reading contests, join one and mark its
book read. Each contest is separate — joining or finishing one never touches another."""

from __future__ import annotations

import html
import logging
import uuid

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards
from app.bot.filters import ActiveMember
from app.core.errors import AppError
from app.models import Book, Campaign, User
from app.services import campaigns
from app.services.campaigns import ParticipantState
from app.utils.timezone import format_date

logger = logging.getLogger(__name__)

router = Router(name="campaigns")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


def _card(campaign: Campaign, books: list[Book], state: ParticipantState) -> tuple[str, object]:
    lines = [f"📖 <b>{html.escape(campaign.name)}</b>"]
    if campaign.description:
        lines.append(html.escape(campaign.description))
    if books:
        lines.append("📚 " + ", ".join(html.escape(book.title) for book in books))
    lines.append(f"🗓 {format_date(campaign.starts_at)} — {format_date(campaign.ends_at)}")
    if state.verified:
        lines.append("✅ Siz bu tanlovni yakunlagansiz — tabriklaymiz!")
    elif state.completed:
        lines.append("⏳ «O'qib tugatdim» deb belgilandi — admin tasdiqlagach, ball qo'shiladi.")
    elif state.joined:
        lines.append("👍 Qatnashyapsiz. Kitobni o'qib bo'lgach, «O'qib tugatdim» ni bosing.")
    rows: list[list[InlineKeyboardButton]] = []
    if not state.joined:
        rows.append([InlineKeyboardButton(text="✅ Qatnashaman", callback_data=f"camp:join:{campaign.id}")])
    elif not state.completed:
        rows.append([InlineKeyboardButton(text="📘 O'qib tugatdim", callback_data=f"camp:done:{campaign.id}")])
    return "\n".join(lines), keyboards.inline(*rows)


def _campaign_id(data: str | None) -> uuid.UUID | None:
    try:
        return uuid.UUID((data or "").rsplit(":", 1)[1])
    except (ValueError, IndexError):
        return None


@router.message(Command("tanlov"))
async def list_contests(message: Message, db: AsyncSession, member: User) -> None:
    rows = await campaigns.active_for_member(db, member.id)
    if not rows:
        await message.answer("Hozircha faol kitob tanlovi yo'q. Tez orada e'lon qilinadi 📚")
        return
    await message.answer(f"📖 <b>Kitob tanlovlari</b> — {len(rows)} ta faol:")
    for campaign, books, state in rows:
        text, markup = _card(campaign, books, state)
        await message.answer(text, reply_markup=markup)


async def _refresh(callback: CallbackQuery, db: AsyncSession, member: User, campaign_id: uuid.UUID, toast: str) -> None:
    await callback.answer(toast)
    if not isinstance(callback.message, Message):
        return
    for campaign, books, state in await campaigns.active_for_member(db, member.id):
        if campaign.id == campaign_id:
            text, markup = _card(campaign, books, state)
            try:
                await callback.message.edit_text(text, reply_markup=markup)
            except Exception:  # the message is too old to edit: leave it
                logger.info("Campaign card could not be edited")
            return


@router.callback_query(F.data.startswith("camp:join:"))
async def join(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    campaign_id = _campaign_id(callback.data)
    if campaign_id is None:
        await callback.answer()
        return
    try:
        await campaigns.join(db, user_id=member.id, campaign_id=campaign_id)
    except AppError as exc:
        await callback.answer(exc.message[:190], show_alert=True)
        return
    await _refresh(callback, db, member, campaign_id, "✅ Qatnashyapsiz! Omad!")


@router.callback_query(F.data.startswith("camp:done:"))
async def completed(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    campaign_id = _campaign_id(callback.data)
    if campaign_id is None:
        await callback.answer()
        return
    try:
        await campaigns.mark_completed(db, user_id=member.id, campaign_id=campaign_id)
    except AppError as exc:
        await callback.answer(exc.message[:190], show_alert=True)
        return
    await _refresh(callback, db, member, campaign_id, "📘 Rahmat! Admin tasdiqlagach, ball qo'shiladi.")
