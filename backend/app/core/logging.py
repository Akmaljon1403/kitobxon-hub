"""Structured (JSON) logging with request correlation IDs and secret redaction."""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

# Patterns that must never reach log storage.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    # Telegram bot tokens (also when embedded in api.telegram.org URLs).
    (re.compile(r"\d{5,12}:[A-Za-z0-9_-]{30,}"), "[REDACTED_BOT_TOKEN]"),
    # Bearer / JWT tokens.
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "[REDACTED_JWT]"),
    # Telegram initData signature fields.
    (re.compile(r"(?i)((?:^|[&?\s])(?:hash|signature)=)[A-Za-z0-9_-]+"), r"\1[REDACTED]"),
    # Generic key=value secrets.
    (re.compile(r"(?i)((?:password|secret|api_key|token)\s*[=:]\s*)[^\s,;&]+"), r"\1[REDACTED]"),
]

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}


def redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFilter(logging.Filter):
    """Redacts secrets from the final message of every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed log call
            return True
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = None
        return True


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key not in {"request_id", "color_message"} and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s")

    def formatException(self, ei) -> str:
        return redact(super().formatException(ei))


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.addFilter(RedactingFilter())
    handler.setFormatter(JsonFormatter() if json_output else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn installs its own handlers; route everything through ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "aiogram", "sqlalchemy.engine"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    # Our middleware writes access logs without query strings; uvicorn's would duplicate them.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
