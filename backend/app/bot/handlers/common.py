"""Commands available to everybody: /help, /myid, /cancel."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.bot.access import is_admin
from app.models import User
from app.models.enums import UserStatus

router = Router(name="common")


@router.message(Command("help"))
@router.message(F.text.in_({texts.BTN_HELP, "ℹ️ Yordam"}))
async def help_(message: Message, state: FSMContext, member: User | None) -> None:
    if member is None:  # possibly in the middle of registration: keep it going
        await message.answer(texts.HELP.split("\n\n")[0] + "\n\n" + texts.NOT_REGISTERED)
        return
    await state.clear()  # leaves «write to admin» / «attendance code» mode
    active = member.status == UserStatus.ACTIVE
    await message.answer(texts.HELP, reply_markup=keyboards.help_menu() if active else None)


@router.message(Command("myid"))
async def my_id(message: Message) -> None:
    assert message.from_user is not None
    await message.answer(texts.MY_ID.format(telegram_id=message.from_user.id))


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if await state.get_state() is None:
        await message.answer(texts.NOTHING_TO_CANCEL)
        return
    await state.clear()
    markup = (
        keyboards.main_menu(is_admin=await is_admin(db, member))
        if member is not None and member.status == UserStatus.ACTIVE
        else None
    )
    await message.answer(texts.CANCELLED, reply_markup=markup)
