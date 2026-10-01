"""Small helpers that insert valid rows for tests."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, Event, Test, User
from app.models.enums import EventStatus, TestStatus, UserStatus

_sequence = itertools.count(1)


def now() -> datetime:
    return datetime.now(UTC)


async def create_user(session: AsyncSession, **overrides: Any) -> User:
    number = next(_sequence)
    values: dict[str, Any] = {
        "telegram_id": 100_000_000 + number,
        "first_name": f"Ism{number}",
        "last_name": f"Familiya{number}",
        "phone": f"+99890{number:07d}",
        "course": 2,
        "group_name": "201",
        "status": UserStatus.ACTIVE,
        "registered_at": now(),
    }
    values.update(overrides)
    user = User(**values)
    session.add(user)
    await session.flush()
    return user


async def create_book(session: AsyncSession, **overrides: Any) -> Book:
    number = next(_sequence)
    values: dict[str, Any] = {"title": f"Kitob {number}", "author": "Abdulla Qodiriy"}
    values.update(overrides)
    book = Book(**values)
    session.add(book)
    await session.flush()
    return book


async def create_event(session: AsyncSession, **overrides: Any) -> Event:
    start = overrides.pop("starts_at", now() - timedelta(minutes=5))
    values: dict[str, Any] = {
        "title": f"Kitob muhokamasi {next(_sequence)}",
        "location": "Kutubxona, 2-qavat",
        "starts_at": start,
        "ends_at": start + timedelta(minutes=90),
        "attendance_opens_at": start,
        "attendance_closes_at": start + timedelta(minutes=10),
        "status": EventStatus.PUBLISHED,
    }
    values.update(overrides)
    event = Event(**values)
    session.add(event)
    await session.flush()
    return event


async def create_test(session: AsyncSession, **overrides: Any) -> Test:
    start = overrides.pop("starts_at", now() - timedelta(minutes=5))
    values: dict[str, Any] = {
        "title": f"Test {next(_sequence)}",
        "starts_at": start,
        "ends_at": start + timedelta(days=1),
        "duration_minutes": 15,
        "max_score": 20,
        "passing_score": 10,
        "status": TestStatus.PUBLISHED,
    }
    values.update(overrides)
    test = Test(**values)
    session.add(test)
    await session.flush()
    return test
