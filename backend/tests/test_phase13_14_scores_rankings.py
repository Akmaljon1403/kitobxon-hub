"""Phases 13-14: score summaries, manual corrections, seasons and deterministic rankings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Faculty, FeatureFlag, ScoreTransaction, User
from app.models.enums import FeatureMode, ScoreCategory, UserStatus
from app.security.permissions import Perm
from app.services.ranking import display_name, period_start
from app.services.scoring import award_points
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


@pytest.fixture(autouse=True)
async def _full_ranking_for_everyone(db: AsyncSession) -> None:
    """These tests are about the order of the ranking; the Premium lock is tested elsewhere."""
    db.add(FeatureFlag(code="ranking_full", mode=FeatureMode.ALL))
    await db.commit()


async def _give(
    db: AsyncSession, user: User, amount: int, category: ScoreCategory = ScoreCategory.ATTENDANCE, **kwargs
) -> uuid.UUID:
    transaction_id = await award_points(
        db,
        user_id=user.id,
        amount=amount,
        category=category,
        idempotency_key=f"test:{uuid.uuid4()}",
        reason=kwargs.pop("reason", "Test uchun ball berildi" if category == ScoreCategory.MANUAL else None),
        **kwargs,
    )
    await db.commit()
    assert transaction_id is not None
    return transaction_id


async def _backdate(db: AsyncSession, transaction_id: uuid.UUID, when: datetime) -> None:
    """Test-only time travel: the ledger is append-only, so the guard trigger is paused briefly."""
    await db.execute(text("ALTER TABLE score_transactions DISABLE TRIGGER score_transactions_append_only"))
    await db.execute(update(ScoreTransaction).where(ScoreTransaction.id == transaction_id).values(created_at=when))
    await db.execute(text("ALTER TABLE score_transactions ENABLE TRIGGER score_transactions_append_only"))
    await db.commit()


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


# ---------------------------------------------------------------------------- personal summary


async def test_my_scores_breakdown_keeps_categories_separate(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    await _give(db, member, 30, ScoreCategory.ATTENDANCE)
    await _give(db, member, 18, ScoreCategory.TEST)
    await _give(db, member, 5, ScoreCategory.TEST_RANK_BONUS)

    response = await client.get("/api/v1/me/scores", headers=member_headers(member))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 53
    assert body["breakdown"] == {"ATTENDANCE": 30, "TEST": 18, "TEST_RANK_BONUS": 5}
    assert len(body["history"]) == 3
    assert body["history_count"] == 3


async def test_reversal_counts_against_original_category(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    manager = await _admin(db, Perm.SCORE_VIEW, Perm.SCORE_MANAGE)
    attendance_id = await _give(db, member, 30, ScoreCategory.ATTENDANCE)
    await _give(db, member, 20, ScoreCategory.TEST)

    reversed_ = await client.post(
        f"/api/v1/admin/scores/{attendance_id}/reverse",
        json={"reason": "Davomat noto'g'ri qayd etilgan"},
        headers=admin_headers(manager),
    )
    assert reversed_.status_code == 201
    body = (await client.get("/api/v1/me/scores", headers=member_headers(member))).json()
    assert body["total"] == 20
    assert body["breakdown"] == {"TEST": 20}
    assert next(item for item in body["history"] if item["id"] == str(attendance_id))["is_reversed"] is True

    twice = await client.post(
        f"/api/v1/admin/scores/{attendance_id}/reverse",
        json={"reason": "Yana bir marta bekor qilish"},
        headers=admin_headers(manager),
    )
    assert twice.status_code == 409


# ---------------------------------------------------------------------------- manual corrections


async def test_manual_adjustment_requires_permission_reason_and_is_audited(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    member = await create_user(db)
    viewer = await _admin(db, Perm.SCORE_VIEW)
    manager = await _admin(db, Perm.SCORE_VIEW, Perm.SCORE_MANAGE)
    await _give(db, member, 30)

    body = {"user_id": str(member.id), "amount": 5, "reason": "Texnik nosozlik tasdiqlangani sababli tuzatildi"}
    assert (
        await client.post("/api/v1/admin/scores/adjust", json=body, headers=admin_headers(viewer))
    ).status_code == 403
    no_reason = {**body, "reason": ""}
    assert (
        await client.post("/api/v1/admin/scores/adjust", json=no_reason, headers=admin_headers(manager))
    ).status_code == 422
    zero = {**body, "amount": 0}
    assert (
        await client.post("/api/v1/admin/scores/adjust", json=zero, headers=admin_headers(manager))
    ).status_code == 400

    ok = await client.post("/api/v1/admin/scores/adjust", json=body, headers=admin_headers(manager))
    assert ok.status_code == 201
    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "SCORE_ADJUST"))
    assert entry.actor_user_id == manager.id
    assert entry.before == {"total": 30}
    assert entry.after == {"total": 35, "amount": 5}
    assert entry.reason == body["reason"]

    ledger = await client.get(f"/api/v1/admin/scores?user_id={member.id}", headers=admin_headers(viewer))
    assert ledger.json()["total"] == 2
    summary = await client.get(f"/api/v1/admin/scores/summary?user_id={member.id}", headers=admin_headers(viewer))
    assert summary.json()["total"] == 35
    assert summary.json()["breakdown"] == {"ATTENDANCE": 30, "MANUAL": 5}
    # The admin dashboard reads the public leaderboard with its admin token.
    board = await client.get("/api/v1/rankings?limit=5", headers=admin_headers(viewer))
    assert board.status_code == 200
    assert board.json()["items"][0]["total"] == 35


async def test_member_cannot_submit_own_score(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """There is no endpoint that accepts a score from a member; admin endpoints reject member tokens."""
    member = await create_user(db)
    await db.commit()
    response = await client.post(
        "/api/v1/admin/scores/adjust",
        json={"user_id": str(member.id), "amount": 1000, "reason": "O'zimga ball qo'shaman"},
        headers=member_headers(member),
    )
    assert response.status_code == 403
    assert await db.scalar(select(func.count()).select_from(ScoreTransaction)) == 0


# ---------------------------------------------------------------------------- rankings


async def test_ranking_order_and_tie_breaks(client: httpx.AsyncClient, db: AsyncSession) -> None:
    first = await create_user(db, first_name="Ali", last_name="Valiyev")
    second = await create_user(db, first_name="Bobur", last_name="Karimov")
    third = await create_user(db, first_name="Dilnoza", last_name="Rahimova")
    await db.commit()
    # Same total (50): more attendance points wins.
    await _give(db, first, 30, ScoreCategory.ATTENDANCE)
    await _give(db, first, 20, ScoreCategory.TEST)
    await _give(db, second, 50, ScoreCategory.TEST)
    # Same total and same split as `first`, but reached later -> ranked after `first`.
    await _give(db, third, 30, ScoreCategory.ATTENDANCE)
    await _give(db, third, 20, ScoreCategory.TEST)

    response = await client.get("/api/v1/rankings?period=all", headers=member_headers(second))
    items = response.json()["items"]
    assert [item["name"] for item in items] == ["Ali V.", "Dilnoza R.", "Bobur K."]
    assert [item["rank"] for item in items] == [1, 2, 3]
    assert items[2]["is_me"] is True
    assert response.json()["me"]["rank"] == 3
    # Personal data is never part of the leaderboard.
    assert "phone" not in response.text and str(first.telegram_id) not in response.text


async def test_ranking_is_deterministic(client: httpx.AsyncClient, db: AsyncSession) -> None:
    users = [await create_user(db) for _ in range(5)]
    await db.commit()
    for user in users:
        await _give(db, user, 10)
    headers = member_headers(users[0])
    first = (await client.get("/api/v1/rankings", headers=headers)).json()["items"]
    second = (await client.get("/api/v1/rankings", headers=headers)).json()["items"]
    assert first == second


async def test_weekly_ranking_ignores_older_points(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    old = await _give(db, member, 100)
    await _give(db, member, 10)
    await _backdate(db, old, datetime.now(UTC) - timedelta(days=40))

    week = (await client.get("/api/v1/rankings?period=week", headers=member_headers(member))).json()
    overall = (await client.get("/api/v1/rankings?period=all", headers=member_headers(member))).json()
    assert week["me"]["total"] == 10
    assert overall["me"]["total"] == 110


async def test_reversal_affects_period_of_original(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    manager = await _admin(db, Perm.SCORE_VIEW, Perm.SCORE_MANAGE)
    old = await _give(db, member, 30)
    await _backdate(db, old, datetime.now(UTC) - timedelta(days=40))
    await _give(db, member, 10)
    await client.post(
        f"/api/v1/admin/scores/{old}/reverse", json={"reason": "Eski xato tuzatildi"}, headers=admin_headers(manager)
    )
    week = (await client.get("/api/v1/rankings?period=week", headers=member_headers(member))).json()
    assert week["me"]["total"] == 10  # this week's ranking is not reduced by last month's correction


async def test_faculty_and_group_scopes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    pediatrics = Faculty(name="Pediatriya")
    medicine = Faculty(name="Davolash ishi")
    db.add_all([pediatrics, medicine])
    await db.commit()
    me = await create_user(db, faculty_id=pediatrics.id, group_name="301")
    classmate = await create_user(db, faculty_id=pediatrics.id, group_name="301")
    same_faculty = await create_user(db, faculty_id=pediatrics.id, group_name="302")
    other = await create_user(db, faculty_id=medicine.id, group_name="301")
    await db.commit()
    for user, points in ((me, 10), (classmate, 20), (same_faculty, 30), (other, 40)):
        await _give(db, user, points)
    headers = member_headers(me)

    faculty = (await client.get("/api/v1/rankings?scope=faculty", headers=headers)).json()
    assert [item["total"] for item in faculty["items"]] == [30, 20, 10]
    group = (await client.get("/api/v1/rankings?scope=group", headers=headers)).json()
    assert [item["total"] for item in group["items"]] == [20, 10]

    faculties = (await client.get("/api/v1/rankings/faculties", headers=headers)).json()
    assert faculties[0]["faculty"] == "Davolash ishi" and faculties[0]["average"] == 40.0
    assert faculties[1] == {"rank": 2, "faculty": "Pediatriya", "members": 3, "total": 60, "average": 20.0}


async def test_inactive_members_are_not_ranked(client: httpx.AsyncClient, db: AsyncSession) -> None:
    active = await create_user(db)
    blocked = await create_user(db, status=UserStatus.BLOCKED)
    await db.commit()
    await _give(db, active, 5)
    await _give(db, blocked, 500)
    items = (await client.get("/api/v1/rankings", headers=member_headers(active))).json()["items"]
    assert [item["total"] for item in items] == [5]


async def test_full_name_format_setting(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from app.models import SystemSetting

    member = await create_user(db, first_name="Malika", last_name="Yusupova")
    setting = await db.get(SystemSetting, "ranking.public_name_format")
    setting.value = "FULL"
    await db.commit()
    await _give(db, member, 5)
    items = (await client.get("/api/v1/rankings", headers=member_headers(member))).json()["items"]
    assert items[0]["name"] == "Malika Yusupova"


async def test_my_ranking_summary(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    body = (await client.get("/api/v1/me/ranking", headers=member_headers(member))).json()
    assert body == {"week": None, "month": None, "all": None}  # no points yet
    await _give(db, member, 5)
    body = (await client.get("/api/v1/me/ranking", headers=member_headers(member))).json()
    assert body["all"]["rank"] == 1 and body["week"]["total"] == 5


def test_period_start_uses_tashkent_calendar() -> None:
    from zoneinfo import ZoneInfo

    # Wednesday 1 October 2026, 02:00 in Tashkent = Tuesday 30 September 21:00 UTC.
    now = datetime(2026, 9, 30, 21, 0, tzinfo=UTC)
    week = period_start("week", now)
    month = period_start("month", now)
    assert week.astimezone(ZoneInfo("Asia/Tashkent")).isoformat() == "2026-09-28T00:00:00+05:00"
    assert month.astimezone(ZoneInfo("Asia/Tashkent")).isoformat() == "2026-10-01T00:00:00+05:00"


def test_display_name_formats() -> None:
    assert display_name("Akmaljon", "Bahodirov", "SHORT") == "Akmaljon B."
    assert display_name("Akmaljon", "Bahodirov", "FULL") == "Akmaljon Bahodirov"


# ---------------------------------------------------------------------------- seasons


async def test_seasons_and_season_ranking(client: httpx.AsyncClient, db: AsyncSession) -> None:
    manager = await _admin(db, Perm.SEASON_MANAGE, Perm.SCORE_VIEW)
    member = await create_user(db)
    await db.commit()
    await _give(db, member, 40)  # before any season

    created = await client.post(
        "/api/v1/admin/seasons",
        json={"name": "2026 Kuz", "starts_on": "2026-09-01", "ends_on": "2026-12-31"},
        headers=admin_headers(manager),
    )
    assert created.status_code == 201 and created.json()["is_current"] is True
    await _give(db, member, 7)  # inside the season

    season = (await client.get("/api/v1/rankings?period=season", headers=member_headers(member))).json()
    assert season["me"]["total"] == 7
    scores = (await client.get("/api/v1/me/scores", headers=member_headers(member))).json()
    assert scores["season"] == {"name": "2026 Kuz", "total": 7}
    assert scores["total"] == 47  # history is kept

    spring = await client.post(
        "/api/v1/admin/seasons",
        json={"name": "2027 Bahor", "starts_on": "2027-02-01", "ends_on": "2027-06-30"},
        headers=admin_headers(manager),
    )
    listing = (await client.get("/api/v1/admin/seasons", headers=admin_headers(manager))).json()
    current = [item["name"] for item in listing if item["is_current"]]
    assert current == ["2027 Bahor"] and spring.status_code == 201


async def test_admin_detailed_rankings_endpoint(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """The admin panel's detailed standings (Q7): full order with each member's points, attendance and
    test counts — reachable with SCORE_VIEW and without the member-side premium gate."""
    admin = await _admin(db, Perm.SCORE_VIEW)
    top = await create_user(db, first_name="Aziz", last_name="Katta")
    low = await create_user(db, first_name="Vali", last_name="Kam")
    await db.commit()
    await _give(db, top, 50, ScoreCategory.ATTENDANCE)
    await _give(db, top, 20, ScoreCategory.TEST)
    await _give(db, low, 10, ScoreCategory.ATTENDANCE)

    board = await client.get("/api/v1/admin/scores/rankings?period=all&limit=100", headers=admin_headers(admin))
    assert board.status_code == 200, board.text
    items = board.json()["items"]
    assert [row["total"] for row in items] == [70, 10]
    assert [row["rank"] for row in items] == [1, 2]
    for key in ("name", "faculty", "group_name", "attendance", "tests", "premium"):
        assert key in items[0]

    # SCORE_VIEW is required: an ordinary member cannot read the admin standings.
    denied = await client.get("/api/v1/admin/scores/rankings", headers=member_headers(low))
    assert denied.status_code == 403
