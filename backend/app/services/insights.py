"""«📈 Statistikam»: a member's own reading life in numbers (a premium perk by default)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord, Certificate, Event, ScoreTransaction, Test, TestAttempt, User
from app.models.enums import AchievementCriteria, AttemptStatus, AttendanceStatus, CertificateKind, EventStatus
from app.utils.timezone import MONTHS_UZ, local_tz

MONTHS = 6


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1, tzinfo=local_tz())


def _shift(start: datetime, months: int) -> datetime:
    index = start.year * 12 + start.month - 1 + months
    return _month_start(index // 12, index % 12 + 1)


async def personal_stats(session: AsyncSession, user: User) -> dict[str, Any]:
    from app.services import achievements, ranking

    now = datetime.now(UTC)
    local_now = now.astimezone(local_tz())
    this_month = _month_start(local_now.year, local_now.month)
    first = _shift(this_month, -(MONTHS - 1))

    # Points per month (the last six months, oldest first).
    month_column = func.date_trunc("month", func.timezone(str(local_tz()), ScoreTransaction.created_at))
    by_month = {
        (value.year, value.month): int(total)
        for value, total in (
            await session.execute(
                select(month_column, func.sum(ScoreTransaction.amount))
                .where(ScoreTransaction.user_id == user.id, ScoreTransaction.created_at >= first)
                .group_by(month_column)
            )
        ).all()
    }
    months = []
    for offset in range(MONTHS):
        start = _shift(first, offset)
        months.append(
            {
                "month": f"{start:%Y-%m}",
                "label": MONTHS_UZ[start.month - 1][:3].capitalize(),
                "points": by_month.get((start.year, start.month), 0),
            }
        )

    # Attendance since joining (events attended before registration count as held too).
    joined = user.registered_at or user.created_at
    attended_events = select(AttendanceRecord.event_id).where(
        AttendanceRecord.user_id == user.id, AttendanceRecord.status == AttendanceStatus.VERIFIED
    )
    held = int(
        await session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.deleted_at.is_(None),
                or_(
                    and_(
                        Event.status.in_((EventStatus.PUBLISHED, EventStatus.COMPLETED)),
                        Event.starts_at >= joined,
                        Event.starts_at <= now,
                    ),
                    Event.id.in_(attended_events),
                ),
            )
        )
        or 0
    )
    attended = int(await session.scalar(select(func.count()).select_from(attended_events.subquery())) or 0)

    # Tests: the best result of every test, as a share of the maximum.
    best = (
        select(TestAttempt.test_id, func.max(TestAttempt.score).label("score"))
        .where(
            TestAttempt.user_id == user.id,
            TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
        )
        .group_by(TestAttempt.test_id)
        .subquery()
    )
    tests_taken, average_share = (
        await session.execute(
            select(func.count(), func.avg(best.c.score * 1.0 / func.nullif(Test.max_score, 0)))
            .select_from(best)
            .join(Test, Test.id == best.c.test_id)
        )
    ).one()
    places = dict(
        (
            await session.execute(
                select(Certificate.place, func.count())
                .where(
                    Certificate.user_id == user.id,
                    Certificate.kind == CertificateKind.TEST_PLACE,
                    Certificate.revoked_at.is_(None),
                )
                .group_by(Certificate.place)
            )
        ).all()
    )

    progress = await achievements.progress(session, user.id)
    summary = await ranking.score_summary(session, user.id)
    overall = await ranking.ranking(session, period="all", scope="all", viewer=user, limit=1)
    month = await ranking.ranking(session, period="month", scope="all", viewer=user, limit=1)
    previous = await ranking.ranking(
        session, period="month", scope="all", viewer=user, limit=1, between=(_shift(this_month, -1), this_month)
    )
    return {
        "months": months,
        "total": summary["total"],
        "breakdown": summary["breakdown"],
        "rank": overall.me.rank if overall.me else None,
        "month_rank": month.me.rank if month.me else None,
        "last_month_rank": previous.me.rank if previous.me else None,
        "events_held": held,
        "events_attended": attended,
        "attendance_rate": round(min(attended, held) / held * 100) if held else None,
        "tests_taken": int(tests_taken or 0),
        "tests_average_percent": round(float(average_share) * 100) if average_share is not None else None,
        "test_places": {str(place): int(count) for place, count in places.items() if place},
        "books_completed": progress[AchievementCriteria.BOOKS_COMPLETED],
        "streak_weeks": progress[AchievementCriteria.ACTIVITY_STREAK_WEEKS],
        "member_days": max((now - joined).days, 0) if joined else 0,
        "since": first.date().isoformat(),
    }
