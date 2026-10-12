"""«🏛 Fakultetlar ligasi»: the faculties compete as teams.

The order is by average points per member (fair between large and small faculties), as in the
ranking; next to it the league shows what makes a reading faculty — how many of its members were
active, pages written in the reading diary, books finished and club events attended.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, Faculty, ReadingLog, ScoreTransaction, ShelfItem, User
from app.models.enums import AttendanceStatus, ShelfStatus, UserStatus
from app.services.ranking import faculty_ranking, period_start
from app.utils.timezone import local_tz

Period = Literal["week", "month", "all"]


async def table(session: AsyncSession, period: Period, viewer: User | None = None) -> dict[str, Any]:
    ranked = await faculty_ranking(session, period=period)
    start = period_start(period)
    members = select(User.id, User.faculty_id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
    since = start or datetime(2000, 1, 1, tzinfo=local_tz())
    active_ids = union(
        select(ScoreTransaction.user_id.label("user_id")).where(ScoreTransaction.created_at >= since),
        select(ReadingLog.user_id.label("user_id")).where(ReadingLog.created_at >= since),
        select(AttendanceRecord.user_id.label("user_id")).where(
            AttendanceRecord.checked_in_at >= since, AttendanceRecord.status == AttendanceStatus.VERIFIED
        ),
    ).subquery()
    member_rows = members.subquery()

    async def per_faculty(query: Any) -> dict[uuid.UUID | None, int]:
        return {faculty_id: int(value or 0) for faculty_id, value in (await session.execute(query)).all()}

    active = await per_faculty(
        select(member_rows.c.faculty_id, func.count())
        .join(active_ids, active_ids.c.user_id == member_rows.c.id)
        .group_by(member_rows.c.faculty_id)
    )
    pages = await per_faculty(
        select(User.faculty_id, func.sum(ReadingLog.pages))
        .join(User, User.id == ReadingLog.user_id)
        .where(ReadingLog.created_at >= since, User.status == UserStatus.ACTIVE)
        .group_by(User.faculty_id)
    )
    books = await per_faculty(
        select(User.faculty_id, func.count(ShelfItem.id))
        .join(User, User.id == ShelfItem.user_id)
        .where(
            ShelfItem.status == ShelfStatus.FINISHED,
            ShelfItem.finished_at >= since,
            User.status == UserStatus.ACTIVE,
        )
        .group_by(User.faculty_id)
    )
    visits = await per_faculty(
        select(User.faculty_id, func.count(AttendanceRecord.id))
        .join(User, User.id == AttendanceRecord.user_id)
        .where(
            AttendanceRecord.checked_in_at >= since,
            AttendanceRecord.status == AttendanceStatus.VERIFIED,
            User.status == UserStatus.ACTIVE,
        )
        .group_by(User.faculty_id)
    )
    ids = {
        name: faculty_id
        for faculty_id, name in (
            await session.execute(select(Faculty.id, Faculty.name).where(Faculty.is_active.is_(True)))
        ).all()
    }
    rows = []
    for item in ranked:
        faculty_id = ids.get(item["faculty"])
        count = item["members"]
        rows.append(
            {
                **item,
                "mine": viewer is not None and faculty_id is not None and viewer.faculty_id == faculty_id,
                "active": active.get(faculty_id, 0),
                "participation": round(active.get(faculty_id, 0) * 100 / count) if count else 0,
                "pages": pages.get(faculty_id, 0),
                "books": books.get(faculty_id, 0),
                "visits": visits.get(faculty_id, 0),
            }
        )
    return {"period": period, "starts_at": start, "items": rows}
