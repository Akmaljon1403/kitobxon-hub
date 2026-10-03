"""Achievements: configurable badges unlocked automatically from verified activity.

Criteria (``Achievement.criteria``) and their measure:
- BOOKS_COMPLETED: books whose reading is completed and verified (test, event or admin), or
  completed at all when book points do not require verification;
- EVENTS_ATTENDED: verified attendance records;
- TESTS_PASSED: tests with a passing result (score above zero and at least the passing score);
- PERFECT_TESTS: tests with the maximum score;
- ACTIVITY_STREAK_WEEKS: the longest run of consecutive weeks (Monday to Sunday, club time zone)
  with a verified attendance or a passed test. It replaces the "reading streak" ideas of the
  specification, because reading happens outside the app and cannot be measured;
- MONTHLY_TOP_RANK: place 1..threshold in a finished month's ranking (checked by the scheduler);
- MANUAL: only granted by an admin.

Once unlocked, an achievement stays (a later correction does not take it away automatically;
an admin can revoke it). Bonus points, if configured, go through the score ledger.
"""

from __future__ import annotations

import html
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    Achievement,
    AttendanceRecord,
    BookRead,
    ScoreTransaction,
    Test,
    TestAttempt,
    User,
    UserAchievement,
)
from app.models.enums import (
    AchievementCriteria,
    AttemptStatus,
    AttendanceStatus,
    NotificationType,
    ReadingStatus,
    ScoreCategory,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.notifications import app_button, celebrate, enqueue_notification, render
from app.services.scoring import award_points, reverse_latest_award
from app.services.settings import get_setting
from app.utils.timezone import local_tz

AUTOMATIC = (
    AchievementCriteria.BOOKS_COMPLETED,
    AchievementCriteria.EVENTS_ATTENDED,
    AchievementCriteria.TESTS_PASSED,
    AchievementCriteria.PERFECT_TESTS,
    AchievementCriteria.ACTIVITY_STREAK_WEEKS,
)
FINISHED = (AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)


# ---------------------------------------------------------------------------- measuring progress


def _passed_condition() -> Any:
    return and_(
        TestAttempt.status.in_(FINISHED),
        TestAttempt.score > 0,
        TestAttempt.score >= Test.passing_score,
    )


async def _activity_weeks(session: AsyncSession, user_id: uuid.UUID) -> set[date]:
    """Mondays (club time zone) of the weeks with a verified attendance or a passed test."""
    attended = await session.scalars(
        select(AttendanceRecord.checked_in_at).where(
            AttendanceRecord.user_id == user_id, AttendanceRecord.status == AttendanceStatus.VERIFIED
        )
    )
    passed = await session.scalars(
        select(TestAttempt.submitted_at)
        .join(Test, Test.id == TestAttempt.test_id)
        .where(TestAttempt.user_id == user_id, _passed_condition())
    )
    weeks = set()
    for moment in [*attended, *passed]:
        if moment is None:
            continue
        local_day = moment.astimezone(local_tz()).date()
        weeks.add(local_day - timedelta(days=local_day.weekday()))
    return weeks


def longest_streak(weeks: set[date]) -> int:
    best = current = 0
    previous: date | None = None
    for monday in sorted(weeks):
        current = current + 1 if previous is not None and monday - previous == timedelta(days=7) else 1
        best = max(best, current)
        previous = monday
    return best


async def progress(session: AsyncSession, user_id: uuid.UUID) -> dict[AchievementCriteria, int]:
    verified_only = await get_setting(session, "score.book_completion_requires_verification")
    books = await session.scalar(
        select(func.count())
        .select_from(BookRead)
        .where(
            BookRead.user_id == user_id,
            BookRead.status == ReadingStatus.COMPLETED,
            BookRead.verified_at.is_not(None) if verified_only else True,
        )
    )
    events = await session.scalar(
        select(func.count())
        .select_from(AttendanceRecord)
        .where(AttendanceRecord.user_id == user_id, AttendanceRecord.status == AttendanceStatus.VERIFIED)
    )
    passed_tests = await session.scalar(
        select(func.count(func.distinct(TestAttempt.test_id)))
        .join(Test, Test.id == TestAttempt.test_id)
        .where(TestAttempt.user_id == user_id, _passed_condition())
    )
    perfect_tests = await session.scalar(
        select(func.count(func.distinct(TestAttempt.test_id)))
        .join(Test, Test.id == TestAttempt.test_id)
        .where(
            TestAttempt.user_id == user_id,
            TestAttempt.status.in_(FINISHED),
            TestAttempt.score == Test.max_score,
        )
    )
    return {
        AchievementCriteria.BOOKS_COMPLETED: int(books or 0),
        AchievementCriteria.EVENTS_ATTENDED: int(events or 0),
        AchievementCriteria.TESTS_PASSED: int(passed_tests or 0),
        AchievementCriteria.PERFECT_TESTS: int(perfect_tests or 0),
        AchievementCriteria.ACTIVITY_STREAK_WEEKS: longest_streak(await _activity_weeks(session, user_id)),
    }


# ---------------------------------------------------------------------------- unlocking


async def _unlock(
    session: AsyncSession,
    *,
    achievement: Achievement,
    user_id: uuid.UUID,
    context: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
) -> bool:
    """Record the achievement once; award its bonus points and queue the congratulation."""
    created = await session.scalar(
        insert(UserAchievement)
        .values(user_id=user_id, achievement_id=achievement.id, context=context)
        .on_conflict_do_nothing(index_elements=[UserAchievement.user_id, UserAchievement.achievement_id])
        .returning(UserAchievement.id)
    )
    if created is None:
        return False
    if achievement.points > 0:
        await award_points(
            session,
            user_id=user_id,
            amount=achievement.points,
            category=ScoreCategory.ACHIEVEMENT,
            idempotency_key=f"achievement:{achievement.id}:{user_id}:{created}",
            source_type="ACHIEVEMENT",
            source_id=achievement.id,
            created_by=actor_id,
            reason=achievement.title,
        )
    text = await render(session, NotificationType.ACHIEVEMENT_UNLOCKED, achievement_title=achievement.title)
    if text is not None:
        if achievement.points > 0:
            text += f"\n+{achievement.points} bonus ball"
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.ACHIEVEMENT_UNLOCKED,
            text=f"{html.escape(achievement.icon, quote=False)} {text}",
            dedup_key=f"achievement:{created}",
            payload=celebrate(app_button("achievements", "🏅 Yutuqlarim")),
        )
    return True


