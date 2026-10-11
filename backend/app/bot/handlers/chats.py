"""Channels and groups the bot is added to: the owners say what each one is for.

When the bot becomes an administrator of a channel or a group, every super administrator gets a
private message: «💳 To'lovlar kanali» (receipts, payment questions, Stars payments), «📣 Klub
kanali» (the bot's posts) or «Hech biri». No settings to type, no chat ids to look up. When the bot
is removed from the payments channel, the owners are told (receipts then come to them in the bot).
"""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import access, texts
from app.models import User
from app.models.enums import NotificationType
from app.services.notifications import enqueue_for_members
from app.services.settings import get_setting, update_setting

router = Router(name="chats")

ROLES = {"pay": "payments.chat_id", "club": "channel.chat_id"}
ADMIN = {"administrator", "creator"}
GONE = {"left", "kicked"}


def _same_chat(setting: str, chat_id: int, username: str | None) -> bool:
    value = setting.strip().lstrip("@").lower()
    return bool(value) and (value == str(chat_id) or (username is not None and value == username.lower()))


@router.my_chat_member(F.chat.type.in_({"channel", "group", "supergroup"}))
async def bot_rights_changed(update: ChatMemberUpdated, db: AsyncSession) -> None:
    from app.services.rbac import super_admins

    chat = update.chat
    title = html.escape(chat.title or str(chat.id), quote=False)
    new, old = update.new_chat_member.status, update.old_chat_member.status
    if new in ADMIN and old not in ADMIN:
        await enqueue_for_members(
            db,
            type_=NotificationType.SYSTEM,
            text=texts.CHAT_ROLE_ASK.format(title=title),
            dedup_prefix=f"chat-role:{chat.id}:{update.date.timestamp():.0f}",
            members=super_admins(),
            payload={
                "buttons": [
                    {"text": texts.BTN_CHAT_PAYMENTS, "callback": f"chatrole:pay:{chat.id}"},
                    {"text": texts.BTN_CHAT_CLUB, "callback": f"chatrole:club:{chat.id}"},
                    {"text": texts.BTN_CHAT_NONE, "callback": f"chatrole:none:{chat.id}"},
                ]
            },
            priority=1,
        )
        await db.commit()
    elif new in GONE or (old in ADMIN and new not in ADMIN):
        payments = str(await get_setting(db, "payments.chat_id") or "")
        if _same_chat(payments, chat.id, chat.username):
            await enqueue_for_members(
                db,
                type_=NotificationType.SYSTEM,
                text=texts.CHAT_PAYMENTS_LOST.format(title=title),
                dedup_prefix=f"chat-lost:{chat.id}:{update.date.timestamp():.0f}",
                members=super_admins(),
                priority=1,
            )
            await db.commit()


@router.callback_query(F.data.startswith("chatrole:"))
async def choose_role(callback: CallbackQuery, db: AsyncSession, member: User | None, bot: Bot) -> None:
    if not await access.is_super_admin(db, member):
        await callback.answer(texts.CARD_ADMIN_ONLY, show_alert=True)
        return
    assert member is not None
    _, role, chat_id = (callback.data or "").split(":", 2)
    if role not in ROLES:
        await callback.answer(texts.CHAT_ROLE_NONE)
        if isinstance(callback.message, Message):
            await callback.message.edit_reply_markup(reply_markup=None)
        return
    try:
        chat = await bot.get_chat(int(chat_id))
    except Exception:
        await callback.answer(texts.CHAT_ROLE_UNREACHABLE, show_alert=True)
        return
    await update_setting(db, key=ROLES[role], value=str(chat.id), actor_id=member.id)
    title = html.escape(chat.title or str(chat.id), quote=False)
    done = (texts.CHAT_ROLE_PAYMENTS_DONE if role == "pay" else texts.CHAT_ROLE_CLUB_DONE).format(title=title)
    await callback.answer("✅")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(done)
    if role == "pay":
        from app.services import payments_chat

        await payments_chat.send_test(db)
