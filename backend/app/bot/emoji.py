"""Every message the bot sends goes through here: ordinary emoji become the club's premium ones
(see ``app.services.custom_emoji``). If Telegram refuses, the message is sent as it was."""

from __future__ import annotations

from typing import Any

from aiogram import Bot
from aiogram.client.default import Default
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    EditMessageCaption,
    EditMessageText,
    SendAnimation,
    SendAudio,
    SendDocument,
    SendMessage,
    SendPhoto,
    SendVideo,
    SendVoice,
)
from aiogram.methods.base import TelegramMethod

from app.services import custom_emoji

TEXT_METHODS = (SendMessage, EditMessageText)
CAPTION_METHODS = (SendPhoto, SendDocument, SendVideo, SendAnimation, SendAudio, SendVoice, EditMessageCaption)


def _is_html(bot: Bot, method: Any) -> bool:
    mode = getattr(method, "parse_mode", None)
    if isinstance(mode, Default):
        mode = bot.default[mode.name]
    return str(getattr(mode, "value", mode) or "").upper() == "HTML"


class CustomEmojiMiddleware(BaseRequestMiddleware):
    async def __call__(
        self, make_request: NextRequestMiddlewareType[Any], bot: Bot, method: TelegramMethod[Any]
    ) -> Any:
        if isinstance(method, TEXT_METHODS):
            field = "text"
        elif isinstance(method, CAPTION_METHODS):
            field = "caption"
        else:
            return await make_request(bot, method)
        original = getattr(method, field, None)
        if not isinstance(original, str) or not original or not _is_html(bot, method):
            return await make_request(bot, method)
        await custom_emoji.refresh_if_stale()
        rewritten = custom_emoji.apply(original)
        if rewritten == original:
            return await make_request(bot, method)
        setattr(method, field, rewritten)
        try:
            return await make_request(bot, method)
        except TelegramBadRequest:
            # Most likely the bot may not use custom emoji (no Fragment username): send it as it was.
            setattr(method, field, original)
            response = await make_request(bot, method)
            custom_emoji.pause()
            return response
