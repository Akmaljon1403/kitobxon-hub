"""«🛠 Boshqaruv» and /admin: a short overview and the Admin Panel, opened inside Telegram."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, summaries, texts
from app.bot.access import has_permission, is_admin
from app.bot.states import ChannelStickers
from app.core.config import get_settings
from app.models import User
from app.models.enums import UserStatus
from app.security.permissions import Perm
from app.services import channel
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
    await message.answer((texts.STICKER_SAVED if created else texts.STICKER_DUPLICATE).format(total=total))


@router.message(ChannelStickers.waiting)
async def sticker_expected(message: Message) -> None:
    await message.answer(texts.STICKER_ONLY)
