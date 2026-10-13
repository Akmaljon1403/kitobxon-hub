"""The words the bot says, live: the owner's edits from the Admin Panel («📝 Matnlar») and the variants
that keep a message from sounding the same every time.

Every ``texts.SOME_TEXT`` (bot texts), every member notification template (``notify.<TYPE>``) and the
channel's phrase lists (``channel.<name>``) pass through ``pick``/``options``:

* when the owner wrote their own wording (one or several variants) — that is used;
* otherwise the built-in text, and — when it has built-in variants (``text_variants.VARIANTS``) and
  rotation is on — one of them, never the same one twice in a row.

The edits live in the ``text_overrides`` table; every process keeps a copy in memory and looks at the table
again at most every ``TTL`` seconds (``refresh``), so a change shows up within half a minute everywhere,
with no restart. Nothing here imports the database at load time: ``texts`` imports this module.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

TTL = 30.0
_random = random.SystemRandom()


@dataclass(frozen=True)
class Override:
    variants: tuple[str, ...]
    rotate: bool = True


_overrides: dict[str, Override] = {}
_loaded_at = 0.0
_rotation = True
_last: dict[str, int] = {}
# Tests compare sent texts with ``texts.X``: rotation is off there unless a test turns it on.
force_rotation: bool | None = None


def _rotating() -> bool:
    if force_rotation is not None:
        return force_rotation
    from app.core.config import get_settings

    return _rotation and get_settings().environment != "test"


def builtin(key: str) -> tuple[str, ...]:
    from app.bot.text_variants import VARIANTS

    return VARIANTS.get(key, ())


def _choose(key: str, options: Sequence[str]) -> str:
    """One of ``options``, never the one chosen for ``key`` the last time."""
    if len(options) == 1:
        return options[0]
    last = _last.get(key)
    choices = [index for index in range(len(options)) if index != last]
    index = _random.choice(choices)
    _last[key] = index
    return options[index]


def pick(key: str, default: str) -> str:
    """The text to send now for ``key`` (``default``: the wording in the code)."""
    override = _overrides.get(key)
    if override is not None and override.variants:
        if not override.rotate or not _rotating():
            return override.variants[0]
        return _choose(key, override.variants)
    extra = builtin(key)
    if not extra or not _rotating():
        return default
    return _choose(key, (default, *extra))


def options(key: str, defaults: Sequence[str]) -> tuple[str, ...]:
    """All the wordings of a list (the channel's phrases): the owner's, or the built-in ones."""
    override = _overrides.get(key)
    if override is not None and override.variants:
        return override.variants
    return tuple(defaults)


def current(key: str) -> Override | None:
    return _overrides.get(key)


def apply(rows: dict[str, Override], rotation: bool) -> None:
    """Replace the in-memory copy (after loading the table, or right after an edit)."""
    global _overrides, _loaded_at, _rotation
    _overrides = dict(rows)
    _rotation = rotation
    _loaded_at = time.monotonic()


def reset() -> None:
    """Forget everything (tests)."""
    global _overrides, _loaded_at, _rotation
    _overrides = {}
    _loaded_at = 0.0
    _rotation = True
    _last.clear()


async def refresh(session: Any, *, force: bool = False) -> None:
    """Look at the owner's edits again when the copy is older than ``TTL`` (cheap otherwise)."""
    if not force and time.monotonic() - _loaded_at < TTL:
        return
    from sqlalchemy import select

    from app.models import TextOverride
    from app.services.settings import get_setting

    try:
        rows = (await session.execute(select(TextOverride.key, TextOverride.variants, TextOverride.rotate))).all()
        rotation = bool(await get_setting(session, "texts.rotate"))
    except Exception:  # the words in the code are always there; never fail a message because of this
        import logging

        logging.getLogger(__name__).warning("The text edits could not be loaded", exc_info=True)
        return
    apply(
        {key: Override(tuple(str(v) for v in variants or ()), bool(rotate)) for key, variants, rotate in rows},
        rotation,
    )
