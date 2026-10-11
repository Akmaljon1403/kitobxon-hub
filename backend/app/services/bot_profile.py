"""The bot's Telegram profile: name, descriptions, the command menu, the avatar and default rights.

Everything the owners would otherwise do by hand in @BotFather is kept in settings (``bot.*``) and
applied by the bot itself — at start-up and whenever a ``bot.*`` setting changes:

* the name (empty setting — the name from @BotFather stays), the short description (profile page and
  shared links) and the description (the empty chat, «What can this bot do?»);
* the command menu: members see the members' commands; every administrator sees the admin commands
  too (in their own chat only); groups and channels see none;
* the default administrator rights suggested when the bot is added to a channel or a group, so the
  owners only press «Save»;
* the club's avatar (``app/brand/bot-avatar.*``) — once, when the bot has no profile photo, or with a
  button in the Admin Panel.

Telegram limits how often a profile may change, so a value is only sent when it differs from what
Telegram already shows.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    BufferedInputFile,
    ChatAdministratorRights,
    InputProfilePhotoStatic,
    MenuButtonWebApp,
    WebAppInfo,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Role, User, UserRole
from app.models.enums import UserStatus
from app.services.settings import get_setting

logger = logging.getLogger(__name__)

MEMBER_COMMANDS = [
    BotCommand(command="start", description="🏠 Bosh menyu"),
    BotCommand(command="davomat", description="✅ Tadbirda davomat qilish"),
    BotCommand(command="pasport", description="🪪 Kitobxon pasportim"),
    BotCommand(command="taklif", description="🤝 Do'stni klubga taklif qilish"),
    BotCommand(command="premium", description="💎 Premium va klubni qo'llab-quvvatlash"),
    BotCommand(command="help", description="❓ Yordam va adminga yozish"),
    BotCommand(command="paysupport", description="💳 To'lov bo'yicha yordam"),
    BotCommand(command="stop", description="⏹ Jarayonni to'xtatib, menyuga qaytish"),
]
ADMIN_COMMANDS = [BotCommand(command="admin", description="🛠 Admin panel")]
SENDER_COMMANDS = [
    BotCommand(command="stiker", description="🎨 Kanal postlari uchun stikerlar"),
    BotCommand(command="emoji", description="✨ Premium emojilarni yuklash"),
]

# Suggested when the owners add the bot as an administrator (they can still change them).
CHANNEL_RIGHTS = ChatAdministratorRights(
    is_anonymous=False,
    can_manage_chat=True,
    can_delete_messages=True,
    can_manage_video_chats=False,
    can_restrict_members=False,
    can_promote_members=False,
    can_change_info=False,
    can_invite_users=True,
    can_post_stories=False,
    can_edit_stories=False,
    can_delete_stories=False,
    can_send_welcome_messages=False,
    can_post_messages=True,
    can_edit_messages=True,
)
GROUP_RIGHTS = ChatAdministratorRights(
    is_anonymous=False,
    can_manage_chat=True,
    can_delete_messages=True,
    can_manage_video_chats=False,
    can_restrict_members=False,
    can_promote_members=False,
    can_change_info=False,
    can_invite_users=True,
    can_post_stories=False,
    can_edit_stories=False,
    can_delete_stories=False,
    can_send_welcome_messages=False,
    can_pin_messages=True,
)


async def _texts(session: AsyncSession) -> dict[str, str]:
    return {
        "name": str(await get_setting(session, "bot.name") or "").strip(),
        "short_description": str(await get_setting(session, "bot.short_description") or "").strip(),
        "description": str(await get_setting(session, "bot.description") or "").strip(),
        "menu_button": str(await get_setting(session, "bot.menu_button") or "").strip() or "📱 Ilova",
    }


async def apply_texts(bot: Bot, session: AsyncSession) -> list[str]:
    """Name and descriptions, each only when Telegram shows something else. Returns what changed."""
    wanted = await _texts(session)
    changed: list[str] = []
    if wanted["name"] and (await bot.get_my_name()).name != wanted["name"]:
        await bot.set_my_name(name=wanted["name"])
        changed.append("name")
    if (await bot.get_my_short_description()).short_description != wanted["short_description"]:
        await bot.set_my_short_description(short_description=wanted["short_description"])
        changed.append("short_description")
    if (await bot.get_my_description()).description != wanted["description"]:
        await bot.set_my_description(description=wanted["description"])
        changed.append("description")
    return changed


async def apply_menu_button(bot: Bot, session: AsyncSession, webapp_url: str | None) -> None:
    if webapp_url:
        text = (await _texts(session))["menu_button"]
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=text, web_app=WebAppInfo(url=webapp_url)))


async def _admins(session: AsyncSession) -> list[User]:
    from app.services.rbac import ADMIN_ROLES

    holders = select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code.in_(ADMIN_ROLES))
    return list(
        await session.scalars(
            select(User).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), User.id.in_(holders))
        )
    )


async def commands_for(session: AsyncSession, user: User) -> list[BotCommand] | None:
    """The menu of one person: None for a member (the members' menu applies)."""
    from app.bot.access import has_permission, is_admin
    from app.security.permissions import Perm

    if not await is_admin(session, user):
        return None
    commands = [*MEMBER_COMMANDS, *ADMIN_COMMANDS]
    if await has_permission(session, user, Perm.NOTIFICATION_SEND):
        commands += SENDER_COMMANDS
    return commands


async def apply_commands_for(bot: Bot, session: AsyncSession, user: User) -> None:
    """After roles change: the person's own menu (admin commands appear or disappear at once)."""
    scope = BotCommandScopeChat(chat_id=user.telegram_id)
    commands = await commands_for(session, user)
    if commands is None:
        await bot.delete_my_commands(scope=scope)
    else:
        await bot.set_my_commands(commands, scope=scope)


async def apply_commands(bot: Bot, session: AsyncSession) -> int:
    """Members' menu in private chats, nothing in groups and channels, the admin menu per admin."""
    await bot.set_my_commands(MEMBER_COMMANDS, scope=BotCommandScopeAllPrivateChats())
    await bot.delete_my_commands(scope=BotCommandScopeDefault())
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    admins = await _admins(session)
    for admin in admins:
        try:
            await apply_commands_for(bot, session, admin)
        except Exception:  # an admin who never opened the bot: Telegram does not know the chat yet
            logger.info("Admin commands could not be set for one administrator")
    return len(admins)


async def apply_rights(bot: Bot) -> None:
    await bot.set_my_default_administrator_rights(rights=CHANNEL_RIGHTS, for_channels=True)
    await bot.set_my_default_administrator_rights(rights=GROUP_RIGHTS, for_channels=False)


async def has_avatar(bot: Bot) -> bool:
    photos = await bot.get_user_profile_photos(bot.id, limit=1)
    return photos.total_count > 0


async def set_avatar(bot: Bot) -> bool:
    """The club's avatar (``app/brand/bot-avatar.*``) as the bot's profile photo. False when there is none."""
    from app.services import brand

    picture = brand.avatar_jpeg()
    if picture is None:
        return False
    photo = BufferedInputFile(picture, filename="avatar.jpg")
    await bot.set_my_profile_photo(photo=InputProfilePhotoStatic(photo=photo))
    return True


async def apply_all(bot: Bot, session: AsyncSession, webapp_url: str | None) -> dict[str, Any]:
    """Start-up: every part on its own, so one refusal from Telegram does not stop the rest."""
    result: dict[str, Any] = {}
    steps: list[tuple[str, Any]] = [
        ("texts", lambda: apply_texts(bot, session)),
        ("commands", lambda: apply_commands(bot, session)),
        ("menu_button", lambda: apply_menu_button(bot, session, webapp_url)),
        ("rights", lambda: apply_rights(bot)),
    ]
    for name, step in steps:
        try:
            result[name] = await step()
        except Exception as exc:
            logger.warning("Bot profile: %s could not be applied (%s)", name, type(exc).__name__)
            result[name] = "error"
    try:
        result["avatar"] = (await set_avatar(bot)) if not await has_avatar(bot) else "kept"
    except Exception as exc:
        logger.warning("Bot profile: the avatar could not be applied (%s)", type(exc).__name__)
        result["avatar"] = "error"
    return result


async def describe(bot: Bot | None, session: AsyncSession) -> dict[str, Any]:
    """For the Admin Panel: what is set here and what Telegram shows now."""
    wanted = await _texts(session)
    if bot is None:
        return {"wanted": wanted, "telegram": None, "username": None, "has_avatar": None, **_avatar_preview()}
    try:
        me = await bot.me()
        telegram = {
            "name": (await bot.get_my_name()).name,
            "short_description": (await bot.get_my_short_description()).short_description,
            "description": (await bot.get_my_description()).description,
        }
        avatar = await has_avatar(bot)
    except Exception:
        return {"wanted": wanted, "telegram": None, "username": None, "has_avatar": None, **_avatar_preview()}
    return {"wanted": wanted, "telegram": telegram, "username": me.username, "has_avatar": avatar, **_avatar_preview()}


def _avatar_preview() -> dict[str, str | None]:
    from app.services import brand

    return {"avatar_preview": brand.data_uri("bot-avatar", 160)}


async def refresh_person(session: AsyncSession, user_id: Any) -> None:
    """Best effort after a role change (the bot may be off in tests or during start-up)."""
    from app.services.delivery import optional_bot

    bot = optional_bot()
    user = await session.get(User, user_id)
    if bot is None or user is None:
        return
    try:
        await apply_commands_for(bot, session, user)
    except Exception:
        logger.info("The command menu of a changed administrator could not be updated")
