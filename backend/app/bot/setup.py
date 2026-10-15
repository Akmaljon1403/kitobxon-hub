"""Creation of the Bot and Dispatcher, and Telegram-side configuration (commands, menu, webhook)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseEventIsolation
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.utils.token import TokenValidationError, validate_token

from app.bot.errors import on_error
from app.bot.handlers import (
    admin,
    campaigns,
    chats,
    common,
    community,
    events,
    fallback,
    feedback,
    membership,
    payments,
    reading,
    registration,
    sections,
    support,
)
from app.bot.middlewares import (
    DbSessionMiddleware,
    FloodMiddleware,
    GroupMiddleware,
    LicenceMiddleware,
    MemberMiddleware,
    SubscriptionMiddleware,
)
from app.bot.storage import PostgresStorage
from app.core.config import Settings, get_settings
from app.security.crypto import derive_key

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/telegram/webhook"


def webhook_secret(settings: Settings | None = None) -> str:
    """Secret Telegram sends back in every webhook call (derived from SECRET_KEY if not set)."""
    settings = settings or get_settings()
    if settings.telegram_webhook_secret:
        return settings.telegram_webhook_secret.get_secret_value()
    return hashlib.sha256(derive_key("telegram-webhook")).hexdigest()


_dispatcher: Dispatcher | None = None


def create_dispatcher() -> Dispatcher:
    """The process-wide dispatcher (aiogram routers can be attached to only one dispatcher)."""
    global _dispatcher
    if _dispatcher is not None:
        return _dispatcher
    # Updates of one user are processed one at a time (e.g. a double tap on "Confirm").
    isolation: BaseEventIsolation = SimpleEventIsolation()
    dispatcher = Dispatcher(storage=PostgresStorage(), events_isolation=isolation)
    dispatcher.update.outer_middleware(FloodMiddleware())
    dispatcher.update.outer_middleware(DbSessionMiddleware())
    dispatcher.update.outer_middleware(MemberMiddleware())
    # In the payments group only the admins' payment buttons work; members must be subscribed to the
    # club channel(s) — both are checked before any handler runs.
    dispatcher.message.outer_middleware(GroupMiddleware())
    dispatcher.callback_query.outer_middleware(GroupMiddleware())
    dispatcher.message.outer_middleware(LicenceMiddleware())
    dispatcher.callback_query.outer_middleware(LicenceMiddleware())
    dispatcher.message.outer_middleware(SubscriptionMiddleware())
    dispatcher.callback_query.outer_middleware(SubscriptionMiddleware())
    # Order matters: free-text handlers (support messages) come after the menu buttons.
    # The chats router first: an admin's answer in the payments group is never a member's message. Then
    # payments: Telegram's payment updates must never be taken by a waiting-for-text state.
    dispatcher.include_routers(
        chats.router,
        payments.router,
        membership.router,
        registration.router,
        events.router,
        common.router,
        admin.router,
        sections.router,
        reading.router,
        community.router,
        campaigns.router,
        feedback.router,
        support.router,
        fallback.router,
    )
    dispatcher.errors.register(on_error)
    _dispatcher = dispatcher
    return dispatcher


def create_bot(token: str) -> Bot:
    from app.bot.emoji import CustomEmojiMiddleware

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    bot.session.middleware(CustomEmojiMiddleware())  # the club's premium emoji in every message
    return bot


@dataclass
class BotRuntime:
    bot: Bot
    dispatcher: Dispatcher
    username: str | None = None  # detected from Telegram (getMe) on start-up


_runtime: BotRuntime | None = None


def get_bot_runtime() -> BotRuntime | None:
    """The process-wide bot, or None when the bot is disabled or not configured."""
    global _runtime
    settings = get_settings()
    if not settings.bot_enabled or settings.bot_token is None:
        return None
    if _runtime is None:
        token = settings.bot_token.get_secret_value()
        if not bot_token_is_valid(token):
            return None  # reported once by bot_token_is_valid; the API keeps running without the bot
        _runtime = BotRuntime(create_bot(token), create_dispatcher())
    return _runtime


_reported_invalid_token = False


def bot_token_is_valid(token: str) -> bool:
    """BotFather tokens look like ``123456789:AA...``; anything else would crash aiogram."""
    global _reported_invalid_token
    try:
        validate_token(token)
    except TokenValidationError:
        if not _reported_invalid_token:
            logger.error("BOT_TOKEN is not a valid Telegram bot token; the bot is disabled until it is fixed")
            _reported_invalid_token = True
        return False
    return True


async def close_bot_runtime() -> None:
    global _runtime
    if _runtime is not None:
        await _runtime.bot.session.close()
    _runtime = None


async def configure_telegram(runtime: BotRuntime, *, with_webhook: bool) -> None:
    """Register commands, the Mini App menu button and (in webhook mode) the webhook URL."""
    settings = get_settings()
    bot = runtime.bot
    me = await bot.me()
    runtime.username = me.username
    remember_username(me.username)
    await _apply_profile(bot, settings.webapp_url)
    if with_webhook:
        if not settings.base_url:
            logger.warning("BOT_MODE=webhook but PUBLIC_BASE_URL is not set; the webhook was not registered")
            return
        await bot.set_webhook(
            url=f"{settings.base_url}{WEBHOOK_PATH}",
            secret_token=webhook_secret(settings),
            allowed_updates=runtime.dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info("Telegram webhook registered")


async def _apply_profile(bot: Bot, webapp_url: str | None) -> None:
    """Name, descriptions, command menus, default rights and the avatar (see services/bot_profile.py)."""
    from app.core.database import get_session_factory
    from app.services import bot_profile

    try:
        async with get_session_factory()() as session:
            result = await bot_profile.apply_all(bot, session, webapp_url)
        logger.info("Bot profile applied: %s", result)
    except Exception:
        logger.exception("The bot profile could not be applied; the bot keeps working")


_detected_username: str | None = None  # learnt from Telegram in this process (webhook, polling or worker)


def remember_username(username: str | None) -> None:
    global _detected_username
    if username:
        _detected_username = username


def bot_username() -> str | None:
    """BOT_USERNAME if configured, otherwise the username detected from Telegram in this process."""
    configured = get_settings().bot_username
    if configured:
        return configured
    if _runtime is not None and _runtime.username:
        return _runtime.username
    return _detected_username


async def resolve_bot_username(bot: Bot | None = None) -> str | None:
    """The bot's username, asking Telegram (getMe) once when it is neither configured nor known yet:
    links such as the personal invitation link must work without BOT_USERNAME in the environment."""
    known = bot_username()
    if known:
        return known
    if bot is None:
        runtime = get_bot_runtime()
        bot = runtime.bot if runtime is not None else None
    if bot is None:
        return None
    try:
        username = (await bot.me()).username
    except Exception:
        logger.warning("Could not ask Telegram for the bot's username", exc_info=True)
        return None
    remember_username(username)
    return username
