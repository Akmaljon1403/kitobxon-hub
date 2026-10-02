"""A fake Telegram connection so the real dispatcher and handlers can be tested end to end."""

from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import AnswerCallbackQuery, SendDocument, SendMessage, SendPhoto
from aiogram.methods.base import TelegramMethod
from aiogram.types import CallbackQuery, Chat, Contact, Message, PhotoSize, Update
from aiogram.types import User as TgUser

from app.bot.setup import create_dispatcher
from app.bot.storage import PostgresStorage

BOT_TOKEN = "123456789:TEST-bot-token-AAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_ids = itertools.count(1)


class FakeTelegramSession(BaseSession):
    """Records every Bot API call instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []

    async def close(self) -> None:
        return None

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield b""

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109 - aiogram API
        self.requests.append(method)
        if method.__returning__ is Message:
            return Message(
                message_id=next(_ids),
                date=datetime.now(UTC),
                chat=Chat(id=getattr(method, "chat_id", 0) or 0, type="private"),
                text=getattr(method, "text", None),
            )
        return True

    # ---- assertions helpers ----
    def sent_messages(self) -> list[SendMessage]:
        return [request for request in self.requests if isinstance(request, SendMessage)]

    def last_text(self) -> str:
        messages = self.sent_messages()
        return messages[-1].text if messages else ""

    def all_text(self) -> str:
        return "\n".join(message.text for message in self.sent_messages())

    def last_caption(self) -> str:
        """Caption of the last photo or file sent."""
        for request in reversed(self.requests):
            if isinstance(request, (SendPhoto, SendDocument)):
                return request.caption or ""
        return ""

    def alerts(self) -> list[str]:
        return [r.text or "" for r in self.requests if isinstance(r, AnswerCallbackQuery)]

    def clear(self) -> None:
        self.requests.clear()


class BotHarness:
    """Feeds updates from one simulated Telegram user into a real dispatcher."""

    def __init__(self, telegram_id: int, first_name: str = "Akmal", dispatcher: Dispatcher | None = None) -> None:
        self.session = FakeTelegramSession()
        self.bot = Bot(token=BOT_TOKEN, session=self.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dispatcher = dispatcher or create_dispatcher()
        self.user = TgUser(
            id=telegram_id, is_bot=False, first_name=first_name, username="akmal_reader", language_code="uz"
        )
        self.chat = Chat(id=telegram_id, type="private")

    def restart_server(self) -> None:
        """Simulate a server restart: a fresh storage object (conversation state must come from the database)."""
        self.dispatcher.fsm.storage = PostgresStorage()

    def _message(self, **fields: Any) -> Message:
        return Message(message_id=next(_ids), date=datetime.now(UTC), chat=self.chat, from_user=self.user, **fields)

    async def send(self, text: str) -> None:
        update = Update(update_id=next(_ids), message=self._message(text=text))
        await self.dispatcher.feed_update(self.bot, update)

    async def share_contact(self, phone: str, owner_id: int | None = None) -> None:
        contact = Contact(phone_number=phone, first_name=self.user.first_name, user_id=owner_id or self.user.id)
        update = Update(update_id=next(_ids), message=self._message(contact=contact))
        await self.dispatcher.feed_update(self.bot, update)

    async def send_photo(self, file_id: str, caption: str | None = None) -> None:
        photo = [PhotoSize(file_id=file_id, file_unique_id=f"u-{file_id}", width=800, height=600)]
        update = Update(update_id=next(_ids), message=self._message(photo=photo, caption=caption))
        await self.dispatcher.feed_update(self.bot, update)

    async def press(self, data: str) -> None:
        callback = CallbackQuery(
            id=str(next(_ids)),
            from_user=self.user,
            chat_instance="test",
            data=data,
            message=self._message(text="..."),
        )
        await self.dispatcher.feed_update(self.bot, Update(update_id=next(_ids), callback_query=callback))

    def last_text(self) -> str:
        return self.session.last_text()

    def all_text(self) -> str:
        return self.session.all_text()
