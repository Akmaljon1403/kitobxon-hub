"""/start and the step-by-step registration conversation.

Every answer is validated with the same rules the API uses (``app.services.members``) and
validated again when the account is finally created.
"""

from __future__ import annotations

import html
import uuid

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.bot.states import Registration
from app.core.errors import ConflictError
from app.models import User
from app.models.enums import UserStatus
from app.services import attendance as attendance_service
from app.services.members import (
    RegistrationData,
    after_registration,
    get_active_faculty,
    list_active_faculties,
    normalize_group,
    normalize_name,
    normalize_phone,
    phone_belongs_to_other_user,
    register_member,
    validate_course,
)
from app.services.settings import get_setting

router = Router(name="registration")

_STATUS_TEXT = {
    UserStatus.PENDING: texts.ACCOUNT_PENDING,
    UserStatus.BLOCKED: texts.ACCOUNT_BLOCKED,
    UserStatus.INACTIVE: texts.ACCOUNT_INACTIVE,
    UserStatus.LEFT: texts.ACCOUNT_LEFT,
}


async def _steps(db: AsyncSession) -> dict[str, str]:
    """Step labels such as "3/6" (the faculty step is skipped when no faculties are configured)."""
    names = ["first_name", "last_name", "phone"]
    if await list_active_faculties(db):
        names.append("faculty")
    names += ["course", "group"]
    return {name: f"{index}/{len(names)}" for index, name in enumerate(names, start=1)}


async def send_member_home(message: Message, member: User, db: AsyncSession) -> None:
    if member.status == UserStatus.ACTIVE:
        await message.answer(
            texts.WELCOME_BACK.format(first_name=html.escape(member.first_name)),
            reply_markup=await access.menu(db, member),
        )
    else:
        await message.answer(_STATUS_TEXT.get(member.status, texts.ACCOUNT_INACTIVE), reply_markup=keyboards.remove())


async def begin_registration(message: Message, state: FSMContext, db: AsyncSession) -> None:
    await _begin(message, state, db)


async def _begin(message: Message, state: FSMContext, db: AsyncSession) -> None:
    await state.clear()
    await state.set_state(Registration.first_name)
    steps = await _steps(db)
    await message.answer(texts.WELCOME_NEW, reply_markup=keyboards.remove())
    await message.answer(texts.ASK_FIRST_NAME.format(step=steps["first_name"]))


@router.message(CommandStart())
async def start(
    message: Message, state: FSMContext, db: AsyncSession, member: User | None, command: CommandObject
) -> None:
    payload = command.args or ""
    if payload.startswith(attendance_service.QR_PREFIX):
        await _check_in_from_qr(message, state, db, member, payload)
        return
    if member is not None and member.status == UserStatus.LEFT:
        from app.bot.handlers.membership import offer_return

        await state.clear()
        await offer_return(message, db, member)
        return
    if member is not None:
        await state.clear()
        await send_member_home(message, member, db)
        return
    await _begin(message, state, db)


async def _check_in_from_qr(
    message: Message, state: FSMContext, db: AsyncSession, member: User | None, payload: str
) -> None:
    """The member scanned the event QR code with the phone camera: Telegram opened the bot with it."""
    if member is None:
        await message.answer(texts.ATTENDANCE_REGISTER_FIRST)
        await _begin(message, state, db)
        return
    if member.status != UserStatus.ACTIVE:
        await send_member_home(message, member, db)
        return
    await state.clear()
    result = await attendance_service.check_in(db, user=member, token=payload)
    await message.answer(
        texts.ATTENDANCE_OK.format(title=html.escape(result.event.title), points=result.points),
        reply_markup=await access.menu(db, member),
    )


@router.message(Command("cancel"), StateFilter(Registration))
async def cancel_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.REGISTRATION_CANCELLED, reply_markup=keyboards.remove())


@router.message(Registration.first_name, F.text, ~F.text.startswith("/"))
async def first_name(message: Message, state: FSMContext, db: AsyncSession) -> None:
    value = normalize_name(message.text or "", "first_name")
    await state.update_data(first_name=value)
    await state.set_state(Registration.last_name)
    await message.answer(texts.ASK_LAST_NAME.format(step=(await _steps(db))["last_name"]))


@router.message(Registration.last_name, F.text, ~F.text.startswith("/"))
async def last_name(message: Message, state: FSMContext, db: AsyncSession) -> None:
    value = normalize_name(message.text or "", "last_name")
    await state.update_data(last_name=value)
    await state.set_state(Registration.phone)
    await message.answer(texts.ASK_PHONE.format(step=(await _steps(db))["phone"]), reply_markup=keyboards.share_phone())


@router.message(Registration.phone, F.contact)
async def phone(message: Message, state: FSMContext, db: AsyncSession) -> None:
    contact = message.contact
    assert contact is not None and message.from_user is not None
    # Telegram fills user_id only when the contact is the sender's own account.
    if contact.user_id != message.from_user.id:
        await message.answer(texts.PHONE_NOT_YOURS, reply_markup=keyboards.share_phone())
        return
    value = normalize_phone(contact.phone_number)
    if await phone_belongs_to_other_user(db, value, message.from_user.id):
        raise ConflictError(
            "PHONE_IN_USE", "Bu telefon raqami boshqa hisobga bog'langan. Klub rahbariyatiga murojaat qiling."
        )
    await state.update_data(phone=value)
    await message.answer(texts.PHONE_ACCEPTED, reply_markup=keyboards.remove())
    await _ask_faculty_or_course(message, state, db)


