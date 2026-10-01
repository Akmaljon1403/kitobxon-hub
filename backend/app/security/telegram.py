"""Validation of Telegram Mini App ``initData``.

Telegram signs the data it passes to a Mini App with a key derived from the bot token
(https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).
The backend recomputes the signature, so a user ID typed into JavaScript is never trusted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

from app.core.errors import UnauthorizedError

MAX_INIT_DATA_LENGTH = 4096
_ALLOWED_CLOCK_SKEW_SECONDS = 60


@dataclass(frozen=True)
class TelegramUser:
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    language_code: str | None
    photo_url: str | None


@dataclass(frozen=True)
class InitData:
    user: TelegramUser
    auth_date: int
    start_param: str | None
    query_id: str | None


class InitDataError(UnauthorizedError):
    code = "INIT_DATA_INVALID"
    message = "Telegram ma'lumotlari tasdiqlanmadi. Ilovani bot orqali qayta oching."


class InitDataExpiredError(UnauthorizedError):
    code = "INIT_DATA_EXPIRED"
    message = "Sessiya muddati tugagan. Ilovani bot orqali qayta oching."


def _signature(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()


def build_data_check_string(fields: dict[str, str]) -> str:
    return "\n".join(f"{key}={value}" for key, value in sorted(fields.items()) if key != "hash")


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Return the ``hash`` Telegram would produce for ``fields`` (used by tests and tooling)."""
    return _signature(build_data_check_string(fields), bot_token)


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int, now: float | None = None) -> InitData:
    if not init_data or len(init_data) > MAX_INIT_DATA_LENGTH:
        raise InitDataError()
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError as exc:
        raise InitDataError() from exc

    fields: dict[str, str] = {}
    for key, value in pairs:
        if key in fields:  # duplicated keys are never produced by Telegram
            raise InitDataError()
        fields[key] = value

    received_hash = fields.get("hash")
    if not received_hash:
        raise InitDataError()
    expected_hash = _signature(build_data_check_string(fields), bot_token)
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError()

    try:
        auth_date = int(fields["auth_date"])
        raw_user: dict[str, Any] = json.loads(fields["user"])
        user_id = int(raw_user["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InitDataError() from exc

    current = time.time() if now is None else now
    if auth_date > current + _ALLOWED_CLOCK_SKEW_SECONDS:
        raise InitDataError()
    if current - auth_date > max_age_seconds:
        raise InitDataExpiredError()

    def _text(name: str, limit: int) -> str | None:
        value = raw_user.get(name)
        return str(value)[:limit] if value not in (None, "") else None

    user = TelegramUser(
        id=user_id,
        first_name=_text("first_name", 64) or "",
        last_name=_text("last_name", 64),
        username=_text("username", 64),
        language_code=_text("language_code", 8),
        photo_url=_text("photo_url", 512),
    )
    return InitData(
        user=user,
        auth_date=auth_date,
        start_param=fields.get("start_param"),
        query_id=fields.get("query_id"),
    )
