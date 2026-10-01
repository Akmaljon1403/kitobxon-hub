"""Display helpers: timestamps are stored in UTC and shown in the club's time zone."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def to_local(value: datetime) -> datetime:
    return value.astimezone(local_tz())


def format_date(value: datetime | None) -> str:
    return to_local(value).strftime("%d.%m.%Y") if value else "—"


def format_datetime(value: datetime | None) -> str:
    return to_local(value).strftime("%d.%m.%Y %H:%M") if value else "—"
