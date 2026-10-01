"""HTTP endpoint that receives updates from Telegram (webhook mode)."""

from __future__ import annotations

import asyncio
import logging

from aiogram.types import Update
from fastapi import APIRouter, Request, Response

from app.bot.setup import WEBHOOK_PATH, get_bot_runtime, webhook_secret
from app.core.errors import NotFoundError, UnauthorizedError
from app.security.crypto import constant_time_equals

logger = logging.getLogger(__name__)
router = APIRouter(include_in_schema=False)

_PROCESSING_TIMEOUT_SECONDS = 50  # Telegram waits ~60 s before retrying


@router.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request) -> Response:
    runtime = get_bot_runtime()
    if runtime is None:
        raise NotFoundError()
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not constant_time_equals(received, webhook_secret()):
        raise UnauthorizedError("WEBHOOK_SECRET_INVALID", "Noto'g'ri so'rov.")

    payload = await request.json()
    update = Update.model_validate(payload, context={"bot": runtime.bot})
    try:
        await asyncio.wait_for(runtime.dispatcher.feed_update(runtime.bot, update), timeout=_PROCESSING_TIMEOUT_SECONDS)
    except Exception:
        # Answer 200 anyway: otherwise Telegram re-sends the same update again and again.
        logger.exception("Failed to process Telegram update")
    return Response(status_code=200)
