"""«💬 A'zolar fikrlari» in the bot.

* /fikr — a member writes a quote, a thought or a testimonial in three short steps;
* after an event comment — «share it with everybody?»;
* «🖼 Kartochkasini olish» — the card of the member's text;
* ✅ / ⭐ / 🙈 under a new text — the admins with «A'zolar fikrlari» decide right in the chat.
"""

from __future__ import annotations

import html
import uuid

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.bot.filters import ActiveMember
from app.bot.states import CommunityWrite
from app.core.errors import AppError
from app.models import EventFeedback, User
from app.models.enums import ContributionKind, ContributionStatus
from app.security.permissions import Perm
from app.services import community, copies

router = Router(name="community")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


@router.message(Command("fikr"))
async def start(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    if await access.gate(message, db, member, "community"):
        return
    await message.answer(texts.COMMUNITY_START, reply_markup=keyboards.community_start())


@router.callback_query(F.data.in_({"cmw:QUOTE", "cmw:THOUGHT", "cmw:CLUB"}))
async def pick_kind(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    if await access.gate(callback, db, member, "community"):
        return
    kind = (callback.data or "").removeprefix("cmw:")
    await state.set_state(CommunityWrite.text)
    await state.update_data(kind=kind)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            texts.COMMUNITY_ASK_TEXT[kind].format(min=community.MIN_TEXT, max=community.MAX_TEXT)
        )


async def _send(message: Message, state: FSMContext, db: AsyncSession, member: User, source: str | None) -> None:
    data = await state.get_data()
    await state.clear()
    try:
        item = await community.submit(
            db, member, kind=ContributionKind(data["kind"]), text=data.get("text", ""), source=source
        )
    except AppError as exc:
        await message.answer(exc.message)
        return
    box = texts.COMMUNITY_SENT_BOX if item.saved_quote_id else ""
    template = texts.COMMUNITY_SENT_LIVE if item.status == ContributionStatus.APPROVED else texts.COMMUNITY_SENT_PENDING
    await message.answer(template.format(box=box), reply_markup=keyboards.community_sent(item.id.hex))


@router.message(StateFilter(CommunityWrite.text), F.text, ~F.text.startswith("/"))
async def got_text(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    text = (message.text or "").strip()
    if len(text) < community.MIN_TEXT or len(text) > community.MAX_TEXT:
        await message.answer(
            texts.COMMUNITY_ASK_TEXT[(await state.get_data()).get("kind", "THOUGHT")].format(
                min=community.MIN_TEXT, max=community.MAX_TEXT
            )
        )
        return
    await state.update_data(text=text)
    if (await state.get_data()).get("kind") == ContributionKind.QUOTE.value:
        await state.set_state(CommunityWrite.source)
        await message.answer(texts.COMMUNITY_ASK_SOURCE, reply_markup=keyboards.community_skip())
        return
    await _send(message, state, db, member, None)


@router.message(StateFilter(CommunityWrite.text, CommunityWrite.source), ~F.text)
async def text_only(message: Message) -> None:
    await message.answer(texts.COMMUNITY_TEXT_ONLY)


@router.message(StateFilter(CommunityWrite.source), F.text, ~F.text.startswith("/"))
async def got_source(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await _send(message, state, db, member, (message.text or "").strip()[: community.MAX_SOURCE])


@router.callback_query(StateFilter(CommunityWrite.source), F.data == "cmw:skip")
async def skip_source(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await _send(callback.message, state, db, member, None)


@router.callback_query(F.data.regexp(r"^cm:card:[0-9a-f]{32}$"))
async def card(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    try:
        item, user, faculty = await community.visible(db, member, uuid.UUID(hex=(callback.data or "")[8:]))
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("🖼 …")
    image = await community.card_png(db, item, user, faculty)
    if isinstance(callback.message, Message):
        await callback.message.answer_photo(
            BufferedInputFile(image, filename=community.card_filename(item)), caption=texts.COMMUNITY_CARD_CAPTION
        )


# ---------------------------------------------------------------------------- after an event comment


@router.callback_query(F.data.regexp(r"^cmfb:([0-9a-f]{32}|no)$"))
async def share_event_comment(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    value = (callback.data or "").removeprefix("cmfb:")
    if value == "no":
        await callback.answer(texts.COMMUNITY_EVENT_NO)
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
        return
    event_id = uuid.UUID(hex=value)
    comment = await db.scalar(
        select(EventFeedback.comment).where(EventFeedback.event_id == event_id, EventFeedback.user_id == member.id)
    )
    try:
        item = await community.submit(
            db, member, kind=ContributionKind.EVENT, text=comment or "", event_id=event_id, save_to_box=False
        )
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await callback.answer("✅")
    if isinstance(callback.message, Message):
        template = (
            texts.COMMUNITY_SENT_LIVE if item.status == ContributionStatus.APPROVED else texts.COMMUNITY_SENT_PENDING
        )
        await callback.message.edit_text(template.format(box=""), reply_markup=keyboards.community_sent(item.id.hex))


# ---------------------------------------------------------------------------- the admins decide in the chat


@router.callback_query(F.data.regexp(r"^cm:(ok|star|hide):[0-9a-f]{32}$"))
async def decide(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    if not await access.has_permission(db, member, Perm.COMMUNITY_MANAGE):
        await callback.answer(texts.COMMUNITY_NO_RIGHT, show_alert=True)
        return
    _, verb, value = (callback.data or "").split(":")
    action = {"ok": "approve", "star": "feature", "hide": "hide"}[verb]
    copies.pressed_here(callback)  # this copy is changed below; the other moderators' copies by the service
    try:
        await community.moderate(db, actor_id=member.id, contribution_id=uuid.UUID(hex=value), action=action)
    except AppError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    done = texts.COMMUNITY_DONE[action].format(admin=html.escape(member.first_name))
    await callback.answer(done.split(" — ")[0])
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"{callback.message.html_text}\n\n{done}", reply_markup=keyboards.community_admin_after()
        )
