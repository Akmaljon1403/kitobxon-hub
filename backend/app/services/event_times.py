"""How an event's time is written in messages and posts, with or without shifts."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from app.utils.timezone import MONTHS_UZ, local_tz

WEEKDAYS = ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba")


class _Timed(Protocol):
    starts_at: datetime
    ends_at: datetime


class _Shift(_Timed, Protocol):
    position: int


def day_text(value: datetime) -> str:
    """«Shanba, 15-noyabr»"""
    local = value.astimezone(local_tz())
    return f"{WEEKDAYS[local.weekday()].capitalize()}, {local.day}-{MONTHS_UZ[local.month - 1]}"


def clock(value: datetime) -> str:
    return f"{value.astimezone(local_tz()):%H:%M}"


def shift_text(shift: _Shift) -> str:
    """«1-smena 10:00–11:30»"""
    return f"{shift.position}-smena {clock(shift.starts_at)}–{clock(shift.ends_at)}"


def when_text(event: _Timed, shifts: Sequence[_Shift] = ()) -> str:
    """«Shanba, 15-noyabr, soat 15:00» or «Shanba, 15-noyabr: 1-smena 10:00–11:30, 2-smena 14:00–15:30»"""
    if shifts:
        return f"{day_text(event.starts_at)}: " + ", ".join(shift_text(shift) for shift in shifts)
    return f"{day_text(event.starts_at)}, soat {clock(event.starts_at)}"


def stamp(value: datetime) -> str:
    """A compact time stamp for dedup keys, so a moved event gets fresh reminders."""
    return f"{value.astimezone(local_tz()):%Y%m%d%H%M}"
