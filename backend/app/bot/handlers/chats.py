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


# ---------------------------------------------------------------------------- answers in the payments chat


async def _answer_in_payments_chat(message: Message, db: AsyncSession, bot: Bot, actor: User | None) -> None:
    """An admin replied in the payments chat to a payment question, a receipt or a Stars payment line:
    the words go to that member (in their conversation with the club), and the reply gets a 👍."""
    import contextlib

    from aiogram.types import ReactionTypeEmoji

    from app.core.errors import AppError
    from app.services import card_payments, payments_chat, support

    reply = message.reply_to_message
    if reply is None or not payments_chat.same_chat(await payments_chat.chat_id(db), message.chat):
        return
    link = await payments_chat.find_link(db, message.chat.id, reply.message_id)
    if link is None:
        return
    text = (message.text or message.caption or "").strip()
    if not text or text.startswith("/"):
        if not text:
            await message.reply(texts.PAYCHAT_TEXT_ONLY)
        return
    actor_id = actor.id if actor else None
    try:
        if link.kind == "ticket":
            await support.admin_reply(
                db, actor_id=actor_id, ticket_id=link.target_id, text=text, payment=True, echo=False
            )
        else:
            about = texts.PAYCHAT_ABOUT_USER
            if link.kind == "card":
                payment = await db.get(card_payments.CardPayment, link.target_id)
                if payment is not None:
                    about = texts.PAYCHAT_ABOUT_CARD.format(
                        what=html.unescape(await card_payments._what(db, payment)),
                        amount=card_payments.format_uzs(payment.amount_uzs),
                    )
            await support.club_message(db, actor_id=actor_id, user_id=link.user_id, text=text, about=about)
    except AppError as exc:
        await message.reply(texts.PAYCHAT_FAILED.format(reason=html.escape(exc.message or "xatolik")))
        return
    member = await db.get(User, link.user_id)
    name = html.escape(member.full_name if member else "—")
    try:
        await bot.set_message_reaction(message.chat.id, message.message_id, [ReactionTypeEmoji(emoji="👍")])
    except Exception:  # reactions may be off in the channel: say it in words
        with contextlib.suppress(Exception):
            await message.reply(texts.PAYCHAT_SENT.format(name=name))


@router.channel_post(F.reply_to_message)
async def channel_answer(message: Message, db: AsyncSession, bot: Bot) -> None:
    """In a channel only its administrators can post, so a reply there is the club's answer."""
    await _answer_in_payments_chat(message, db, bot, None)


@router.message(F.chat.type.in_({"group", "supergroup"}), F.reply_to_message)
async def group_answer(message: Message, db: AsyncSession, bot: Bot, member: User | None) -> None:
    """In a payments group anyone may write: only the super administrators' replies reach members."""
    from app.services import payments_chat

    if not payments_chat.same_chat(await payments_chat.chat_id(db), message.chat):
        return
    if not await access.is_super_admin(db, member):
        if message.reply_to_message and await payments_chat.find_link(
            db, message.chat.id, message.reply_to_message.message_id
        ):
            await message.reply(texts.PAYCHAT_SUPER_ONLY)
        return
    await _answer_in_payments_chat(message, db, bot, member)


# ---------------------------------------------------------------------------- «what is this channel's id?»


@router.message(F.chat.type == "private", F.forward_origin)
async def forwarded_from_a_chat(message: Message, db: AsyncSession, member: User | None) -> None:
    """An admin forwards a post from a channel: the bot tells its id (the «-100…» number for the settings).
    Members' forwards go on to the other handlers (e.g. a question to the admins)."""
    from aiogram.dispatcher.event.bases import SkipHandler
    from aiogram.types import MessageOriginChannel, MessageOriginChat

    if not await access.is_admin(db, member):
        raise SkipHandler
    origin = message.forward_origin
    chat = origin.chat if isinstance(origin, MessageOriginChannel | MessageOriginChat) else None
    if chat is None:
        await message.answer(texts.CHAT_ID_HIDDEN)
        return
    await message.answer(
        texts.CHAT_ID_INFO.format(
            title=html.escape(chat.title or str(chat.id), quote=False),
            chat_id=chat.id,
            username=texts.CHAT_ID_USERNAME.format(username=chat.username) if chat.username else "",
        )
    )
