"""Main menu of registered, active members."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.bot.filters import ActiveMember
from app.core.config import get_settings
from app.models import Faculty, User, UserNotificationSettings
from app.utils.timezone import format_date

router = Router(name="menu")
router.message.filter(ActiveMember())
router.callback_query.filter(ActiveMember())


@router.message(Command("menu"))
async def show_menu(message: Message, member: User) -> None:
    await message.answer(
        texts.WELCOME_BACK.format(first_name=html.escape(member.first_name)), reply_markup=keyboards.main_menu()
    )


@router.message(F.text == texts.BTN_PROFILE)
async def profile(message: Message, db: AsyncSession, member: User) -> None:
    faculty = await db.get(Faculty, member.faculty_id) if member.faculty_id else None
    await message.answer(
        texts.PROFILE.format(
            first_name=html.escape(member.first_name),
            last_name=html.escape(member.last_name),
            faculty=html.escape(faculty.name) if faculty else texts.NO_FACULTY,
            course=member.course or "—",
            group=html.escape(member.group_name or "—"),
            registered=format_date(member.registered_at),
        ),
        reply_markup=keyboards.open_app(get_settings().webapp_url, keyboards.SECTION_ROUTES[texts.BTN_PROFILE]),
    )


@router.message(F.text.in_(texts.SECTION_HINTS.keys()))
async def section(message: Message) -> None:
    label = message.text or ""
    markup = keyboards.open_app(get_settings().webapp_url, keyboards.SECTION_ROUTES[label])
    await message.answer(texts.SECTION_HINTS[label] if markup else texts.APP_NOT_CONFIGURED, reply_markup=markup)


async def _notification_settings(db: AsyncSession, member: User) -> UserNotificationSettings:
    settings = await db.get(UserNotificationSettings, member.id)
    if settings is None:
        settings = UserNotificationSettings(user_id=member.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.message(F.text == texts.BTN_NOTIFICATIONS)
async def notifications(message: Message, db: AsyncSession, member: User) -> None:
    settings = await _notification_settings(db, member)
    await message.answer(texts.NOTIFICATIONS, reply_markup=keyboards.notification_settings(settings))


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
        await callback.message.edit_reply_markup(reply_markup=keyboards.notification_settings(settings))
