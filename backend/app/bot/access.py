"""Who may see what in the bot: administrators, and the menu without switched-off sections."""

from __future__ import annotations

from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, texts
from app.models import User
from app.security.permissions import Perm
from app.services.rbac import get_effective_permissions, get_role_codes, is_admin_role_set


async def is_admin(db: AsyncSession, member: User | None) -> bool:
    if member is None:
        return False
    return is_admin_role_set(await get_role_codes(db, member.id))


async def has_permission(db: AsyncSession, member: User | None, permission: Perm) -> bool:
    if member is None:
        return False
    roles = await get_role_codes(db, member.id)
    if not is_admin_role_set(roles):
        return False
    return permission.value in await get_effective_permissions(db, member.id, roles)


# Menu sections that the super admin can switch off (feature code per button).
SECTION_FEATURES = {
    texts.BTN_RANKING: "ranking",
    texts.BTN_ACHIEVEMENTS: "achievements",
    texts.BTN_PASSPORT: "passport",
}


async def menu(db: AsyncSession, member: User) -> ReplyKeyboardMarkup:
    """The main menu without the sections that are switched off."""
    from app.services import features

    access = await features.access(db, member)
    hidden = frozenset(label for label, code in SECTION_FEATURES.items() if access[code] == "off")
    return keyboards.main_menu(is_admin=await is_admin(db, member), hidden=hidden, premium=access["premium"] != "off")


async def gate(event: Message | CallbackQuery, db: AsyncSession, member: User, code: str) -> bool:
    """Answer kindly and return True when the member may not use a feature (off, or premium only)."""
    from app.services import features

    state = await features.allowed(db, member, code)
    if state == "on":
        return False
    feature = features.get_feature(code)
    if state == "off":
        text, markup = texts.FEATURE_OFF.format(title=feature.title), None
    else:
        text, markup = texts.FEATURE_PREMIUM.format(title=feature.title), keyboards.premium_offer()
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event
    if isinstance(message, Message):
        await message.answer(text, reply_markup=markup)
    return True


async def is_super_admin(db: AsyncSession, member: User | None) -> bool:
    return member is not None and "SUPER_ADMIN" in await get_role_codes(db, member.id)