@router.message(Registration.phone, ~F.text.startswith("/"))
async def phone_typed(message: Message) -> None:
    await message.answer(texts.ASK_PHONE_USE_BUTTON, reply_markup=keyboards.share_phone())


async def _ask_faculty_or_course(message: Message, state: FSMContext, db: AsyncSession) -> None:
    steps = await _steps(db)
    faculties = await list_active_faculties(db)
    if faculties:
        await state.set_state(Registration.faculty)
        await message.answer(
            texts.ASK_FACULTY.format(step=steps["faculty"]), reply_markup=keyboards.faculties(faculties)
        )
        return
    await state.update_data(faculty_id=None, faculty_name=None)
    await _ask_course(message, state, db)


async def _ask_course(message: Message, state: FSMContext, db: AsyncSession) -> None:
    await state.set_state(Registration.course)
    max_course = await get_setting(db, "registration.max_course")
    await message.answer(
        texts.ASK_COURSE.format(step=(await _steps(db))["course"]), reply_markup=keyboards.courses(max_course)
    )


@router.callback_query(Registration.faculty, F.data.startswith("reg:fac:"))
async def faculty(callback: CallbackQuery, state: FSMContext, db: AsyncSession) -> None:
    try:
        faculty_id = uuid.UUID((callback.data or "").removeprefix("reg:fac:"))
    except ValueError:
        await callback.answer(texts.REGISTRATION_EXPIRED, show_alert=True)
        return
    chosen = await get_active_faculty(db, faculty_id)
    await state.update_data(faculty_id=str(chosen.id), faculty_name=chosen.name)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"🏛 {html.escape(chosen.name)}")
        await _ask_course(callback.message, state, db)


@router.callback_query(Registration.course, F.data.startswith("reg:course:"))
async def course(callback: CallbackQuery, state: FSMContext, db: AsyncSession) -> None:
    raw = (callback.data or "").removeprefix("reg:course:")
    if not raw.isdigit():
        await callback.answer(texts.REGISTRATION_EXPIRED, show_alert=True)
        return
    value = await validate_course(db, int(raw))
    await state.update_data(course=value)
    await state.set_state(Registration.group)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"🎓 {value}-kurs")
        await callback.message.answer(texts.ASK_GROUP.format(step=(await _steps(db))["group"]))


@router.message(Registration.group, F.text, ~F.text.startswith("/"))
async def group(message: Message, state: FSMContext) -> None:
    value = normalize_group(message.text or "")
    data = await state.update_data(group_name=value)
    await state.set_state(Registration.confirm)
    await message.answer(
        texts.CONFIRM.format(
            first_name=html.escape(data["first_name"]),
            last_name=html.escape(data["last_name"]),
            phone=html.escape(data["phone"]),
            faculty=html.escape(data.get("faculty_name") or texts.NO_FACULTY),
            course=data["course"],
            group=html.escape(value),
        ),
        reply_markup=keyboards.confirm_registration(),
    )


@router.callback_query(Registration.confirm, F.data == "reg:confirm")
async def confirm(callback: CallbackQuery, state: FSMContext, db: AsyncSession) -> None:
    data = await state.get_data()
    sender = callback.from_user
    registration = RegistrationData(
        telegram_id=sender.id,
        telegram_username=sender.username,
        language_code=sender.language_code,
        first_name=data["first_name"],
        last_name=data["last_name"],
        phone=data["phone"],
        faculty_id=uuid.UUID(data["faculty_id"]) if data.get("faculty_id") else None,
        course=int(data["course"]),
        group_name=data["group_name"],
    )
    try:
        user = await register_member(db, registration)
    except ConflictError as exc:
        if exc.code != "ALREADY_REGISTERED":
            raise
        await state.clear()
        await callback.answer(exc.message, show_alert=True)
        return
    await state.clear()
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(reply_markup=None)
        if user.status == UserStatus.ACTIVE:
            await callback.message.answer(
                texts.REGISTERED.format(first_name=html.escape(user.first_name)),
                reply_markup=await access.menu(db, user),
            )
        else:
            await callback.message.answer(texts.REGISTERED_PENDING.format(first_name=html.escape(user.first_name)))
    await after_registration(db, user.id)


@router.callback_query(F.data == "reg:restart")
async def restart(callback: CallbackQuery, state: FSMContext, db: AsyncSession, member: User | None) -> None:
    await callback.answer()
    if member is not None or not isinstance(callback.message, Message):
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await _begin(callback.message, state, db)


@router.callback_query(F.data.startswith("reg:"))
async def stale_registration_button(callback: CallbackQuery) -> None:
    await callback.answer(texts.REGISTRATION_EXPIRED, show_alert=True)


@router.message(StateFilter(Registration), ~F.text.startswith("/"))
async def unexpected_input(message: Message) -> None:
    """Stickers, photos, etc. during registration."""
    await message.answer(texts.REGISTRATION_TEXT_ONLY)
