"""«🛠 Boshqaruv» and /admin: a short overview and the Admin Panel, opened inside Telegram."""

from __future__ import annotations

import contextlib
import html
import uuid

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, summaries, texts
from app.bot.access import has_permission, is_admin
from app.bot.states import ChannelPostEdit, ChannelStickers, CustomEmojiCollect
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import User
from app.models.enums import UserStatus
from app.security.permissions import Perm
from app.services import channel, custom_emoji
from app.services.auth import NotAdminError, admin_login_url, create_admin_login_link

router = Router(name="admin")


async def _allowed(db: AsyncSession, member: User | None) -> bool:
    return member is not None and member.status == UserStatus.ACTIVE and await is_admin(db, member)


@router.message(Command("admin"))
@router.message(F.text == texts.BTN_ADMIN)
async def admin_home(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await state.clear()
    if not await _allowed(db, member):
        await message.answer(texts.ADMIN_ONLY)
        return
    if get_settings().base_url is None:
        await message.answer(texts.ADMIN_URL_NOT_CONFIGURED)
        return
    await message.answer(await summaries.admin_home(db), reply_markup=keyboards.admin_home())


@router.callback_query(F.data == "adm:link")
async def computer_link(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if member is None or not await _allowed(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    try:
        raw_token, _ = await create_admin_login_link(db, member)
    except NotAdminError:
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    url = admin_login_url(raw_token)
    await callback.answer()
    if url and isinstance(callback.message, Message):
        minutes = max(1, get_settings().admin_login_link_ttl_seconds // 60)
        await callback.message.answer(texts.ADMIN_LINK.format(minutes=minutes), reply_markup=keyboards.admin_login(url))


# ---------------------------------------------------------------------------- channel stickers


@router.message(Command("stiker"))
async def stickers_start(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if not await _allowed(db, member) or not await has_permission(db, member, Perm.NOTIFICATION_SEND):
        await message.answer(texts.ADMIN_ONLY)
        return
    await state.set_state(ChannelStickers.waiting)
    await message.answer(texts.STICKER_ASK)


@router.message(ChannelStickers.waiting, Command("tayyor"))
async def stickers_done(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.STICKER_DONE)


@router.message(ChannelStickers.waiting, F.sticker)
async def sticker_save(message: Message, db: AsyncSession, member: User | None) -> None:
    if member is None or message.sticker is None:
        return
    sticker = message.sticker
    created, total = await channel.add_sticker(
        db,
        actor_id=member.id,
        file_id=sticker.file_id,
        file_unique_id=sticker.file_unique_id,
        emoji=sticker.emoji,
        set_name=sticker.set_name,
        is_animated=bool(sticker.is_animated or sticker.is_video),
    )
    mood = texts.STICKER_MOODS.get(str(created.mood) if created else "ANY", "")
    await message.answer((texts.STICKER_SAVED if created else texts.STICKER_DUPLICATE).format(total=total, mood=mood))


@router.message(ChannelStickers.waiting)
async def sticker_expected(message: Message) -> None:
    await message.answer(texts.STICKER_ONLY)


# ---------------------------------------------------------------------------- premium emoji in messages


async def _emoji_overview(db: AsyncSession) -> str:
    rows = await custom_emoji.list_all(db)
    items = "".join(
        f'\n{html.escape(row.fallback)} → <tg-emoji emoji-id="{html.escape(row.custom_emoji_id)}">'
        f"{html.escape(row.fallback)}</tg-emoji>"
        for row in rows[:40]
    )
    text = texts.EMOJI_ASK.format(count=len(rows), items=items)
    return text + (texts.EMOJI_PAUSED if custom_emoji.paused() else "")


@router.message(Command("emoji"))
async def emoji_start(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if not await _allowed(db, member) or not await has_permission(db, member, Perm.NOTIFICATION_SEND):
        await message.answer(texts.ADMIN_ONLY)
        return
    await state.set_state(CustomEmojiCollect.waiting)
    has_any = bool(await custom_emoji.list_all(db))
    markup = (
        keyboards.inline([InlineKeyboardButton(text=texts.BTN_EMOJI_CLEAR, callback_data="emj:clear")])
        if has_any
        else None
    )
    await message.answer(await _emoji_overview(db), reply_markup=markup)


@router.message(CustomEmojiCollect.waiting, Command("tayyor"))
async def emoji_done(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.EMOJI_DONE)


@router.message(CustomEmojiCollect.waiting)
async def emoji_save(message: Message, db: AsyncSession, member: User | None) -> None:
    if member is None:
        return
    pairs = custom_emoji.pairs_from_message(message.text or message.caption or "", message.entities or [])
    if not pairs:
        await message.answer(texts.EMOJI_NONE_FOUND)
        return
    total = await custom_emoji.save(db, actor_id=member.id, pairs=pairs)
    shown = ", ".join(
        f'{html.escape(emoji)} → <tg-emoji emoji-id="{html.escape(custom_id)}">{html.escape(fallback)}</tg-emoji>'
        for emoji, custom_id, fallback in pairs
    )
    await message.answer(texts.EMOJI_SAVED.format(pairs=shown, total=total))


@router.callback_query(F.data == "emj:clear")
async def emoji_clear(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not await _allowed(db, member) or not await has_permission(db, member, Perm.NOTIFICATION_SEND):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    await custom_emoji.clear(db)
    await callback.answer("🗑")
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.EMOJI_CLEARED)


# ---------------------------------------------------------------------------- channel posts: admins look first


async def _post_id(callback: CallbackQuery, db: AsyncSession, member: User | None, prefix: str) -> uuid.UUID | None:
    if not await _allowed(db, member) or not await has_permission(db, member, Perm.NOTIFICATION_SEND):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return None
    try:
        return uuid.UUID(hex=(callback.data or "").removeprefix(prefix))
    except ValueError:
        await callback.answer()
        return None


async def _done(callback: CallbackQuery, text: str) -> None:
    await callback.answer(text)
    if isinstance(callback.message, Message):
        with contextlib.suppress(TelegramBadRequest):  # the preview may be too old to edit
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(text)


@router.callback_query(F.data.startswith("chp:ok:"))
async def channel_post_now(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    post_id = await _post_id(callback, db, member, "chp:ok:")
    if post_id is None or member is None:
        return
    try:
        await channel.publish_now(db, actor_id=member.id, post_id=post_id, by_preview=True)
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await _done(callback, texts.CHANNEL_POST_NOW)


@router.callback_query(F.data.startswith("chp:no:"))
async def channel_post_cancel(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    post_id = await _post_id(callback, db, member, "chp:no:")
    if post_id is None or member is None:
        return
    try:
        await channel.cancel_post(db, actor_id=member.id, post_id=post_id, by_preview=True)
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await _done(callback, texts.CHANNEL_POST_CANCELLED)


@router.callback_query(F.data.startswith("chp:edit:"))
async def channel_post_edit(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    post_id = await _post_id(callback, db, member, "chp:edit:")
    if post_id is None or member is None:
        return
    try:
        await channel.hold_for_edit(db, actor_id=member.id, post_id=post_id)
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await state.set_state(ChannelPostEdit.waiting)
    await state.update_data(post_id=post_id.hex)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.CHANNEL_POST_EDIT_ASK)


@router.message(ChannelPostEdit.waiting, Command("cancel"))
async def channel_post_edit_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CHANNEL_POST_EDIT_KEPT)


@router.message(ChannelPostEdit.waiting, F.text)
async def channel_post_new_text(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    data = await state.get_data()
    if member is None or not data.get("post_id"):
        await state.clear()
        return
    try:
        await channel.edit_post(db, actor_id=member.id, post_id=uuid.UUID(hex=data["post_id"]), text=message.html_text)
    except AppError as error:
        if error.code != "EMPTY_POST" and error.code != "POST_TOO_LONG":
            await state.clear()
        await message.answer(error.message)
        return
    await state.clear()
    await message.answer(texts.CHANNEL_POST_EDITED)


@router.message(ChannelPostEdit.waiting)
async def channel_post_text_expected(message: Message) -> None:
    await message.answer(texts.CHANNEL_POST_TEXT_ONLY)
