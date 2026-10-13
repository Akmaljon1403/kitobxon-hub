"""«🛠 Boshqaruv» and /admin: a short overview and the Admin Panel, opened inside Telegram."""

from __future__ import annotations

import contextlib
import html
import uuid

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, summaries, texts
from app.bot.access import has_permission, is_admin, is_super_admin
from app.bot.states import ChannelPostEdit, ChannelStickers, CustomEmojiCollect
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import ChannelSticker, User
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


@router.callback_query(F.data == "adm:logoutall")
async def logout_all(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    """«🔒 Barcha seanslarni yopish»: every Admin Panel session of this person ends now (a stolen link is useless)."""
    from app.services.auth import logout_everywhere

    if member is None:
        await callback.answer()
        return
    await logout_everywhere(db, member.id)
    await callback.answer(texts.ADMIN_LOGGED_OUT, show_alert=True)
    if isinstance(callback.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)


# ---------------------------------------------------------------------------- stickers and premium emoji
# Any admin with the right may teach the bot stickers (/stiker) and premium emoji (/emoji): both kinds
# are accepted in both modes, and outside them the bot offers to save what an admin sends.


async def _decor_right(db: AsyncSession, member: User | None) -> str | None:
    """None when the admin may add stickers and premium emoji, otherwise the reason to show."""
    if not await _allowed(db, member):
        return texts.ADMIN_ONLY
    if await is_super_admin(db, member):
        return None
    for permission in (Perm.NOTIFICATION_SEND, Perm.SETTINGS_MANAGE):
        if await has_permission(db, member, permission):
            return None
    return texts.DECOR_NO_RIGHT


async def _save_sticker(db: AsyncSession, member: User, message: Message) -> tuple[ChannelSticker | None, int]:
    sticker = message.sticker
    assert sticker is not None
    return await channel.add_sticker(
        db,
        actor_id=member.id,
        file_id=sticker.file_id,
        file_unique_id=sticker.file_unique_id,
        emoji=sticker.emoji,
        set_name=sticker.set_name,
        is_animated=bool(sticker.is_animated or sticker.is_video),
    )


def _mood(created: ChannelSticker | None) -> str:
    return texts.STICKER_MOODS.get(str(created.mood) if created else "ANY", "")


def _emoji_pairs(message: Message) -> list[tuple[str, str, str]]:
    if message.text is not None:
        return custom_emoji.pairs_from_message(message.text, list(message.entities or []))
    return custom_emoji.pairs_from_message(message.caption or "", list(message.caption_entities or []))


def _has_premium_emoji(message: Message) -> bool:
    return any(entity.type == "custom_emoji" for entity in (message.entities or message.caption_entities or []))


async def _probe(message: Message, pairs: list[tuple[str, str]]) -> bool:
    """Send a sample with the premium emoji (fallback, id); True when Telegram accepted it."""
    sample = " ".join(
        f'<tg-emoji emoji-id="{html.escape(custom_id)}">{html.escape(fallback)}</tg-emoji>'
        for fallback, custom_id in pairs[:30]
    )
    try:
        await message.answer(texts.EMOJI_SAMPLE.format(sample=sample))
    except TelegramBadRequest:
        custom_emoji.report_refusal(message.chat.id)
        await message.answer(texts.EMOJI_STATUS_REFUSED)
        return False
    custom_emoji.resume()
    custom_emoji.report_success(message.chat.id)
    return True


def _status_text() -> str:
    state = custom_emoji.status()
    if state["paused"] or state["state"] == "refused":
        return texts.EMOJI_STATUS_REFUSED
    if state["state"] == "working":
        return texts.EMOJI_STATUS_WORKING
    if state["state"] == "group_refused":
        return texts.EMOJI_STATUS_GROUP
    return texts.EMOJI_STATUS_UNKNOWN


async def _emoji_overview(db: AsyncSession) -> tuple[str, bool]:
    """The /emoji text (plain emoji only, so it always arrives) and whether anything is saved."""
    rows = await custom_emoji.list_all(db)
    items = ": " + " ".join(html.escape(row.emoji) for row in rows[:60]) if rows else ""
    return texts.EMOJI_ASK.format(count=len(rows), items=items, status=_status_text()), bool(rows)


@router.message(Command("stiker"))
async def stickers_start(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    denied = await _decor_right(db, member)
    if denied:
        await message.answer(denied)
        return
    await state.set_state(ChannelStickers.waiting)
    total = len(await channel.stickers(db))
    await message.answer(texts.STICKER_ASK, reply_markup=keyboards.sticker_overview(total))


@router.callback_query(F.data == "stk:list")
async def stickers_list(callback: CallbackQuery, db: AsyncSession, member: User | None, bot: Bot) -> None:
    """Show every saved sticker right in the bot, each with its own «🗑 O'chirish» button."""
    if await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    rows = await channel.stickers(db)
    if not rows:
        await callback.message.answer(texts.STICKER_LIST_EMPTY)
        return
    await callback.message.answer(texts.STICKER_LIST_HEADER.format(total=len(rows)))
    for sticker in rows:
        with contextlib.suppress(TelegramBadRequest):
            await bot.send_sticker(
                callback.message.chat.id, sticker.file_id, reply_markup=keyboards.sticker_delete(sticker.id)
            )


@router.callback_query(F.data.startswith("stk:del:"))
async def stickers_delete(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if member is None or await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    try:
        sticker_id = uuid.UUID((callback.data or "").removeprefix("stk:del:"))
    except ValueError:
        await callback.answer()
        return
    await channel.delete_sticker(db, actor_id=member.id, sticker_id=sticker_id)
    total = len(await channel.stickers(db))
    await callback.answer("🗑")
    if isinstance(callback.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await callback.message.delete()
        await callback.message.answer(texts.STICKER_DELETED.format(total=total))


@router.message(ChannelStickers.waiting, Command("tayyor"))
async def stickers_done(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.STICKER_DONE)


@router.message(ChannelStickers.waiting, F.sticker)
@router.message(CustomEmojiCollect.waiting, F.sticker)
async def sticker_save(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if member is None or await _decor_right(db, member):
        await state.clear()
        await message.answer(texts.ADMIN_ONLY)
        return
    created, total = await _save_sticker(db, member, message)
    if await state.get_state() == CustomEmojiCollect.waiting.state:
        await message.answer(texts.STICKER_FROM_EMOJI.format(mood=_mood(created), total=total))
        return
    await message.answer(
        (texts.STICKER_SAVED if created else texts.STICKER_DUPLICATE).format(total=total, mood=_mood(created))
    )


@router.message(ChannelStickers.waiting, ~F.text.startswith("/"), F.func(_has_premium_emoji))
async def sticker_mode_emoji(message: Message, db: AsyncSession, member: User | None) -> None:
    """Premium emoji sent while collecting stickers are saved as premium emoji."""
    pairs = _emoji_pairs(message)
    if member is None or not pairs:
        await message.answer(texts.STICKER_ONLY)
        return
    total = await custom_emoji.save(db, actor_id=member.id, pairs=pairs)
    shown = ", ".join(emoji for emoji, _, _ in pairs)
    await message.answer(texts.EMOJI_FROM_STICKER_MODE.format(emoji=html.escape(shown), total=total))
    await _probe(message, [(fallback, custom_id) for _, custom_id, fallback in pairs])


@router.message(ChannelStickers.waiting, ~F.text.startswith("/"))
async def sticker_expected(message: Message) -> None:
    await message.answer(texts.STICKER_ONLY)


@router.message(Command("emoji"))
async def emoji_start(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    denied = await _decor_right(db, member)
    if denied:
        await message.answer(denied)
        return
    await state.set_state(CustomEmojiCollect.waiting)
    text, has_any = await _emoji_overview(db)
    await message.answer(text, reply_markup=keyboards.emoji_tools(has_any))


@router.message(CustomEmojiCollect.waiting, Command("tayyor"))
async def emoji_done(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.EMOJI_DONE)


@router.message(CustomEmojiCollect.waiting, ~F.text.startswith("/"))
async def emoji_save(message: Message, db: AsyncSession, member: User | None) -> None:
    if member is None:
        return
    pairs = _emoji_pairs(message)
    if not pairs:
        await message.answer(texts.EMOJI_NONE_FOUND)
        return
    total = await custom_emoji.save(db, actor_id=member.id, pairs=pairs)
    shown = ", ".join(emoji for emoji, _, _ in pairs)
    await message.answer(texts.EMOJI_SAVED.format(emoji=html.escape(shown), count=len(pairs), total=total))
    await _probe(message, [(fallback, custom_id) for _, custom_id, fallback in pairs])


@router.callback_query(F.data == "emj:test")
async def emoji_test(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()
    rows = await custom_emoji.list_all(db)
    if not isinstance(callback.message, Message):
        return
    if not rows:
        await callback.message.answer(texts.EMOJI_NONE_FOUND)
        return
    if await _probe(callback.message, [(row.fallback, row.custom_emoji_id) for row in rows]):
        await callback.message.answer(texts.EMOJI_STATUS_WORKING)


@router.callback_query(F.data == "emj:list")
async def emoji_list(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    """Show the saved premium emoji, each with its own delete button."""
    if await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    rows = await custom_emoji.list_all(db)
    if not rows:
        await callback.message.answer(texts.EMOJI_LIST_EMPTY)
        return
    await callback.message.answer(
        texts.EMOJI_LIST_HEADER,
        reply_markup=keyboards.emoji_delete_list([(row.emoji, row.custom_emoji_id) for row in rows]),
    )


@router.callback_query(F.data.startswith("emj:del:"))
async def emoji_delete_one(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    emoji = (callback.data or "").removeprefix("emj:del:")
    await custom_emoji.clear(db, emoji=emoji)
    await callback.answer(texts.EMOJI_DELETED.format(emoji=emoji))
    if isinstance(callback.message, Message):
        rows = await custom_emoji.list_all(db)
        with contextlib.suppress(TelegramBadRequest):
            if rows:
                await callback.message.edit_reply_markup(
                    reply_markup=keyboards.emoji_delete_list([(row.emoji, row.custom_emoji_id) for row in rows])
                )
            else:
                await callback.message.edit_text(texts.EMOJI_LIST_EMPTY)


@router.callback_query(F.data == "emj:clear")
async def emoji_clear(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    await custom_emoji.clear(db)
    await callback.answer("🗑")
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.EMOJI_CLEARED)


# Outside the modes: an admin who simply sends a sticker or premium emoji is offered to save it.


@router.message(StateFilter(None), F.sticker | F.func(_has_premium_emoji), F.chat.type == "private")
async def decor_offer(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if await _decor_right(db, member):
        raise SkipHandler  # a member's sticker: the usual handlers answer
    if message.sticker is not None:
        sticker = message.sticker
        await state.update_data(
            decor={
                "kind": "sticker",
                "file_id": sticker.file_id,
                "file_unique_id": sticker.file_unique_id,
                "emoji": sticker.emoji,
                "set_name": sticker.set_name,
                "animated": bool(sticker.is_animated or sticker.is_video),
            }
        )
        text = texts.DECOR_OFFER_STICKER
    else:
        pairs = _emoji_pairs(message)
        if not pairs:
            raise SkipHandler
        await state.update_data(decor={"kind": "emoji", "pairs": [list(pair) for pair in pairs]})
        text = texts.DECOR_OFFER_EMOJI.format(count=len(pairs))
    await message.answer(text, reply_markup=keyboards.decor_offer())


@router.callback_query(F.data.in_({"dec:save", "dec:skip"}))
async def decor_answer(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if member is None or await _decor_right(db, member):
        await callback.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    data = await state.get_data()
    offer = data.get("decor")
    await state.update_data(decor=None)
    await callback.answer()
    message = callback.message if isinstance(callback.message, Message) else None
    if message is not None:
        with contextlib.suppress(TelegramBadRequest):
            await message.edit_reply_markup(reply_markup=None)
    if message is None:
        return
    if callback.data == "dec:skip":
        await message.answer(texts.DECOR_SKIPPED)
        return
    if not offer:
        await message.answer(texts.DECOR_EXPIRED)
        return
    if offer["kind"] == "sticker":
        created, total = await channel.add_sticker(
            db,
            actor_id=member.id,
            file_id=offer["file_id"],
            file_unique_id=offer["file_unique_id"],
            emoji=offer.get("emoji"),
            set_name=offer.get("set_name"),
            is_animated=bool(offer.get("animated")),
        )
        await message.answer(
            (texts.DECOR_STICKER_ADDED if created else texts.DECOR_STICKER_KNOWN).format(
                total=total, mood=_mood(created)
            )
        )
        return
    pairs = [(str(a), str(b), str(c)) for a, b, c in offer["pairs"]]
    total = await custom_emoji.save(db, actor_id=member.id, pairs=pairs)
    shown = ", ".join(emoji for emoji, _, _ in pairs)
    await message.answer(texts.DECOR_EMOJI_ADDED.format(emoji=html.escape(shown), total=total))
    await _probe(message, [(fallback, custom_id) for _, custom_id, fallback in pairs])


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
