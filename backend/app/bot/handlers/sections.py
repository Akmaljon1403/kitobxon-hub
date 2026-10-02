"""Main menu of registered, active members: a short summary per section plus a Mini App button,
notification settings, and attendance by typing the code shown on the screen."""

from __future__ import annotations

import html
import re

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, summaries, texts
from app.bot.access import is_admin
from app.bot.filters import ActiveMember
from app.bot.states import AttendanceCode
from app.models import User, UserNotificationSettings
from app.services import attendance as attendance_service

router = Router(name="sections")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())

# Codes use 2-9 and A-Z without I and O; members may type them in lower case or with spaces.
_CODE = re.compile(r"^[2-9A-HJ-NP-Z]{6}$")


async def home(message: Message, db: AsyncSession, member: User, text: str | None = None) -> None:
    await message.answer(
        text or texts.WELCOME_BACK.format(first_name=html.escape(member.first_name)),
        reply_markup=keyboards.main_menu(is_admin=await is_admin(db, member)),
    )


@router.message(Command("menu"))
async def show_menu(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await home(message, db, member)


@router.message(F.text.in_(texts.LEGACY_BUTTONS.keys()))
async def legacy_button(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    """Old keyboard: answer the new section and send the new menu."""
    await state.clear()
    label = texts.LEGACY_BUTTONS[message.text or ""]
    await _answer_section(message, state, db, member, label)
    await home(message, db, member, texts.MENU_UPDATED)


@router.message(F.text.in_(keyboards.SECTION_ROUTES.keys() | {texts.BTN_SETTINGS}))
async def section(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await _answer_section(message, state, db, member, message.text or "")


async def _answer_section(message: Message, state: FSMContext, db: AsyncSession, member: User, label: str) -> None:
    if label == texts.BTN_SETTINGS:
        settings = await _notification_settings(db, member)
        await message.answer(texts.SETTINGS, reply_markup=keyboards.settings_menu(settings))
        return
    if label == texts.BTN_ATTENDANCE:
        await _attendance(message, state, db, member)
        return
    builders = {
        texts.BTN_BOOKS: summaries.books,
        texts.BTN_EVENTS: summaries.events,
        texts.BTN_TESTS: summaries.tests,
        texts.BTN_RESULTS: summaries.results,
        texts.BTN_RANKING: summaries.ranking,
        texts.BTN_ACHIEVEMENTS: summaries.achievements,
        texts.BTN_PASSPORT: summaries.passport,
    }
    text = await builders[label](db, member)
    await message.answer(text, reply_markup=keyboards.section_more(keyboards.SECTION_ROUTES[label]))


@router.message(Command("davomat"))
async def attendance_command(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await _attendance(message, state, db, member)


@router.message(Command("pasport"))
async def passport_command(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await _answer_section(message, state, db, member, texts.BTN_PASSPORT)


# ---------------------------------------------------------------------------- attendance


async def _attendance(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    text, can_check_in = await summaries.attendance(db, member)
    if can_check_in:
        await state.set_state(AttendanceCode.waiting)
    await message.answer(text, reply_markup=keyboards.attendance(scan=can_check_in))


def normalize_code(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


@router.message(StateFilter(AttendanceCode.waiting), F.text, ~F.text.startswith("/"))
async def attendance_code(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    code = normalize_code(message.text or "")
    if not _CODE.match(code):
        await message.answer(texts.ATTENDANCE_CODE_HINT)
        return
    result = await attendance_service.check_in(db, user=member, code=code)
    await state.clear()
    await message.answer(texts.ATTENDANCE_OK.format(title=html.escape(result.event.title), points=result.points))


# ---------------------------------------------------------------------------- notification settings


async def _notification_settings(db: AsyncSession, member: User) -> UserNotificationSettings:
    settings = await db.get(UserNotificationSettings, member.id)
    if settings is None:
        settings = UserNotificationSettings(user_id=member.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.callback_query(F.data.startswith("ntf:"))
async def toggle_notification(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    field = (callback.data or "").removeprefix("ntf:")
    if field not in texts.NOTIFICATION_LABELS:
        await callback.answer()
        return
    settings = await _notification_settings(db, member)
    new_value = not getattr(settings, field)
    setattr(settings, field, new_value)
    await db.commit()
    await callback.answer("Yoqildi ✅" if new_value else "O'chirildi ❌")
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=keyboards.settings_menu(settings))
