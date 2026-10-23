"""Phase 20: analytics aggregates and the inactive-members list."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    BookRead,
    BookReflection,
    Faculty,
    ScoreTransaction,
    ShelfItem,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceMethod,
    AttendanceStatus,
    BookStatus,
    ReadingStatus,
    ScoreCategory,
    ShelfStatus,
)
from app.security.permissions import Perm
from app.services.analytics import _month_starts
from app.services.scoring import award_points
from app.utils.timezone import local_tz
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


def test_month_starts_cross_year_boundaries() -> None:
    starts = _month_starts(4, datetime(2026, 2, 15).date())
    assert [f"{start:%Y-%m}" for start in starts] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert all(start.tzinfo == local_tz() for start in starts)


async def test_overview_aggregates(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.ANALYTICS_VIEW)
    faculty = Faculty(name="Pediatriya")
    db.add(faculty)
    await db.flush()
    members = [await create_user(db, faculty_id=faculty.id, group_name="201") for _ in range(3)]
    loner = await create_user(db, faculty_id=faculty.id, group_name="305")
    event = await create_event(db)
    for member in members[:2]:
        db.add(
            AttendanceRecord(
                event_id=event.id, user_id=member.id, method=AttendanceMethod.QR, status=AttendanceStatus.VERIFIED
            )
        )
        await award_points(
            db, user_id=member.id, amount=30, category=ScoreCategory.ATTENDANCE, idempotency_key=f"a:{member.id}"
        )
    book = await create_book(db, status=BookStatus.ACTIVE, title="Kecha va kunduz")
    db.add_all(
        [
            BookRead(
                book_id=book.id, user_id=members[0].id, status=ReadingStatus.COMPLETED, completed_at=datetime.now(UTC)
            ),
            BookRead(book_id=book.id, user_id=members[1].id, status=ReadingStatus.READING),
        ]
    )
    test = await create_test(db, title="Test 1", max_score=20, passing_score=10)
    now = datetime.now(UTC)
    for member, score in ((members[0], 20), (members[1], 5)):
        db.add(
            TestAttempt(
                test_id=test.id,
                user_id=member.id,
                status=AttemptStatus.SUBMITTED,
                started_at=now - timedelta(minutes=5),
                deadline_at=now,
                submitted_at=now - timedelta(minutes=1),
                question_order=[],
                option_order={},
                score=score,
            )
        )
    await db.commit()

    response = await client.get("/api/v1/admin/analytics?months=3", headers=admin_headers(admin))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["months"]) == 3
    assert body["months"][-1] == f"{datetime.now(local_tz()):%Y-%m}"
    # admin + 3 members + loner are active members; 2 of them earned activity points this month;
    # the others registered just now, so they are not counted as inactive yet
    assert body["headline"]["members"] == 5
    assert body["headline"]["active_30_days"] == 2
    assert body["headline"]["inactive_30_days"] == 0
    assert body["headline"]["average_test_percent"] == 62.5
    assert body["by_month"]["attendance"][-1] == 2
    assert body["by_month"]["active_members"][-1] == 2
    assert body["by_month"]["books_completed"][-1] == 1
    assert body["by_month"]["new_members"][-1] == 5

    distribution = {row["bucket"]: row["members"] for row in body["points_distribution"]}
    assert distribution["0"] == 3 and distribution["1–49"] == 2

    pediatriya = next(row for row in body["faculties"] if row["name"] == "Pediatriya")
    assert pediatriya == {
        "name": "Pediatriya",
        "members": 4,
        "active_30_days": 2,
        "total_points": 60,
        "average_points": 15.0,
        "attendance": 2,
    }
    # Group 305 has a single member, so it is not shown (privacy).
    assert [row["group"] for row in body["groups"]] == ["201"]
    assert body["tests"][0] == {
        "title": "Test 1",
        "participants": 2,
        "average_percent": 62.5,
        "pass_rate": 50.0,
        "ends_at": body["tests"][0]["ends_at"],
    }
    campaign = next(row for row in body["books"] if row["title"] == "Kecha va kunduz")
    assert (campaign["readers"], campaign["completed"], campaign["completion_rate"]) == (2, 1, 50.0)
    assert loner.first_name not in response.text  # no names in aggregates


async def test_overview_top_rated_books(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.ANALYTICS_VIEW)
    loved = await create_book(db, status=BookStatus.ACTIVE, title="Sevimli")
    plain = await create_book(db, status=BookStatus.ACTIVE, title="Oddiy")
    readers = [await create_user(db) for _ in range(3)]
    for user, rating in zip(readers, (5, 4, 3), strict=True):
        db.add(ShelfItem(user_id=user.id, book_id=loved.id, status=ShelfStatus.FINISHED, rating=rating))
    db.add(ShelfItem(user_id=readers[0].id, book_id=plain.id, status=ShelfStatus.FINISHED, rating=2))
    # A rating with no stars set must be ignored, not counted as zero.
    db.add(ShelfItem(user_id=readers[1].id, book_id=plain.id, status=ShelfStatus.READING, rating=None))
    await db.commit()

    body = (await client.get("/api/v1/admin/analytics?months=3", headers=admin_headers(admin))).json()
    top = {row["title"]: row for row in body["top_rated"]}
    assert top["Sevimli"] == {"title": "Sevimli", "author": top["Sevimli"]["author"], "average": 4.0, "ratings": 3}
    assert top["Oddiy"]["average"] == 2.0 and top["Oddiy"]["ratings"] == 1
    # Most-loved first.
    assert [row["title"] for row in body["top_rated"]] == ["Sevimli", "Oddiy"]


async def test_reflections_need_user_view(client: httpx.AsyncClient, db: AsyncSession) -> None:
    analyst = await _admin(db, Perm.ANALYTICS_VIEW)
    manager = await _admin(db, Perm.ANALYTICS_VIEW, Perm.USER_VIEW)
    reader = await create_user(db, first_name="Dilnoza")
    book = await create_book(db, status=BookStatus.ACTIVE, title="Mehrobdan chayon")
    shelf = ShelfItem(user_id=reader.id, book_id=book.id, status=ShelfStatus.FINISHED, rating=5)
    db.add(shelf)
    await db.flush()
    db.add(
        BookReflection(
            user_id=reader.id,
            shelf_item_id=shelf.id,
            main_idea="Vatanparvarlik",
            favorite_moment="Oxirgi bob",
            apply_in_life="Kundalik o'qishni davom ettiraman",
        )
    )
    await db.commit()

    assert (await client.get("/api/v1/admin/analytics/reflections", headers=admin_headers(analyst))).status_code == 403
    response = await client.get("/api/v1/admin/analytics/reflections", headers=admin_headers(manager))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["first_name"] == "Dilnoza"
    assert item["book_title"] == "Mehrobdan chayon"
    assert item["rating"] == 5
    assert item["main_idea"] == "Vatanparvarlik"
    assert item["apply_in_life"] == "Kundalik o'qishni davom ettiraman"


async def test_inactive_members_list_needs_user_view(client: httpx.AsyncClient, db: AsyncSession) -> None:
    analyst = await _admin(db, Perm.ANALYTICS_VIEW)
    manager = await _admin(db, Perm.ANALYTICS_VIEW, Perm.USER_VIEW)
    quiet = await create_user(db, first_name="Sokin", registered_at=datetime.now(UTC) - timedelta(days=90))
    busy = await create_user(db, first_name="Faol", registered_at=datetime.now(UTC) - timedelta(days=90))
    newcomer = await create_user(db, first_name="Yangi")
    await award_points(db, user_id=busy.id, amount=30, category=ScoreCategory.ATTENDANCE, idempotency_key="busy")
    await db.commit()
    quiet_id, busy_id, newcomer_id = quiet.id, busy.id, newcomer.id

    assert (await client.get("/api/v1/admin/analytics/inactive", headers=admin_headers(analyst))).status_code == 403
    response = await client.get("/api/v1/admin/analytics/inactive?days=30", headers=admin_headers(manager))
    ids = {row["user_id"] for row in response.json()}
    assert str(quiet_id) in ids
    assert str(busy_id) not in ids
    assert str(newcomer_id) not in ids  # just registered — not "inactive" yet

    # Old activity counts as inactive again.
    await db.execute(text("ALTER TABLE score_transactions DISABLE TRIGGER score_transactions_append_only"))
    await db.execute(
        update(ScoreTransaction)
        .where(ScoreTransaction.user_id == busy_id)
        .values(created_at=datetime.now(UTC) - timedelta(days=45))
    )
    await db.execute(text("ALTER TABLE score_transactions ENABLE TRIGGER score_transactions_append_only"))
    await db.commit()
    response = await client.get("/api/v1/admin/analytics/inactive?days=30", headers=admin_headers(manager))
    assert str(busy_id) in {row["user_id"] for row in response.json()}
