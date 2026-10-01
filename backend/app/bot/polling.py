"""Run the bot with long polling (local development, no public HTTPS address needed).

BOT_MODE=polling python -m app.bot.polling
"""

from __future__ import annotations

import asyncio

from app.bot.setup import configure_telegram, create_bot, create_dispatcher
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    if settings.bot_token is None:
        raise SystemExit("BOT_TOKEN is not set")
    bot = create_bot(settings.bot_token.get_secret_value())
    dispatcher = create_dispatcher()
    from app.bot.setup import BotRuntime

    await configure_telegram(BotRuntime(bot, dispatcher), with_webhook=False)
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