async def evaluate(session: AsyncSession, user_id: uuid.UUID) -> list[Achievement]:
    """Unlock every automatic achievement the member now qualifies for. The caller commits."""
    unlocked_ids = set(
        await session.scalars(select(UserAchievement.achievement_id).where(UserAchievement.user_id == user_id))
    )
    candidates = [
        achievement
        for achievement in await session.scalars(
            select(Achievement).where(Achievement.is_active.is_(True), Achievement.criteria.in_(AUTOMATIC))
        )
        if achievement.id not in unlocked_ids
    ]
    if not candidates:
        return []
    values = await progress(session, user_id)
    new = []
    for achievement in candidates:
        value = values.get(AchievementCriteria(achievement.criteria), 0)
        if value >= achievement.threshold and await _unlock(
            session, achievement=achievement, user_id=user_id, context={"value": value}
        ):
            new.append(achievement)
    return new


async def evaluate_recently_active(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler safety net: re-check members who earned points in the last two days."""
    since = (now or datetime.now(UTC)) - timedelta(days=2)
    user_ids = list(
        await session.scalars(
            select(func.distinct(ScoreTransaction.user_id))
            .join(User, User.id == ScoreTransaction.user_id)
            .where(ScoreTransaction.created_at >= since, User.status == UserStatus.ACTIVE)
        )
    )
    total = 0
    for user_id in user_ids:
        total += len(await evaluate(session, user_id))
    return total


async def monthly_top_ranks(session: AsyncSession, now: datetime | None = None) -> int:
    """In the first week of a month, members placed 1..N in last month's ranking unlock
    MONTHLY_TOP_RANK achievements (N = the achievement's threshold)."""
    from app.services.ranking import ranking  # local import: ranking imports scoring and settings

    local_now = (now or datetime.now(UTC)).astimezone(local_tz())
    if local_now.day > 7:
        return 0
    achievements = list(
        await session.scalars(
            select(Achievement).where(
                Achievement.is_active.is_(True), Achievement.criteria == AchievementCriteria.MONTHLY_TOP_RANK
            )
        )
    )
    if not achievements:
        return 0
    this_month = datetime.combine(local_now.date().replace(day=1), time.min, tzinfo=local_tz())
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    deepest = max(achievement.threshold for achievement in achievements)
    board = await ranking(
        session, period="month", scope="all", viewer=None, limit=deepest, between=(last_month, this_month)
    )
    month_label = f"{last_month:%Y-%m}"
    unlocked = 0
    for achievement in achievements:
        for row in board.items:
            if row.rank <= achievement.threshold and await _unlock(
                session,
                achievement=achievement,
                user_id=row.user_id,
                context={"month": month_label, "rank": row.rank},
            ):
                unlocked += 1
    return unlocked


# ---------------------------------------------------------------------------- member view


async def member_achievements(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    unlocked = {
        row.achievement_id: row
        for row in await session.scalars(select(UserAchievement).where(UserAchievement.user_id == user_id))
    }
    values = await progress(session, user_id)
    result = []
    for achievement in await session.scalars(
        select(Achievement)
        .where(or_(Achievement.is_active.is_(True), Achievement.id.in_(list(unlocked))))
        .order_by(Achievement.sort_order, Achievement.title)
    ):
        earned = unlocked.get(achievement.id)
        criteria = AchievementCriteria(achievement.criteria)
        current = values.get(criteria)
        result.append(
            {
                "code": achievement.code,
                "title": achievement.title,
                "description": achievement.description,
                "icon": achievement.icon,
                "criteria": criteria,
                "threshold": achievement.threshold,
                "points": achievement.points,
                "progress": min(current, achievement.threshold) if current is not None else None,
                "unlocked_at": earned.unlocked_at if earned else None,
            }
        )
    return result


# ---------------------------------------------------------------------------- admin


_EDITABLE = ("title", "description", "icon", "threshold", "points", "is_active", "sort_order")


async def get_achievement(session: AsyncSession, achievement_id: uuid.UUID) -> Achievement:
    achievement = await session.get(Achievement, achievement_id)
    if achievement is None:
        raise NotFoundError("ACHIEVEMENT_NOT_FOUND", "Yutuq topilmadi.")
    return achievement


async def list_admin(session: AsyncSession) -> list[tuple[Achievement, int]]:
    counts = dict(
        (
            await session.execute(
                select(UserAchievement.achievement_id, func.count()).group_by(UserAchievement.achievement_id)
            )
        ).all()
    )
    achievements = await session.scalars(select(Achievement).order_by(Achievement.sort_order, Achievement.title))
    return [(achievement, int(counts.get(achievement.id, 0))) for achievement in achievements]


def _snapshot(achievement: Achievement) -> dict[str, Any]:
    return {field: getattr(achievement, field) for field in (*_EDITABLE, "criteria", "code")}


async def create(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Achievement:
    code = data["code"].strip().upper()
    if await session.scalar(select(Achievement.id).where(Achievement.code == code)):
        raise ConflictError("ACHIEVEMENT_CODE_TAKEN", "Bu kod bilan yutuq allaqachon bor.")
    achievement = Achievement(
        code=code,
        criteria=data["criteria"],
        **{field: data[field] for field in _EDITABLE if data.get(field) is not None},
    )
    session.add(achievement)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="ACHIEVEMENT_CREATE",
        entity_type="achievement",
        entity_id=achievement.id,
        after=_snapshot(achievement),
    )
    await session.commit()
    return achievement


async def update(
    session: AsyncSession, *, actor_id: uuid.UUID, achievement_id: uuid.UUID, changes: dict[str, Any]
) -> Achievement:
    achievement = await get_achievement(session, achievement_id)
    before = _snapshot(achievement)
    for field, value in changes.items():
        if field in _EDITABLE and value is not None:
            setattr(achievement, field, value)
    after = _snapshot(achievement)
    if before != after:
        record_audit(
            session,
            actor_id=actor_id,
            action="ACHIEVEMENT_UPDATE",
            entity_type="achievement",
            entity_id=achievement.id,
            before=before,
            after=after,
        )
    await session.commit()
    return achievement


async def holders(session: AsyncSession, achievement_id: uuid.UUID) -> list[tuple[UserAchievement, User]]:
    await get_achievement(session, achievement_id)
    rows = await session.execute(
        select(UserAchievement, User)
        .join(User, User.id == UserAchievement.user_id)
        .where(UserAchievement.achievement_id == achievement_id)
        .order_by(UserAchievement.unlocked_at.desc())
    )
    return [(row, user) for row, user in rows]


async def grant(
    session: AsyncSession, *, actor_id: uuid.UUID, achievement_id: uuid.UUID, user_id: uuid.UUID, reason: str
) -> None:
    achievement = await get_achievement(session, achievement_id)
    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    if not await _unlock(
        session, achievement=achievement, user_id=user_id, context={"granted_by": str(actor_id)}, actor_id=actor_id
    ):
        raise ConflictError("ACHIEVEMENT_ALREADY_UNLOCKED", "A'zoda bu yutuq allaqachon bor.")
    record_audit(
        session,
        actor_id=actor_id,
        action="ACHIEVEMENT_GRANT",
        entity_type="achievement",
        entity_id=achievement.id,
        after={"user_id": str(user_id)},
        reason=reason,
    )
    await session.commit()


async def revoke(session: AsyncSession, *, actor_id: uuid.UUID, user_achievement_id: uuid.UUID, reason: str) -> None:
    row = await session.get(UserAchievement, user_achievement_id)
    if row is None:
        raise NotFoundError("ACHIEVEMENT_NOT_FOUND", "Yutuq topilmadi.")
    achievement = await get_achievement(session, row.achievement_id)
    if not reason.strip():
        raise BadRequestError("REASON_REQUIRED", "Sababni yozing.")
    await reverse_latest_award(
        session,
        user_id=row.user_id,
        category=ScoreCategory.ACHIEVEMENT,
        source_type="ACHIEVEMENT",
        source_id=achievement.id,
        created_by=actor_id,
        reason=f"Yutuq bekor qilindi: {reason}",
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="ACHIEVEMENT_REVOKE",
        entity_type="achievement",
        entity_id=achievement.id,
        before={"user_id": str(row.user_id), "unlocked_at": row.unlocked_at.isoformat()},
        reason=reason,
    )
    await session.delete(row)
    await session.commit()
