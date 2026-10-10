"""Events and books opened from a channel post («✅ Qatnashaman», «📖 O'qiyman»), and the super
admin's decision on members added to the attendance by hand."""

from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, keyboards, texts
from app.core.errors import AppError
from app.models import User
from app.models.enums import EventStatus, UserStatus
from app.services import books as book_service
from app.services import event_times
from app.services import events as event_service
from app.utils.timezone import format_human_date

logger = logging.getLogger(__name__)
router = Router(name="events")


def _hex_id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(hex=value)
    except ValueError:
        return None


async def show_event(message: Message, db: AsyncSession, member: User, event_id: uuid.UUID) -> None:
    """The event card with one-tap registration (per shift when there are several)."""
    try:
        event, registration, record = await event_service.get_member_event(db, user_id=member.id, event_id=event_id)
    except AppError:
        await message.answer(texts.EVENT_NOT_FOUND)
        return
    shifts = await event_service.shifts_of(db, event.id)
    counts = await event_service.shift_registrations(db, [event.id])
    registered, _ = (await event_service.counts(db, [event.id]))[event.id]
    titles = await event_service.book_titles(db, {event.book_id} if event.book_id else set())
    lines = [f"📅 <b>«{html.escape(event.title)}»</b>", f"🗓 {html.escape(event_times.when_text(event, shifts))}"]
    if event.location:
        lines.append(f"📍 {html.escape(event.location)}")
    if event.book_id and event.book_id in titles:
        lines.append(f"📚 «{html.escape(titles[event.book_id])}» asari bo'yicha")
    lines.append(f"👥 Ro'yxatdan o'tgan: {registered}")
    is_registered = registration is not None and registration.status.value == "REGISTERED"
    rows: list[list[InlineKeyboardButton | None]] = []
    open_for_registration = event.status == EventStatus.PUBLISHED and event.ends_at > datetime.now(UTC)
    if record is not None and record.status in event_service.COUNTED:
        lines += ["", texts.EVENT_ATTENDING if event.ends_at > datetime.now(UTC) else texts.EVENT_ATTENDED]
    elif not open_for_registration:
        lines += ["", texts.EVENT_REGISTRATION_CLOSED]
    elif shifts:
        mine = next((shift for shift in shifts if registration and shift.id == registration.shift_id), None)
        lines += [
            "",
            texts.EVENT_PICK_SHIFT
            if mine is None or not is_registered
            else texts.EVENT_YOUR_SHIFT.format(shift=html.escape(event_times.shift_text(mine))),
        ]
        for shift in shifts:
            if shift.ends_at <= datetime.now(UTC):
                continue
            chosen = is_registered and mine is not None and mine.id == shift.id
            label = f"{'✅ ' if chosen else ''}{event_times.shift_text(shift)} · {counts.get(shift.id, 0)} kishi"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"evr:{event.id.hex}:{shift.position}")])
    elif is_registered:
        lines += ["", texts.EVENT_REGISTERED]
    else:
        lines += ["", texts.EVENT_WHY_REGISTER]
        rows.append([InlineKeyboardButton(text=texts.BTN_ATTEND, callback_data=f"evr:{event.id.hex}:0")])
    if is_registered and open_for_registration and event.starts_at > datetime.now(UTC):
        rows.append([InlineKeyboardButton(text=texts.BTN_UNREGISTER, callback_data=f"evx:{event.id.hex}")])
    rows.append([keyboards.app_button(f"events/{event.id}")])
    await message.answer("\n".join(lines), reply_markup=keyboards.inline(*rows))


