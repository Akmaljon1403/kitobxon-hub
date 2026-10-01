"""Commands available to everybody: /help, /myid, /admin, /cancel."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.core.config import get_settings
from app.models import User
from app.services.auth import NotAdminError, admin_login_url, create_admin_login_link

router = Router(name="common")


@router.message(Command("help"))
@router.message(F.text == texts.BTN_HELP)
async def help_(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("myid"))
async def my_id(message: Message) -> None:
    assert message.from_user is not None
    await message.answer(texts.MY_ID.format(telegram_id=message.from_user.id))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(Command("admin"))
async def admin_login(message: Message, db: AsyncSession, member: User | None) -> None:
    if member is None:
        await message.answer(texts.ADMIN_ONLY)
        return
    if get_settings().base_url is None:
        await message.answer(texts.ADMIN_URL_NOT_CONFIGURED)
        return
    try:
        raw_token, _ = await create_admin_login_link(db, member)
    except NotAdminError:
        await message.answer(texts.ADMIN_ONLY)
        return
    url = admin_login_url(raw_token)
    assert url is not None
    minutes = max(1, get_settings().admin_login_link_ttl_seconds // 60)
    await message.answer(texts.ADMIN_LINK.format(minutes=minutes), reply_markup=keyboards.admin_login(url))
