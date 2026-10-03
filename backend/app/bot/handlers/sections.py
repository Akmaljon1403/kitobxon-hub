"""Main menu of registered, active members: a short summary per section plus a Mini App button,
notification settings, and attendance by typing the code shown on the screen."""

from __future__ import annotations

import html
import logging
import re
import uuid

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, summaries, texts
from app.bot.filters import ActiveMember
from app.bot.states import AttendanceCode
from app.core.errors import NotFoundError
from app.models import User, UserNotificationSettings
from app.services import attendance as attendance_service
from app.services import certificates as certificate_service
from app.services import delivery
from app.services import passport as passport_service

logger = logging.getLogger(__name__)
router = Router(name="sections")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())

# Codes use 2-9 and A-Z without I and O; members may type them in lower case or with spaces.
_CODE = re.compile(r"^[2-9A-HJ-NP-Z]{6}$")


async def home(message: Message, db: AsyncSession, member: User, text: str | None = None) -> None:
    await message.answer(
        text or texts.WELCOME_BACK.format(first_name=html.escape(member.first_name)),
        reply_markup=await access.menu(db, member),
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
    code = access.SECTION_FEATURES.get(label)
    if code and await access.gate(message, db, member, code):
        return
    if label == texts.BTN_PASSPORT:
        await _passport(message, db, member)
        return
    builders = {
        texts.BTN_BOOKS: summaries.books,
        texts.BTN_EVENTS: summaries.events,
        texts.BTN_TESTS: summaries.tests,
        texts.BTN_RESULTS: summaries.results,
        texts.BTN_RANKING: summaries.ranking,
        texts.BTN_ACHIEVEMENTS: summaries.achievements,
    }
    text = await builders[label](db, member)
    markup = (
        keyboards.achievements()
        if label == texts.BTN_ACHIEVEMENTS
        else keyboards.section_more(keyboards.SECTION_ROUTES[label])
    )
    await message.answer(text, reply_markup=markup)


@router.message(Command("davomat"))
async def attendance_command(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await _attendance(message, state, db, member)


@router.message(Command("pasport"))
async def passport_command(message: Message, state: FSMContext, db: AsyncSession, member: User) -> None:
    await state.clear()
    await _answer_section(message, state, db, member, texts.BTN_PASSPORT)


# ---------------------------------------------------------------------------- passport and certificates


async def _passport(message: Message, db: AsyncSession, member: User) -> None:
    """The passport card as a picture, with the short text summary as its caption."""
    caption = await summaries.passport(db, member)
    try:
        if message.bot is not None:
            await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
        image = await passport_service.render(db, member, bot=message.bot)
    except Exception:
        logger.exception("Passport image failed for %s", member.id)
        await message.answer(caption, reply_markup=keyboards.passport())
        return
    await message.answer_photo(
        BufferedInputFile(image, filename=passport_service.filename(member)),
        caption=caption,
        reply_markup=keyboards.passport(),
    )


@router.callback_query(F.data == "pp:file")
async def passport_file(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    if await access.gate(callback, db, member, "passport"):
        return
    try:
        await delivery.send_passport(callback.bot, db, member, as_file=True)
    except Exception:
        logger.exception("Passport file failed for %s", member.id)
        await callback.answer(texts.FILE_FAILED, show_alert=True)
        return
    await callback.answer(texts.FILE_SENT)


@router.callback_query(F.data == "cert:list")
async def certificate_list(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    if await access.gate(callback, db, member, "certificates"):
        return
    items = await certificate_service.member_certificates(db, member.id)
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    if not items:
        await callback.message.answer(texts.CERTIFICATES_NONE, reply_markup=keyboards.section_more("certificates"))
        return
    await callback.message.answer(
        texts.CERTIFICATES.format(count=len(items)),
        reply_markup=keyboards.certificates([(str(item.id), item.title) for item in items]),
    )


@router.callback_query(F.data.startswith("cert:get:"))
async def certificate_file(callback: CallbackQuery, db: AsyncSession, member: User) -> None:
    if await access.gate(callback, db, member, "certificates"):
        return
    try:
        certificate_id = uuid.UUID((callback.data or "").removeprefix("cert:get:"))
        certificate = await certificate_service.get_own(db, user_id=member.id, certificate_id=certificate_id)
    except (ValueError, NotFoundError):
        await callback.answer(texts.FILE_FAILED, show_alert=True)
        return
    try:
        await delivery.send_certificate(callback.bot, db, member, certificate)
        await db.commit()
    except Exception:
        logger.exception("Certificate file failed for %s", certificate.id)
        await callback.answer(texts.FILE_FAILED, show_alert=True)
        return
    await callback.answer(texts.FILE_SENT)


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
