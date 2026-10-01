"""Dashboard statistics (aggregates only, no personal data)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, BookRead, Faculty, User
from app.models.enums import BookStatus, ReadingStatus, UserStatus


async def dashboard(session: AsyncSession) -> dict[str, Any]:
    alive = User.deleted_at.is_(None)
    by_status = dict(
        (await session.execute(select(User.status, func.count()).where(alive).group_by(User.status))).all()
    )
    week_ago = datetime.now(UTC) - timedelta(days=7)
    new_users = await session.scalar(
        select(func.count()).select_from(User).where(alive, User.registered_at >= week_ago)
    )

    book_alive = Book.deleted_at.is_(None)
    books_by_status = dict(
        (await session.execute(select(Book.status, func.count()).where(book_alive).group_by(Book.status))).all()
    )
    completions = await session.scalar(
        select(func.count()).select_from(BookRead).where(BookRead.status == ReadingStatus.COMPLETED)
    )
    readers = await session.scalar(select(func.count(func.distinct(BookRead.user_id))))

    faculty_rows = await session.execute(
        select(Faculty.name, func.count(User.id))
        .outerjoin(User, (User.faculty_id == Faculty.id) & alive & (User.status == UserStatus.ACTIVE))
        .group_by(Faculty.id, Faculty.name, Faculty.sort_order)
        .order_by(Faculty.sort_order, Faculty.name)
    )
    return {
        "users": {
            "total": sum(by_status.values()),
            "active": by_status.get(UserStatus.ACTIVE, 0),
            "pending": by_status.get(UserStatus.PENDING, 0),
            "blocked": by_status.get(UserStatus.BLOCKED, 0),
            "inactive": by_status.get(UserStatus.INACTIVE, 0),
            "new_last_7_days": int(new_users or 0),
        },
        "books": {
            "total": sum(books_by_status.values()),
            "active": books_by_status.get(BookStatus.ACTIVE, 0),
            "draft": books_by_status.get(BookStatus.DRAFT, 0),
            "readers": int(readers or 0),
            "completions": int(completions or 0),
        },
        "faculties": [{"name": name, "members": int(count)} for name, count in faculty_rows],
    }
