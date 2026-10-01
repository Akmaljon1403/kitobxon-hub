"""Phase 16: achievements unlocked from verified activity, admin configuration, grant and revoke."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Achievement,
    AttendanceRecord,
    AuditLog,
    Notification,
    ScoreTransaction,
    TestOption,
    TestQuestion,
    User,
    UserAchievement,
)
from app.models.enums import AttendanceMethod, AttendanceStatus, BookStatus, NotificationType, ScoreCategory
from app.security.permissions import Perm
from app.services import achievements, attendance, books, quizzes
from app.services.scoring import award_points
from app.utils.timezone import local_tz
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


async def _codes(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = await db.scalars(
        select(Achievement.code)
        .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
        .where(UserAchievement.user_id == user_id)
    )
    return set(rows)


async def _points(db: AsyncSession, user_id: uuid.UUID, category: ScoreCategory) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user_id, ScoreTransaction.category == category
            )
        )
    )


async def test_first_attendance_unlocks_first_event(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    member = await create_user(db)
    event = await create_event(db)
    await db.commit()
    member_id = member.id
    await attendance.manual_check_in(
        db, actor_id=admin.id, event_id=event.id, user_id=member_id, note="Qog'ozda belgilangan"
    )
    assert await _codes(db, member_id) == {"FIRST_EVENT"}
    note = await db.scalar(select(Notification).where(Notification.type == NotificationType.ACHIEVEMENT_UNLOCKED))
    assert "Ilk uchrashuv" in note.text
    assert note.payload["buttons"][0]["app_route"] == "achievements"

    response = await client.get("/api/v1/me/achievements", headers=member_headers(member))
    items = {item["code"]: item for item in response.json()}
    assert items["FIRST_EVENT"]["unlocked_at"] is not None
    assert items["TEN_EVENTS"]["unlocked_at"] is None
    assert items["TEN_EVENTS"]["progress"] == 1
    assert items["TEN_EVENTS"]["threshold"] == 10


async def test_unlocking_is_idempotent_and_awards_configured_points(db: AsyncSession) -> None:
    member = await create_user(db)
    event = await create_event(db)
    await db.execute(update(Achievement).where(Achievement.code == "FIRST_EVENT").values(points=5))
    db.add(
        AttendanceRecord(
            event_id=event.id, user_id=member.id, method=AttendanceMethod.MANUAL, status=AttendanceStatus.VERIFIED
        )
    )
    await db.commit()
    member_id = member.id
    assert [a.code for a in await achievements.evaluate(db, member_id)] == ["FIRST_EVENT"]
    await db.commit()
    assert await achievements.evaluate(db, member_id) == []
    await db.commit()
    assert await _points(db, member_id, ScoreCategory.ACHIEVEMENT) == 5


async def test_book_achievement_needs_verified_reading(db: AsyncSession) -> None:
    admin = await _admin(db)
    member = await create_user(db)
    book = await create_book(db, status=BookStatus.ACTIVE)
    await db.commit()
    member_id = member.id
    await books.set_reading_status(db, user_id=member_id, book_id=book.id, action="start")
    await books.set_reading_status(db, user_id=member_id, book_id=book.id, action="complete")
    assert await _codes(db, member_id) == set()  # self-reported only
    await books.verify_reading(db, actor_id=admin.id, book_id=book.id, user_id=member_id)
    assert await _codes(db, member_id) == {"FIRST_BOOK"}


async def test_perfect_tests_unlock_test_master(db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    member_id = member.id
    for _ in range(3):
        test = await create_test(db, passing_score=0)
        question = TestQuestion(test_id=test.id, text="Savol", points=1)
        db.add(question)
        await db.flush()
        correct = TestOption(question_id=question.id, text="Ha", is_correct=True)
        db.add_all([correct, TestOption(question_id=question.id, text="Yo'q")])
        await db.commit()
        await quizzes.start_attempt(db, user=member, test_id=test.id)
        await quizzes.submit_attempt(db, user_id=member_id, test_id=test.id, answers=[(question.id, [correct.id])])
    assert "TEST_MASTER" in await _codes(db, member_id)


def test_longest_streak() -> None:
    monday = date(2026, 9, 7)
    weeks = {monday + timedelta(weeks=i) for i in (0, 1, 2, 4, 5, 6, 7)}
    assert achievements.longest_streak(weeks) == 4
    assert achievements.longest_streak(set()) == 0
    assert achievements.longest_streak({monday}) == 1


async def test_four_active_weeks_unlock_the_streak(db: AsyncSession) -> None:
    member = await create_user(db)
    now = datetime.now(UTC)
    for week in range(4):
        event = await create_event(db, starts_at=now - timedelta(weeks=week))
        db.add(
            AttendanceRecord(
                event_id=event.id,
                user_id=member.id,
                method=AttendanceMethod.MANUAL,
                status=AttendanceStatus.VERIFIED,
                checked_in_at=now - timedelta(weeks=week),
            )
        )
    await db.commit()
    member_id = member.id
    await achievements.evaluate(db, member_id)
    await db.commit()
    assert "ACTIVE_STREAK_4_WEEKS" in await _codes(db, member_id)
    assert "ACTIVE_STREAK_12_WEEKS" not in await _codes(db, member_id)


async def test_monthly_top_three(db: AsyncSession) -> None:
    members = [await create_user(db) for _ in range(4)]
    await db.commit()
    member_ids = [m.id for m in members]
    local_now = datetime.now(local_tz())
    first_of_month = local_now.replace(day=1, hour=10, minute=0, second=0, microsecond=0)
    last_month = first_of_month - timedelta(days=10)
    for index, user_id in enumerate(member_ids):
        tx = await award_points(
            db, user_id=user_id, amount=40 - index * 5, category=ScoreCategory.ATTENDANCE, idempotency_key=f"m:{index}"
        )
        await db.execute(text("ALTER TABLE score_transactions DISABLE TRIGGER score_transactions_append_only"))
        await db.execute(update(ScoreTransaction).where(ScoreTransaction.id == tx).values(created_at=last_month))
        await db.execute(text("ALTER TABLE score_transactions ENABLE TRIGGER score_transactions_append_only"))
    await db.commit()

    assert await achievements.monthly_top_ranks(db, first_of_month.replace(day=15)) == 0  # only in the first week
    assert await achievements.monthly_top_ranks(db, first_of_month.replace(day=2)) == 3
    await db.commit()
    assert await achievements.monthly_top_ranks(db, first_of_month.replace(day=3)) == 0
    holders = [user_id for user_id in member_ids if "TOP_3_MONTH" in await _codes(db, user_id)]
    assert holders == member_ids[:3]


async def test_inactive_achievement_is_not_unlocked(db: AsyncSession) -> None:
    member = await create_user(db)
    event = await create_event(db)
    await db.execute(update(Achievement).where(Achievement.code == "FIRST_EVENT").values(is_active=False))
    db.add(
        AttendanceRecord(
            event_id=event.id, user_id=member.id, method=AttendanceMethod.MANUAL, status=AttendanceStatus.VERIFIED
        )
    )
    await db.commit()
    assert await achievements.evaluate(db, member.id) == []


async def test_admin_creates_grants_and_revokes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    settings_admin = await _admin(db, Perm.SETTINGS_MANAGE)
    score_admin = await _admin(db, Perm.SCORE_VIEW, Perm.SCORE_MANAGE)
    viewer = await _admin(db)
    member = await create_user(db)
    await db.commit()
    member_id = member.id
    body = {
        "code": "best_volunteer",
        "title": "Faol ko'ngilli",
        "description": "Klub tadbirlarini tashkil qilishda yordam bergani uchun",
        "icon": "🤲",
        "criteria": "MANUAL",
        "points": 15,
    }
    assert (
        await client.post("/api/v1/admin/achievements", json=body, headers=admin_headers(viewer))
    ).status_code == 403
    created = await client.post("/api/v1/admin/achievements", json=body, headers=admin_headers(settings_admin))
    assert created.status_code == 201
    assert created.json()["code"] == "BEST_VOLUNTEER"
    achievement_id = created.json()["id"]
    duplicate = await client.post("/api/v1/admin/achievements", json=body, headers=admin_headers(settings_admin))
    assert duplicate.status_code == 409

    grant = {"user_id": str(member_id), "reason": "Kitob ko'rgazmasini tashkil qildi"}
    assert (
        await client.post(
            f"/api/v1/admin/achievements/{achievement_id}/grant", json=grant, headers=admin_headers(viewer)
        )
    ).status_code == 403
    granted = await client.post(
        f"/api/v1/admin/achievements/{achievement_id}/grant", json=grant, headers=admin_headers(score_admin)
    )
    assert granted.status_code == 204
    again = await client.post(
        f"/api/v1/admin/achievements/{achievement_id}/grant", json=grant, headers=admin_headers(score_admin)
    )
    assert again.status_code == 409
    assert await _points(db, member_id, ScoreCategory.ACHIEVEMENT) == 15

    holders = await client.get(f"/api/v1/admin/achievements/{achievement_id}/holders", headers=admin_headers(viewer))
    assert holders.json()[0]["granted"] is True
    listing = await client.get("/api/v1/admin/achievements", headers=admin_headers(viewer))
    assert next(a for a in listing.json() if a["code"] == "BEST_VOLUNTEER")["holders"] == 1

    revoked = await client.post(
        f"/api/v1/admin/user-achievements/{holders.json()[0]['id']}/revoke",
        json={"reason": "Xato bilan berilgan edi"},
        headers=admin_headers(score_admin),
    )
    assert revoked.status_code == 204
    # The ledger is append-only: the bonus stays and a reversal cancels it.
    assert await _points(db, member_id, ScoreCategory.ACHIEVEMENT) == 15
    assert await _points(db, member_id, ScoreCategory.REVERSAL) == -15
    assert await _codes(db, member_id) == set()
    actions = set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "achievement")))
    assert {"ACHIEVEMENT_CREATE", "ACHIEVEMENT_GRANT", "ACHIEVEMENT_REVOKE"} <= actions


async def test_editing_a_definition(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.SETTINGS_MANAGE)
    achievement_id = await db.scalar(select(Achievement.id).where(Achievement.code == "TEN_EVENTS"))
    changed = await client.patch(
        f"/api/v1/admin/achievements/{achievement_id}",
        json={"threshold": 8, "title": "Sakkiz tadbir"},
        headers=admin_headers(admin),
    )
    assert changed.status_code == 200
    assert changed.json()["threshold"] == 8
    assert changed.json()["code"] == "TEN_EVENTS"  # the code never changes
