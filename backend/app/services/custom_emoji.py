"""Premium (custom) emoji inside the bot's messages: «Salom ✋» goes out with the club's premium ✋.

An admin sends premium emoji to the bot with /emoji. Each one replaces an ordinary emoji: the one
written right before it («✋ = <premium>»), or else the emoji Telegram shows for it by default.
Every message the bot sends (HTML) is then rewritten: the ordinary emoji becomes
``<tg-emoji emoji-id="…">✋</tg-emoji>``.

Telegram lets bots use custom emoji only when the bot has an extra username bought on Fragment.
If Telegram refuses such a message, it is sent again with ordinary emoji and the replacement pauses
for an hour — members always get their messages.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CustomEmoji

logger = logging.getLogger(__name__)

VARIATION = "️"
RELOAD_SECONDS = 60
PAUSE_SECONDS = 60 * 60
MAX_EMOJI = 200
_SEPARATORS = " \t\n=:→->—–,;"
# Inside these tags nothing is replaced (code, links' own markup, existing custom emoji).
_SKIP_TAGS = {"code", "pre", "tg-emoji"}
_TAG = re.compile(r"(<[^>]+>)")
_TAG_NAME = re.compile(r"^</?\s*([a-zA-Z-]+)")

_mapping: dict[str, tuple[str, str]] = {}  # emoji (no U+FE0F) -> (custom emoji id, fallback)
_pattern: re.Pattern[str] | None = None
_loaded_at = 0.0
_paused_until = 0.0


def normalize(emoji: str) -> str:
    return emoji.replace(VARIATION, "").strip()


def _is_emoji(text: str) -> bool:
    """A short run of symbols (no letters or digits): one emoji, maybe with a skin tone or ZWJ parts."""
    return 0 < len(text) <= 8 and not any(char.isalnum() for char in text.replace(VARIATION, ""))


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def _slice(encoded: bytes, start: int, end: int) -> str:
    """Telegram counts entity offsets in UTF-16 code units."""
    return encoded[start * 2 : end * 2].decode("utf-16-le", errors="ignore")


def pairs_from_message(text: str, entities: list[Any]) -> list[tuple[str, str, str]]:
    """(ordinary emoji, custom emoji id, fallback) for each premium emoji in an admin's message."""
    encoded = _utf16(text or "")
    result: list[tuple[str, str, str]] = []
    previous_end = 0
    for entity in sorted(entities or [], key=lambda item: item.offset):
        if getattr(entity, "type", None) != "custom_emoji" or not getattr(entity, "custom_emoji_id", None):
            continue
        fallback = _slice(encoded, entity.offset, entity.offset + entity.length)
        before = _slice(encoded, previous_end, entity.offset).strip(_SEPARATORS)
        previous_end = entity.offset + entity.length
        key = normalize(before) if _is_emoji(normalize(before)) else normalize(fallback)
        if key and _is_emoji(key):
            result.append((key, entity.custom_emoji_id, fallback or key))
    return result


async def save(session: AsyncSession, *, actor_id: uuid.UUID | None, pairs: list[tuple[str, str, str]]) -> int:
    """Store (or replace) mappings; returns how many the club has now."""
    for emoji, custom_id, fallback in pairs:
        statement = insert(CustomEmoji).values(
            emoji=emoji[:16], custom_emoji_id=custom_id[:64], fallback=fallback[:16], created_by=actor_id
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[CustomEmoji.emoji],
                set_={"custom_emoji_id": statement.excluded.custom_emoji_id, "fallback": statement.excluded.fallback},
            )
        )
    await session.commit()
    forget()
    return len(await list_all(session))


async def list_all(session: AsyncSession) -> list[CustomEmoji]:
    return list(await session.scalars(select(CustomEmoji).order_by(CustomEmoji.created_at).limit(MAX_EMOJI)))


async def clear(session: AsyncSession, emoji: str | None = None) -> None:
    query = delete(CustomEmoji)
    if emoji is not None:
        query = query.where(CustomEmoji.emoji == normalize(emoji))
    await session.execute(query)
    await session.commit()
    forget()


def forget() -> None:
    """Reload the mappings before the next message."""
    global _loaded_at
    _loaded_at = 0.0


def _compile(mapping: dict[str, tuple[str, str]]) -> re.Pattern[str] | None:
    if not mapping:
        return None
    keys = sorted(mapping, key=len, reverse=True)
    # Each emoji may be written with or without the variation mark after any of its characters.
    alternatives = ["".join(re.escape(char) + f"{VARIATION}?" for char in key) for key in keys]
    return re.compile("|".join(alternatives))


def use(mapping: dict[str, tuple[str, str]]) -> None:
    """Set the mappings directly (tests, and after loading from the database)."""
    global _mapping, _pattern, _loaded_at
    _mapping = dict(mapping)
    _pattern = _compile(_mapping)
    _loaded_at = time.monotonic()


async def refresh_if_stale() -> None:
    if time.monotonic() - _loaded_at < RELOAD_SECONDS:
        return
    from app.core.database import get_session_factory

    try:
        async with get_session_factory()() as session:
            rows = await list_all(session)
    except Exception:
        logger.warning("Custom emoji could not be loaded")
        use(_mapping)  # try again in a minute
        return
    use({row.emoji: (row.custom_emoji_id, row.fallback) for row in rows})


def apply(html_text: str) -> str:
    """Rewrite ordinary emoji in Telegram HTML as the club's premium ones."""
    if _pattern is None or not html_text or time.monotonic() < _paused_until:
        return html_text
    pattern = _pattern
    parts = _TAG.split(html_text)
    skipping: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:  # a tag
            match = _TAG_NAME.match(part)
            name = match.group(1).lower() if match else ""
            if name in _SKIP_TAGS:
                if part.startswith("</"):
                    if skipping and skipping[-1] == name:
                        skipping.pop()
                elif not part.endswith("/>"):
                    skipping.append(name)
            continue
        if skipping or not part:
            continue

        def replace(found: re.Match[str]) -> str:
            emoji = normalize(found.group(0))
            custom_id, _ = _mapping.get(emoji, ("", ""))
            if not custom_id:
                return found.group(0)
            return f'<tg-emoji emoji-id="{custom_id}">{found.group(0)}</tg-emoji>'

        parts[index] = pattern.sub(replace, part)
    return "".join(parts)


def pause() -> None:
    """Telegram refused custom emoji (the bot has no Fragment username): ordinary emoji for an hour."""
    global _paused_until
    _paused_until = time.monotonic() + PAUSE_SECONDS
    logger.warning("Telegram refused custom emoji; sending ordinary emoji for an hour")


def paused() -> bool:
    return time.monotonic() < _paused_until
