"""Club analytics for the Admin Panel. Aggregates only — no personal data except the explicit
inactive-members list, which needs USER_VIEW. Groups with fewer than three members are left
out of group statistics so that nobody can be identified through them."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    Book,
    BookRead,
    Event,
    Faculty,
    ScoreTransaction,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    BookStatus,
    EventStatus,
    ReadingStatus,
    ScoreCategory,
    UserStatus,
)
from app.utils.timezone import local_tz

MIN_GROUP_SIZE = 3
ACTIVITY_CATEGORIES = (
    ScoreCategory.ATTENDANCE,
    ScoreCategory.TEST,
    ScoreCategory.TEST_RANK_BONUS,
    ScoreCategory.BOOK_COMPLETION,
)
POINT_BUCKETS = ((0, 0, "0"), (1, 49, "1–49"), (50, 99, "50–99"), (100, 199, "100–199"), (200, 499, "200–499"))
FINISHED = (AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)


def _month_starts(months: int, today: date) -> list[datetime]:
    first = today.replace(day=1)
    starts = []
    for offset in range(months - 1, -1, -1):
        year, month = first.year, first.month - offset
        while month <= 0:
            month += 12
            year -= 1
        starts.append(datetime.combine(date(year, month, 1), time.min, tzinfo=local_tz()))
    return starts


def _month_key(column: Any) -> Any:
    return func.to_char(func.timezone(str(local_tz()), column), "YYYY-MM")


async def _monthly(session: AsyncSession, moment: Any, value: Any, conditions: list[Any], keys: list[str]) -> list[int]:
    """One number per month (club time zone) for the given timestamp column."""
    month = _month_key(moment)
    rows = await session.execute(select(month, value).where(*conditions).group_by(month))
    counts = dict(rows.all())
    return [int(counts.get(key, 0)) for key in keys]


async def overview(session: AsyncSession, *, months: int = 6, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    local_today = now.astimezone(local_tz()).date()
    starts = _month_starts(months, local_today)
    keys = [f"{start:%Y-%m}" for start in starts]
    since = starts[0]
    active_member = and_(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))

    # ---- by month
    new_members = await _monthly(
        session, User.registered_at, func.count(), [User.deleted_at.is_(None), User.registered_at >= since], keys
    )
    active_members = await _monthly(
        session,
        ScoreTransaction.created_at,
        func.count(func.distinct(ScoreTransaction.user_id)),
        [ScoreTransaction.created_at >= since, ScoreTransaction.category.in_(ACTIVITY_CATEGORIES)],
        keys,
    )
    attendance = await _monthly(
        session,
        AttendanceRecord.checked_in_at,
        func.count(),
        [AttendanceRecord.checked_in_at >= since, AttendanceRecord.status == AttendanceStatus.VERIFIED],
        keys,
    )
    completions = await _monthly(
        session,
        BookRead.completed_at,
        func.count(),
        [BookRead.completed_at >= since, BookRead.status == ReadingStatus.COMPLETED],
        keys,
    )
    events = await _monthly(
        session,
        Event.starts_at,
        func.count(),
        [
            Event.starts_at >= since,
            Event.deleted_at.is_(None),
            Event.status.in_((EventStatus.PUBLISHED, EventStatus.COMPLETED)),
        ],
        keys,
    )

    # ---- headline numbers
    month_ago = now - timedelta(days=30)
    recent_activity = (
        select(ScoreTransaction.user_id)
        .where(ScoreTransaction.created_at >= month_ago, ScoreTransaction.category.in_(ACTIVITY_CATEGORIES))
        .distinct()
    )
    members_total = int(await session.scalar(select(func.count()).select_from(User).where(active_member)) or 0)
    active_30 = int(
        await session.scalar(select(func.count()).select_from(User).where(active_member, User.id.in_(recent_activity)))
        or 0
    )
    avg_test = await session.scalar(
        select(func.avg(TestAttempt.score * 100.0 / Test.max_score))
        .select_from(TestAttempt)
        .join(Test, Test.id == TestAttempt.test_id)
        .where(TestAttempt.status.in_(FINISHED), TestAttempt.submitted_at >= since)
    )
    test_participants = await session.scalar(
        select(func.count(func.distinct(TestAttempt.user_id))).where(
            TestAttempt.status.in_(FINISHED), TestAttempt.submitted_at >= since
        )
    )

    # ---- points distribution (all time, active members)
    totals = (
        select(User.id.label("user_id"), func.coalesce(func.sum(ScoreTransaction.amount), 0).label("total"))
        .outerjoin(ScoreTransaction, ScoreTransaction.user_id == User.id)
        .where(active_member)
        .group_by(User.id)
        .subquery()
    )
    bucket_rows = await session.execute(select(totals.c.total))
    distribution = {label: 0 for *_, label in POINT_BUCKETS}
    distribution["500+"] = 0
    for (total,) in bucket_rows:
        value = int(total)
        for low, high, label in POINT_BUCKETS:
            if low <= value <= high:
                distribution[label] += 1
                break
        else:
            if value >= 500:
                distribution["500+"] += 1
            else:
                distribution["0"] += 1  # negative totals (corrections) count as no points

    # ---- faculties
    points = (
        select(ScoreTransaction.user_id, func.sum(ScoreTransaction.amount).label("total"))
        .group_by(ScoreTransaction.user_id)
        .subquery()
    )
    attended = (
        select(AttendanceRecord.user_id, func.count().label("visits"))
        .where(AttendanceRecord.status == AttendanceStatus.VERIFIED)
        .group_by(AttendanceRecord.user_id)
        .subquery()
    )
    faculty_rows = await session.execute(
        select(
            Faculty.name,
            func.count(User.id),
            func.count(User.id).filter(User.id.in_(recent_activity)),
            func.coalesce(func.sum(points.c.total), 0),
            func.coalesce(func.sum(attended.c.visits), 0),
        )
        .outerjoin(User, and_(User.faculty_id == Faculty.id, active_member))
        .outerjoin(points, points.c.user_id == User.id)
        .outerjoin(attended, attended.c.user_id == User.id)
        .where(Faculty.is_active.is_(True))
        .group_by(Faculty.id, Faculty.name, Faculty.sort_order)
        .order_by(Faculty.sort_order, Faculty.name)
    )
    faculties = [
        {
            "name": name,
            "members": int(members),
            "active_30_days": int(active),
            "total_points": int(total),
            "average_points": round(int(total) / int(members), 1) if members else 0.0,
            "attendance": int(visits),
        }
        for name, members, active, total, visits in faculty_rows
    ]

    # ---- groups (only groups with at least MIN_GROUP_SIZE members)
    group_rows = await session.execute(
        select(
            User.group_name,
            Faculty.name,
            func.count(User.id),
            func.coalesce(func.sum(points.c.total), 0),
        )
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .outerjoin(points, points.c.user_id == User.id)
        .where(active_member, User.group_name.is_not(None))
        .group_by(User.group_name, Faculty.name)
        .having(func.count(User.id) >= MIN_GROUP_SIZE)
    )
    groups = sorted(
        (
            {
                "group": group,
                "faculty": faculty,
                "members": int(count),
                "average_points": round(int(total) / int(count), 1),
            }
            for group, faculty, count, total in group_rows
        ),
        key=lambda row: (-row["average_points"], row["group"]),
    )[:10]

    # ---- tests (latest 10 with results)
    test_rows = await session.execute(
        select(
            Test.title,
            Test.max_score,
            func.count(func.distinct(TestAttempt.user_id)),
            func.avg(TestAttempt.score),
            func.count(func.distinct(TestAttempt.user_id)).filter(
                TestAttempt.score > 0, TestAttempt.score >= Test.passing_score
            ),
            Test.ends_at,
        )
        .join(TestAttempt, and_(TestAttempt.test_id == Test.id, TestAttempt.status.in_(FINISHED)))
        .where(Test.deleted_at.is_(None))
        .group_by(Test.id)
        .order_by(Test.ends_at.desc())
        .limit(10)
    )
    tests = [
        {
            "title": title,
            "participants": int(participants),
            "average_percent": round(float(average or 0) * 100 / max_score, 1),
            "pass_rate": round(int(passed) * 100 / int(participants), 1) if participants else 0.0,
            "ends_at": ends_at,
        }
        for title, max_score, participants, average, passed, ends_at in test_rows
    ]

    # ---- reading campaigns (active and recently completed books)
    book_rows = await session.execute(
        select(
            Book.title,
            Book.author,
            Book.status,
            Book.deadline,
            func.count(BookRead.id),
            func.count(BookRead.id).filter(BookRead.status == ReadingStatus.COMPLETED),
            func.count(BookRead.id).filter(BookRead.verified_at.is_not(None)),
        )
        .outerjoin(BookRead, BookRead.book_id == Book.id)
        .where(Book.deleted_at.is_(None), Book.status.in_((BookStatus.ACTIVE, BookStatus.COMPLETED)))
        .group_by(Book.id)
        .order_by(case((Book.status == BookStatus.ACTIVE, 0), else_=1), Book.created_at.desc())
        .limit(10)
    )
    books = [
        {
            "title": title,
            "author": author,
            "status": status,
            "deadline": deadline,
            "readers": int(readers),
            "completed": int(completed),
            "verified": int(verified),
            "completion_rate": round(int(completed) * 100 / int(readers), 1) if readers else 0.0,
        }
        for title, author, status, deadline, readers, completed, verified in book_rows
    ]

    return {
        "months": keys,
        "headline": {
            "members": members_total,
            "active_30_days": active_30,
            "inactive_30_days": int(
                await session.scalar(select(func.count()).select_from(_inactive_query(30).subquery())) or 0
            ),
            "test_participants": int(test_participants or 0),
            "average_test_percent": round(float(avg_test), 1) if avg_test is not None else None,
        },
        "by_month": {
            "new_members": new_members,
            "active_members": active_members,
            "attendance": attendance,
            "events": events,
            "books_completed": completions,
        },
        "points_distribution": [{"bucket": bucket, "members": count} for bucket, count in distribution.items()],
        "faculties": faculties,
        "groups": groups,
        "tests": tests,
        "books": books,
    }


def _inactive_query(days: int) -> Any:
    """Active members whose latest activity (or registration, if none) is older than ``days`` days."""
    since = datetime.now(UTC) - timedelta(days=days)
    last_activity = (
        select(ScoreTransaction.user_id, func.max(ScoreTransaction.created_at).label("last_at"))
        .where(ScoreTransaction.category.in_(ACTIVITY_CATEGORIES))
        .group_by(ScoreTransaction.user_id)
        .subquery()
    )
    return (
        select(User, Faculty.name.label("faculty"), last_activity.c.last_at)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .outerjoin(last_activity, last_activity.c.user_id == User.id)
        .where(
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
            func.coalesce(last_activity.c.last_at, User.registered_at, User.created_at) < since,
        )
        .order_by(last_activity.c.last_at.asc().nulls_first(), User.last_name)
    )


async def inactive_members(session: AsyncSession, *, days: int, limit: int = 200) -> list[dict[str, Any]]:
    """Active members with no attendance, test or book activity for ``days`` days."""
    rows = await session.execute(_inactive_query(days).limit(limit))
    return [
        {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "faculty": faculty,
            "course": user.course,
            "group_name": user.group_name,
            "registered_at": user.registered_at,
            "last_activity_at": last_at,
        }
        for user, faculty, last_at in rows
    ]