async def show_book(message: Message, db: AsyncSession, member: User, book_id: uuid.UUID) -> None:
    try:
        book = await book_service.get_book(db, book_id)
    except AppError:
        await message.answer(texts.BOOK_NOT_FOUND)
        return
    lines = [f"📖 <b>«{html.escape(book.title)}»</b>", f"✍️ {html.escape(book.author)}"]
    if book.deadline:
        lines.append(f"🗓 O'qish muddati: {format_human_date(book.deadline)} gacha")
    if book.description:
        lines += ["", html.escape(book.description.strip()[:600])]
    lines += ["", texts.BOOK_START_HINT]
    await message.answer(
        "\n".join(lines),
        reply_markup=keyboards.inline(
            [InlineKeyboardButton(text=texts.BTN_START_READING, callback_data=f"bkr:{book.id.hex}")],
            [keyboards.app_button(f"books/{book.id}")],
        ),
    )


async def open_link(message: Message, db: AsyncSession, member: User, payload: str) -> bool:
    """/start ev_<id> or bk_<id> from a channel post. Returns False for other payloads."""
    kind, _, raw = payload.partition("_")
    target = _hex_id(raw)
    if kind not in ("ev", "bk") or target is None:
        return False
    if kind == "ev":
        await show_event(message, db, member, target)
    else:
        await show_book(message, db, member, target)
    return True


def _active(member: User | None) -> bool:
    return member is not None and member.status == UserStatus.ACTIVE


@router.callback_query(F.data.startswith("evr:"))
async def register(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or not isinstance(callback.message, Message):
        await callback.answer(texts.NOT_REGISTERED, show_alert=True)
        return
    assert member is not None
    _, raw, position = (callback.data or "").split(":", 2)
    event_id = _hex_id(raw)
    if event_id is None:
        await callback.answer()
        return
    shift_id = None
    if position != "0":
        shift = next((s for s in await event_service.shifts_of(db, event_id) if str(s.position) == position), None)
        shift_id = shift.id if shift else None
    try:
        await event_service.register(db, user_id=member.id, event_id=event_id, shift_id=shift_id)
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await callback.answer(texts.EVENT_REGISTERED_ALERT)
    await show_event(callback.message, db, member, event_id)


@router.callback_query(F.data.startswith("evx:"))
async def unregister(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member) or not isinstance(callback.message, Message):
        await callback.answer()
        return
    assert member is not None
    event_id = _hex_id((callback.data or "").removeprefix("evx:"))
    if event_id is None:
        await callback.answer()
        return
    try:
        await event_service.cancel_registration(db, user_id=member.id, event_id=event_id)
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await callback.answer(texts.EVENT_UNREGISTERED)
    await show_event(callback.message, db, member, event_id)


@router.callback_query(F.data.startswith("bkr:"))
async def start_reading(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    if not _active(member):
        await callback.answer(texts.NOT_REGISTERED, show_alert=True)
        return
    assert member is not None
    book_id = _hex_id((callback.data or "").removeprefix("bkr:"))
    if book_id is None:
        await callback.answer()
        return
    try:
        await book_service.set_reading_status(db, user_id=member.id, book_id=book_id, action="start")
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer(texts.BOOK_STARTED)


# ---------------------------------------------------------------------------- manual attendance requests


@router.callback_query(F.data.startswith("att:"))
async def decide_attendance(callback: CallbackQuery, db: AsyncSession, member: User | None) -> None:
    from app.services import attendance as attendance_service

    if not await access.is_super_admin(db, member):
        await callback.answer(texts.SUPER_ADMIN_ONLY, show_alert=True)
        return
    assert member is not None
    _, decision, raw = (callback.data or "").split(":", 2)
    record_id = _hex_id(raw)
    if record_id is None:
        await callback.answer()
        return
    try:
        record = await attendance_service.decide_request(
            db, actor_id=member.id, record_id=record_id, approve=decision == "ok"
        )
    except AppError as error:
        await callback.answer(error.message, show_alert=True)
        return
    text = texts.ATTENDANCE_APPROVED if record is not None else texts.ATTENDANCE_REJECTED
    await callback.answer(text)
    if isinstance(callback.message, Message):
        await callback.message.answer(text)
