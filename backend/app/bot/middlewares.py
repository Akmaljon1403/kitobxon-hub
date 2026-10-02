"""Update-level middlewares: database session, the sender's member account, flood protection."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TelegramUser
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import RateLimitedError
from app.models import User
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
