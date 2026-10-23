"""Required channel subscription: members use the bot and the Mini App only while subscribed.

The super admin lists the channels (by default the club channel). The bot asks Telegram
(``getChatMember``) whether the member is in each of them; for that the bot must be an
administrator of every listed channel. Answers are cached for a few minutes, so the check is
repeated regularly ("doimiy") without asking Telegram on every message.

Administrators are never asked to subscribe. When Telegram cannot answer (the bot is not an
administrator there, a network problem) the member is let through: a wrong setting must never
lock everybody out of the club.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings import get_setting

logger = logging.getLogger(__name__)

OK_SECONDS = 10 * 60  # a subscribed member is checked again after 10 minutes
MISSING_SECONDS = 20  # someone who has just subscribed should not wait long
TITLE_SECONDS = 6 * 60 * 60
MAX_CACHE = 50_000

_SPLIT = re.compile(r"[\s,;]+")
_LINK = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?P<name>[A-Za-z0-9_]{4,64})/?$")
_NAME = re.compile(r"^@(?P<name>[A-Za-z][A-Za-z0-9_]{3,63})$")
_PRIVATE = re.compile(r"^(?P<id>-100\d{5,20})=(?P<url>https://t\.me/\S+)$")


@dataclass(frozen=True)
class Channel:
    chat_id: str  # "@name" or "-100..."
    url: str
    title: str


_checked: dict[int, tuple[float, tuple[Channel, ...]]] = {}
_titles: dict[str, tuple[float, str]] = {}


def parse(text: str) -> list[tuple[str, str]]:
    """(chat id, link) pairs from the setting: «@name», «https://t.me/name» or «-100…=https://t.me/+invite»."""
    result: list[tuple[str, str]] = []
    for item in _SPLIT.split(text.strip()):
        if not item:
            continue
        if match := _PRIVATE.match(item):
            pair = (match["id"], match["url"])
        elif match := _LINK.match(item) or _NAME.match(item):
            pair = (f"@{match['name']}", f"https://t.me/{match['name']}")
        else:
            continue
        if pair[0].lower() not in {chat.lower() for chat, _ in result}:
            result.append(pair)
    return result[:5]


async def configured(session: AsyncSession) -> list[tuple[str, str]]:
    """The channels a member must join (empty when the rule is off)."""
    if not await get_setting(session, "subscription.required"):
        return []
    listed = parse(str(await get_setting(session, "subscription.channels")))
    if listed:
        return listed
    return parse(str(await get_setting(session, "channel.chat_id")))


def _bot() -> Any:
    from app.bot.setup import get_bot_runtime

    runtime = get_bot_runtime()
    return runtime.bot if runtime is not None else None


async def _title(bot: Any, chat_id: str, fallback: str) -> str:
    cached = _titles.get(chat_id)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    title = fallback
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or fallback
    except Exception:  # the link still works without a nice title
        logger.info("Channel title is not available")
    _titles[chat_id] = (time.monotonic() + TITLE_SECONDS, title)
    return title


def _status(member: Any) -> str:
    status = getattr(member, "status", "")
    return str(getattr(status, "value", status))


def _subscribed(member: Any) -> bool:
    status = _status(member)
    if status in {"creator", "administrator", "member"}:
        return True
    return status == "restricted" and bool(getattr(member, "is_member", False))


async def missing(session: AsyncSession, telegram_id: int, *, bot: Any = None, fresh: bool = False) -> list[Channel]:
    """The required channels this person has not joined (empty: all good, or the rule is off)."""
    channels = await configured(session)
    if not channels:
        return []
    bot = bot or _bot()
    if bot is None:
        return []
    now = time.monotonic()
    cached = _checked.get(telegram_id)
    if cached and cached[0] > now and not fresh:
        return list(cached[1])

    async def _check(chat_id: str, url: str) -> Channel | None:
        try:
            member = await bot.get_chat_member(chat_id, telegram_id)
        except Exception:
            # Not an administrator of that channel, or Telegram is unreachable: let the member in.
            logger.warning("Subscription could not be checked in a required channel")
            return None
        if _subscribed(member):
            return None
        fallback = chat_id if chat_id.startswith("@") else "Kanal"
        return Channel(chat_id=chat_id, url=url, title=await _title(bot, chat_id, fallback))

    # Ask Telegram about every required channel at once rather than one after another: this gate runs
    # on each bot message and each Mini App request, so a member with several channels no longer waits
    # for N sequential round-trips. gather keeps the configured order.
    checked = await asyncio.gather(*(_check(chat_id, url) for chat_id, url in channels))
    result: list[Channel] = [channel for channel in checked if channel is not None]
    if len(_checked) > MAX_CACHE:
        for key in [key for key, (expires, _) in _checked.items() if expires <= now]:
            _checked.pop(key, None)
        if len(_checked) > MAX_CACHE:
            _checked.clear()
    _checked[telegram_id] = (now + (MISSING_SECONDS if result else OK_SECONDS), tuple(result))
    return result


def forget(telegram_id: int | None = None) -> None:
    """Drop cached answers (one person, or everybody after the channel list changed)."""
    if telegram_id is None:
        _checked.clear()
    else:
        _checked.pop(telegram_id, None)


def as_dicts(channels: list[Channel]) -> list[dict[str, str]]:
    return [{"title": channel.title, "url": channel.url} for channel in channels]


async def check_bot_rights(session: AsyncSession) -> list[dict[str, Any]]:
    """For the admins: can the bot check members in each listed channel?"""
    bot = _bot()
    result = []
    for chat_id, url in parse(str(await get_setting(session, "subscription.channels"))) or parse(
        str(await get_setting(session, "channel.chat_id"))
    ):
        ok, problem = False, "Bot ishlamayapti."
        if bot is not None:
            try:
                me = await bot.get_me()
                member = await bot.get_chat_member(chat_id, me.id)
                ok = _status(member) in {"administrator", "creator"}
                problem = "" if ok else "Bot bu kanalda administrator emas."
            except Exception:
                problem = "Kanal topilmadi yoki bot unga qo'shilmagan."
        result.append({"chat_id": chat_id, "url": url, "ok": ok, "problem": problem})
    return result
