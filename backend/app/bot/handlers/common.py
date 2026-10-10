"""Commands available to everybody: /help with the questions and answers, /myid, /cancel and /stop."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.models import User
from app.models.enums import UserStatus
from app.services import card_payments, faq, features

router = Router(name="common")


@router.message(Command("help"))
@router.message(F.text.in_({texts.BTN_HELP, "ℹ️ Yordam"}))
async def help_(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    if member is None:  # possibly in the middle of registration: keep it going
        await message.answer(texts.HELP.split("\n\n")[0] + "\n\n" + texts.NOT_REGISTERED)
        return
    await state.clear()  # leaves «write to admin» / «attendance code» mode
    if member.status != UserStatus.ACTIVE:
        await message.answer(texts.HELP, reply_markup=keyboards.limited_account())
        return
    available = await features.access(db, member)
    markup = keyboards.help_menu(
        support=available["support"] == "on",
        premium=available["premium"] != "off",
        # «Klubni qo'llab-quvvatlash» is for everyone: Stars donations, or simply the club's card.
        donations=available["donations"] != "off" or await card_payments.card_details(db) is not None,
    )
    await message.answer(texts.HELP, reply_markup=markup)


@router.callback_query(F.data == "faq:list")
async def faq_list(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(
            texts.FAQ_TOPICS, reply_markup=keyboards.faq_topics([(topic.code, topic.title) for topic in faq.TOPICS])
        )


@router.callback_query(F.data.startswith("faq:t:"))
async def faq_topic(callback: CallbackQuery, member: User | None) -> None:
    topic = faq.BY_CODE.get((callback.data or "").removeprefix("faq:t:"))
    await callback.answer()
    if topic is None or not isinstance(callback.message, Message):
        return
    body = "\n\n".join(
        f"<b>❔ {html.escape(question, quote=False)}</b>\n{html.escape(answer, quote=False)}"
        for question, answer in topic.items
    )
    await callback.message.answer(
        f"<b>{html.escape(topic.title)}</b>\n\n{body}", reply_markup=keyboards.faq_answer(support=member is not None)
    )


@router.message(Command("stop"))
async def stop(message: Message, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    """Stops whatever was going on (writing to the admins, a code, a receipt, a broadcast...)."""
    await state.clear()
    if member is not None and member.status == UserStatus.ACTIVE:
        await message.answer(texts.STOPPED, reply_markup=await access.menu(db, member))
    else:
        await message.answer(texts.STOPPED)


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
    markup = await access.menu(db, member) if member is not None and member.status == UserStatus.ACTIVE else None
    await message.answer(texts.CANCELLED, reply_markup=markup)
