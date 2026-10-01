"""Turns exceptions raised by handlers into friendly Uzbek replies."""

from __future__ import annotations

import logging

from aiogram.types import ErrorEvent

from app.bot import texts
from app.core.errors import AppError

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    exception = event.exception
    if isinstance(exception, AppError):
        reply = exception.message
    else:
        logger.error("Unhandled bot error", exc_info=exception)
        reply = texts.UNEXPECTED_ERROR

    update = event.update
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(reply[:200], show_alert=True)
        elif update.message is not None:
            await update.message.answer(reply)
    except Exception:  # the reply itself failed (e.g. user blocked the bot); nothing else to do
        logger.warning("Could not deliver error message to the user")
    return True
