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
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from app.bot import texts
from app.bot.errors import on_error
from app.bot.handlers import common, fallback, menu, registration
from app.bot.middlewares import DbSessionMiddleware, FloodMiddleware, MemberMiddleware
from app.bot.storage import PostgresStorage
from app.core.config import Settings, get_settings
from app.security.crypto import derive_key

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/telegram/webhook"

COMMANDS = [
    BotCommand(command="start", description="Bosh menyu / ro'yxatdan o'tish"),
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="myid", description="Telegram ID raqamim"),
    BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
]


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
    dispatcher.include_routers(registration.router, common.router, menu.router, fallback.router)
    dispatcher.errors.register(on_error)
    _dispatcher = dispatcher
    return dispatcher


def create_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


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
        _runtime = BotRuntime(create_bot(settings.bot_token.get_secret_value()), create_dispatcher())
    return _runtime


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
    await bot.set_my_commands(COMMANDS)
    await bot.set_my_short_description(short_description=texts.BOT_SHORT_DESCRIPTION)
    await bot.set_my_description(description=texts.BOT_DESCRIPTION)
    if settings.webapp_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="📚 Kitobxon Hub", web_app=WebAppInfo(url=settings.webapp_url))
        )
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


def bot_username() -> str | None:
    """BOT_USERNAME if configured, otherwise the username detected from Telegram on start-up."""
    configured = get_settings().bot_username
    if configured:
        return configured
    return _runtime.username if _runtime is not None else None
