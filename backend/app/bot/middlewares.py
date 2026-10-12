"""Update-level middlewares: database session, the sender's member account, flood protection, and the
required channel subscription."""

from __future__ import annotations

import html
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TelegramUser
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import RateLimitedError
from app.models import User
from app.models.enums import UserStatus
from app.security.rate_limit import RateLimit, enforce
from app.services.rbac import ensure_bootstrap_super_admin

logger = logging.getLogger(__name__)

BOT_FLOOD_LIMIT = RateLimit("bot-updates", limit=40, window_seconds=60)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]


class DbSessionMiddleware(BaseMiddleware):
    """One database session per update, available to handlers as ``db``."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        async with get_session_factory()() as session:
            data["db"] = session
            try:
                return await handler(event, data)
            finally:
                await session.rollback()  # anything a handler did not commit is discarded


class MemberMiddleware(BaseMiddleware):
    """Loads the member account of the sender (``member`` is None for unregistered people)."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        telegram_user: TelegramUser | None = data.get("event_from_user")
        member = None
        if telegram_user is not None:
            db = data["db"]
            member = await db.scalar(
                select(User).where(User.telegram_id == telegram_user.id, User.deleted_at.is_(None))
            )
            # Owners listed in SUPER_ADMIN_TELEGRAM_IDS get their role on the next message, without
            # having to open the Mini App first.
            if member is not None and member.telegram_id in get_settings().super_admin_telegram_ids:
                if await ensure_bootstrap_super_admin(db, member):
                    await db.commit()
            if member is not None:
                from app.services import lifecycle

                # Made «faol emas» automatically after a long break: they are back, so they are active again.
                if await lifecycle.wake_up(db, member):
                    data["woke_up"] = True
                elif await lifecycle.touch(db, member):
                    await db.commit()
        data["member"] = member
        return await handler(event, data)


class FloodMiddleware(BaseMiddleware):
    """Silently drops updates from a user who sends far too many in a short time."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        telegram_user: TelegramUser | None = data.get("event_from_user")
        if telegram_user is not None:
            try:
                await enforce(BOT_FLOOD_LIMIT, str(telegram_user.id))
            except RateLimitedError:
                logger.warning("Bot flood limit reached", extra={"telegram_user": "redacted"})
                return None
        return await handler(event, data)


class LicenceMiddleware(BaseMiddleware):
    """A rented copy whose licence ended: members get one polite line; administrators carry on."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        from app.bot import access
        from app.core import licence

        if not licence.status().blocks_members:
            return await handler(event, data)
        if isinstance(event, Message):
            if event.chat.type != "private" or event.successful_payment is not None:
                return await handler(event, data)
        elif not isinstance(event, CallbackQuery):
            return await handler(event, data)
        if await access.is_admin(data["db"], data.get("member")):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer(licence.MEMBER_MESSAGE[:200], show_alert=True)
        else:
            await event.answer(licence.MEMBER_MESSAGE)
        return None


CHECK = "sub:check"

# Buttons the bot answers in groups and channels (the payments chat): payment decisions and replies to
# payment questions. Everything else there is ignored, so the bot never chats in a group.
GROUP_CALLBACKS = ("cp:", "sup:ans:", "sup:pay:", "sup:full:", "sup:close:")


class GroupMiddleware(BaseMiddleware):
    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        if isinstance(event, Message):
            if event.chat.type == "private":
                return await handler(event, data)
            if event.reply_to_message is not None and event.chat.type in ("group", "supergroup"):
                return await handler(event, data)  # maybe an answer in the payments group (checked there)
            return None
        if isinstance(event, CallbackQuery):
            chat = event.message.chat if event.message is not None else None
            if chat is None or chat.type == "private" or (event.data or "").startswith(GROUP_CALLBACKS):
                return await handler(event, data)
            await event.answer()
            return None
        return await handler(event, data)


class SubscriptionMiddleware(BaseMiddleware):
    """Members use the bot only while subscribed to the required channel(s).

    Registered on messages and button presses in private chats. Administrators, payments and members
    whose account is not active (they have their own messages) pass through. «✅ Obuna bo'ldim»
    checks again and continues where the person stopped (e.g. a /start link from a channel post).
    """

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        from app.bot import access
        from app.services import subscription

        if isinstance(event, Message):
            chat, sender = event.chat, event.from_user
            if event.successful_payment is not None or event.refunded_payment is not None:
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            chat = event.message.chat if event.message is not None else None
            sender = event.from_user
        else:
            return await handler(event, data)
        if chat is None or chat.type != "private" or sender is None:
            return await handler(event, data)
        db = data["db"]
        member: User | None = data.get("member")
        if member is not None and member.status != UserStatus.ACTIVE:
            return await handler(event, data)
        is_check = isinstance(event, CallbackQuery) and (event.data or "").startswith(CHECK)
        channels = await subscription.missing(db, sender.id, bot=data.get("bot"), fresh=is_check)
        if channels and await access.is_admin(db, member):
            channels = []
        if not channels:
            if is_check:
                assert isinstance(event, CallbackQuery)
                await self._resume(event, data)
                return None
            return await handler(event, data)
        if is_check:
            assert isinstance(event, CallbackQuery)
            names = ", ".join(channel.title for channel in channels)
            await event.answer(texts_module().SUBSCRIBE_STILL_MISSING.format(channels=names)[:200], show_alert=True)
            return None
        await self._ask(event, channels)
        return None

    @staticmethod
    async def _ask(event: Message | CallbackQuery, channels: list[Any]) -> None:
        from app.bot import keyboards

        payload = ""
        if isinstance(event, Message) and (event.text or "").startswith("/start "):
            payload = (event.text or "").split(maxsplit=1)[1].strip()
        check = f"{CHECK}:{payload}" if payload and len(payload) <= 52 else CHECK
        markup = keyboards.subscribe([(html.escape(channel.title), channel.url) for channel in channels], check)
        texts = texts_module()
        if isinstance(event, CallbackQuery):
            await event.answer()
            if isinstance(event.message, Message):
                await event.message.answer(texts.SUBSCRIBE_REQUIRED, reply_markup=markup)
        else:
            await event.answer(texts.SUBSCRIBE_REQUIRED, reply_markup=markup)

    @staticmethod
    async def _resume(callback: CallbackQuery, data: dict[str, Any]) -> None:
        from app.bot.handlers.registration import handle_start

        texts = texts_module()
        await callback.answer("✅")
        if not isinstance(callback.message, Message):
            return
        try:
            await callback.message.edit_text(texts.SUBSCRIBE_THANKS)
        except Exception:  # an old message that can no longer be edited
            await callback.message.answer(texts.SUBSCRIBE_THANKS)
        payload = (callback.data or "").removeprefix(CHECK).removeprefix(":")
        await handle_start(callback.message, data["state"], data["db"], data.get("member"), payload)


def texts_module() -> Any:
    from app.bot import texts

    return texts
