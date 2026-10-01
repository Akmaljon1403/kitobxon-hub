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


MONTHS_UZ = (
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "may",
    "iyun",
    "iyul",
    "avgust",
    "sentabr",
    "oktabr",
    "noyabr",
    "dekabr",
)


def format_human(value: datetime | None) -> str:
    """ "5-oktabr, 15:30" — the friendly form used in Telegram messages."""
    if value is None:
        return "—"
    local = to_local(value)
    return f"{local.day}-{MONTHS_UZ[local.month - 1]}, {local:%H:%M}"


def format_human_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return f"{value.day}-{MONTHS_UZ[value.month - 1]}"
