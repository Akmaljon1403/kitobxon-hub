"""Promo-code giveaways: random draw, test leaders, event places, ranking; schedule and monthly repeat."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    Giveaway,
    Notification,
    PremiumSubscription,
    Reward,
    ScoreTransaction,
    TestAttempt,
    User,
    UserReward,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceMethod,
    GiveawayRule,
    GiveawayStatus,
    NotificationType,
    PremiumSource,
    RewardType,
    ScoreCategory,
    TestStatus,
)
from app.security.permissions import Perm
from app.services import giveaways as giveaway_service
from app.services import rewards as reward_service
from app.utils.timezone import local_tz
from tests.factories import create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _manager(db: AsyncSession) -> User:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.REWARD_MANAGE)
    return admin


async def _reward(db: AsyncSession, admin: User, codes: int = 0, title: str = "Kitob ilovasi — 1 oy") -> Reward:
    reward = await reward_service.create_reward(
        db, actor_id=admin.id, data={"title": title, "type": RewardType.SUBSCRIPTION_CODE}
    )
    if codes:
        await reward_service.add_codes(
            db,
            actor_id=admin.id,
            reward_id=reward.id,
            codes=[f"KOD-{uuid.uuid4().hex[:8]}" for _ in range(codes)],
            expires_at=None,
        )
    return reward


def _today() -> date:
    return datetime.now(local_tz()).date()


def _body(reward: Reward, **values: Any) -> dict[str, Any]:
    body = {
        "title": "Oy sovg'asi",
        "reward_id": str(reward.id),
        "rule": "RANDOM",
        "winners_count": 2,
        "period_start": str(_today() - timedelta(days=20)),
        "period_end": str(_today()),
    }
    body.update(values)
    return body


async def _premium(db: AsyncSession, user: User) -> None:
    now = datetime.now(UTC)
    db.add(
        PremiumSubscription(
            user_id=user.id,
            source=PremiumSource.MANUAL,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=20),
        )
    )
    await db.flush()


async def test_random_draw_with_codes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _manager(db)
    members = [await create_user(db, first_name=f"Aziz{i}", last_name="Karimov") for i in range(5)]
    await create_user(db, registered_at=None)  # not registered: never takes part
    await _premium(db, members[0])
    await db.commit()
    reward = await _reward(db, admin, codes=3)
    headers = admin_headers(admin)

    assert (await client.get("/api/v1/admin/giveaways", headers=member_headers(members[0]))).status_code == 403
    created = await client.post("/api/v1/admin/giveaways", json=_body(reward), headers=headers)
    assert created.status_code == 201, created.text
    giveaway = created.json()
    assert (
        giveaway["status"] == "DRAFT" and giveaway["codes_available"] == 3 and giveaway["rule_title"].startswith("🎲")
    )

    preview = (await client.get(f"/api/v1/admin/giveaways/{giveaway['id']}/preview", headers=headers)).json()
    assert preview["eligible"] == 5 and preview["premium"] == 1 and preview["winners"] == []  # the admin is out

    drawn = await client.post(f"/api/v1/admin/giveaways/{giveaway['id']}/draw", headers=headers)
    assert drawn.status_code == 200, drawn.text
    result = drawn.json()
    assert result["status"] == "DONE" and len(result["seed"]) == 32 and len(result["winners"]) == 2
    winner_ids = {uuid.UUID(w["user_id"]) for w in result["winners"]}
    assert winner_ids <= {m.id for m in members} and all(
        w["full_name"].startswith("Karimov") for w in result["winners"]
    )
    assert (await client.post(f"/api/v1/admin/giveaways/{giveaway['id']}/draw", headers=headers)).status_code == 409

    given = list(await db.scalars(select(UserReward).where(UserReward.reward_id == reward.id)))
    assert {row.user_id for row in given} == winner_ids and all(row.reward_code_id for row in given)
    personal = await db.scalar(
        select(Notification.text).where(
            Notification.user_id == next(iter(winner_ids)), Notification.dedup_key.like("reward:%")
        )
    )
    assert "g'olibisiz" in personal and "Kitob ilovasi — 1 oy" in personal
    announced = await db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.dedup_key.like(f"giveaway:{giveaway['id']}:announce:%"))
    )
    assert announced >= 5
    winner = next(m for m in members if m.id in winner_ids)
    own = await client.get("/api/v1/me/rewards", headers=member_headers(winner))
    assert own.json()[0]["has_code"] is True

    public = (await client.get("/api/v1/me/giveaways", headers=member_headers(members[1]))).json()
    assert public["upcoming"] == [] and public["recent"][0]["title"] == "Oy sovg'asi"
    assert "user_id" not in public["recent"][0]["winners"][0] and len(public["recent"][0]["winners"]) == 2

    # One code left, three winners wanted: nothing changes until codes are added.
    second = (await client.post("/api/v1/admin/giveaways", json=_body(reward, winners_count=3), headers=headers)).json()
    preview = (await client.get(f"/api/v1/admin/giveaways/{second['id']}/preview", headers=headers)).json()
    assert any("Kodlar yetmaydi" in note for note in preview["notes"])
    short = await client.post(f"/api/v1/admin/giveaways/{second['id']}/draw", headers=headers)
    assert short.status_code == 409 and short.json()["error"]["code"] == "NO_CODES_LEFT"
    await reward_service.add_codes(db, actor_id=admin.id, reward_id=reward.id, codes=["A1", "A2"], expires_at=None)
    again = await client.post(f"/api/v1/admin/giveaways/{second['id']}/draw", headers=headers)
    assert again.status_code == 200 and len(again.json()["winners"]) == 3  # earlier winners may win again

    cancelled = (await client.post("/api/v1/admin/giveaways", json=_body(reward), headers=headers)).json()
    assert (await client.post(f"/api/v1/admin/giveaways/{cancelled['id']}/cancel", headers=headers)).json()[
        "status"
    ] == "CANCELLED"
    assert (await client.post(f"/api/v1/admin/giveaways/{cancelled['id']}/draw", headers=headers)).status_code == 409


async def test_premium_members_have_double_chance(db: AsyncSession) -> None:
    admin = await _manager(db)
    regular, premium = await create_user(db), await create_user(db)
    await _premium(db, premium)
    await db.commit()
    reward = await _reward(db, admin)
    giveaway = Giveaway(
        title="Sinov",
        reward_id=reward.id,
        rule=GiveawayRule.RANDOM,
        winners_count=1,
        period_start=_today(),
        period_end=_today(),
        premium_bonus=True,
    )
    wins = 0
    for index in range(600):
        draw = await giveaway_service.pick(db, giveaway, seed=f"s{index}")
        wins += draw.winners[0].user_id == premium.id
    assert 0.58 < wins / 600 < 0.75  # 2 : 1 → about two thirds
    # The same seed always gives the same winner (the draw can be re-checked).
    first = await giveaway_service.pick(db, giveaway, seed="published")
    assert (await giveaway_service.pick(db, giveaway, seed="published")).winners[0].user_id == first.winners[0].user_id
    assert regular.id != premium.id


async def _attempt(db: AsyncSession, test_id: Any, user: User, score: int) -> None:
    started = datetime.now(UTC) - timedelta(minutes=30)
    db.add(
        TestAttempt(
            test_id=test_id,
            user_id=user.id,
            status=AttemptStatus.SUBMITTED,
            started_at=started,
            deadline_at=started + timedelta(minutes=15),
            submitted_at=started + timedelta(minutes=5),
            question_order=[],
            option_order={},
            correct_count=score,
            raw_score=score,
            raw_max=20,
            score=score,
        )
    )
    await db.flush()


async def test_event_places_test_top_and_ranking(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _manager(db)
    a, b, c, d = [await create_user(db, first_name=name, last_name="Aliyev") for name in ("Ali", "Bek", "Vali", "Gul")]
    now = datetime.now(UTC)
    first = await create_event(db, title="Kitob kechasi", starts_at=now - timedelta(days=6))
    second = await create_event(db, title="Navoiy kuni", starts_at=now - timedelta(days=2))
    third = await create_event(db, title="Ochiq test", starts_at=now - timedelta(days=1))
    test1 = await create_test(db, event_id=first.id, status=TestStatus.CLOSED, starts_at=now - timedelta(days=6))
    test2 = await create_test(db, event_id=second.id, status=TestStatus.CLOSED, starts_at=now - timedelta(days=2))
    await create_test(db, event_id=third.id, starts_at=now - timedelta(days=1))  # still open
    for member in (a, b, c):
        db.add(AttendanceRecord(event_id=first.id, user_id=member.id, method=AttendanceMethod.CODE))
    for member in (a, d):
        db.add(AttendanceRecord(event_id=second.id, user_id=member.id, method=AttendanceMethod.CODE))
    await _attempt(db, test1.id, d, 20)  # did not attend the first event: no place there
    await _attempt(db, test1.id, b, 18)
    await _attempt(db, test1.id, a, 15)
    await _attempt(db, test1.id, c, 12)
    await _attempt(db, test2.id, a, 19)
    await _attempt(db, test2.id, d, 11)
    for member, amount, category in (
        (c, 40, ScoreCategory.TEST),
        (b, 25, ScoreCategory.TEST),
        (d, 90, ScoreCategory.ATTENDANCE),
    ):
        db.add(
            ScoreTransaction(user_id=member.id, amount=amount, category=category, idempotency_key=f"t:{uuid.uuid4()}")
        )
    await db.commit()
    reward = await _reward(db, admin, title="Kitob — sovg'a")  # no codes: a book handed over in person
    headers = admin_headers(admin)

    places = (
        await client.post(
            "/api/v1/admin/giveaways", json=_body(reward, rule="EVENT_PLACES", winners_count=3), headers=headers
        )
    ).json()
    preview = (await client.get(f"/api/v1/admin/giveaways/{places['id']}/preview", headers=headers)).json()
    assert [(w["name"], w["place"]) for w in preview["winners"]] == [
        ("Bek A.", 1),
        ("Ali A.", 2),
        ("Vali A.", 3),
        ("Ali A.", 1),
        ("Gul A.", 2),
    ]
    assert preview["winners"][0]["reason"] == "«Kitob kechasi» — 1-o'rin"
    assert any("«Ochiq test» testi hali yopilmagan" in note for note in preview["notes"])
    drawn = (await client.post(f"/api/v1/admin/giveaways/{places['id']}/draw", headers=headers)).json()
    assert len(drawn["winners"]) == 5 and not any(w.get("error") for w in drawn["winners"])
    assert await db.scalar(select(func.count()).select_from(UserReward).where(UserReward.user_id == a.id)) == 2

    too_many = await client.post(
        "/api/v1/admin/giveaways", json=_body(reward, rule="EVENT_PLACES", winners_count=11), headers=headers
    )
    assert too_many.status_code == 400

    top = (
        await client.post(
            "/api/v1/admin/giveaways", json=_body(reward, rule="TEST_TOP", winners_count=1), headers=headers
        )
    ).json()
    preview = (await client.get(f"/api/v1/admin/giveaways/{top['id']}/preview", headers=headers)).json()
    assert [(w["name"], w["reason"]) for w in preview["winners"]] == [("Vali A.", "Testlarda 40 ball — 1-o'rin")]

    leaders = (
        await client.post(
            "/api/v1/admin/giveaways", json=_body(reward, rule="RANKING_TOP", winners_count=2), headers=headers
        )
    ).json()
    preview = (await client.get(f"/api/v1/admin/giveaways/{leaders['id']}/preview", headers=headers)).json()
    assert [w["name"] for w in preview["winners"]] == ["Gul A.", "Vali A."]
    assert preview["winners"][0]["reason"] == "Reytingda 1-o'rin (90 ball)"

    # Outside the period nobody wins: the draw is refused and nothing is recorded.
    old = (
        await client.post(
            "/api/v1/admin/giveaways",
            json=_body(reward, rule="TEST_TOP", period_start="2026-01-01", period_end="2026-01-31"),
            headers=headers,
        )
    ).json()
    empty = await client.post(f"/api/v1/admin/giveaways/{old['id']}/draw", headers=headers)
    assert empty.status_code == 409 and empty.json()["error"]["code"] == "NO_WINNERS"


async def test_scheduled_draw_repeats_monthly(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _manager(db)
    for _ in range(3):
        await create_user(db)
    await db.commit()
    reward = await _reward(db, admin)
    headers = admin_headers(admin)
    month_start = _today().replace(day=1)
    body = _body(
        reward,
        title="Oylik tasodifiy sovg'a",
        winners_count=1,
        period_start=str(month_start),
        period_end=str(giveaway_service.next_period(month_start, month_start)[0] - timedelta(days=1)),
        scheduled_at=(datetime.now(UTC) + timedelta(hours=2)).isoformat(),
        repeat_monthly=True,
    )
    body["period_end"] = str(
        giveaway_service.next_period(month_start, month_start.replace(day=28))[0].replace(day=1) - timedelta(days=1)
    )
    past = await client.post(
        "/api/v1/admin/giveaways", json={**body, "scheduled_at": "2026-01-01T10:00:00+05:00"}, headers=headers
    )
    assert past.status_code == 400
    created = (await client.post("/api/v1/admin/giveaways", json=body, headers=headers)).json()
    assert created["status"] == "SCHEDULED"
    member_view = (await client.get("/api/v1/me/giveaways", headers=headers)).json()
    assert member_view["upcoming"][0]["title"] == "Oylik tasodifiy sovg'a"

    assert await giveaway_service.run_due(db) == 0  # not yet
    await db.execute(
        update(Giveaway).where(Giveaway.id == uuid.UUID(created["id"])).values(scheduled_at=datetime.now(UTC))
    )
    await db.commit()
    assert await giveaway_service.run_due(db) == 1
    rows = list(await db.scalars(select(Giveaway).order_by(Giveaway.created_at)))
    assert [row.status for row in rows] == [GiveawayStatus.DONE, GiveawayStatus.SCHEDULED]
    following = rows[1]
    assert following.period_start == giveaway_service.next_period(rows[0].period_start, rows[0].period_end)[0]
    assert following.period_start.day == 1 and following.repeat_monthly and following.scheduled_at > datetime.now(UTC)

    # A scheduled giveaway that cannot be drawn waits; the admins hear about it once.
    admin_id = admin.id  # the failed draws below roll the session back (expiring loaded objects)
    rewarded = await _reward(db, admin, codes=1, title="Kod")
    await reward_service.assign(db, actor_id=admin.id, reward_id=rewarded.id, user_id=admin.id, note=None)
    stuck = (
        await client.post(
            "/api/v1/admin/giveaways",
            json=_body(rewarded, scheduled_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()),
            headers=headers,
        )
    ).json()
    await db.execute(
        update(Giveaway).where(Giveaway.id == uuid.UUID(stuck["id"])).values(scheduled_at=datetime.now(UTC))
    )
    await db.commit()
    assert await giveaway_service.run_due(db) == 0
    assert await giveaway_service.run_due(db) == 0
    warnings = list(
        await db.scalars(
            select(Notification.text).where(
                Notification.user_id == admin_id,
                Notification.type == NotificationType.SYSTEM,
                Notification.dedup_key.like(f"giveaway:{stuck['id']}:failed%"),
            )
        )
    )
    assert len(warnings) == 1 and "kodlar yetmaydi" in warnings[0]
    assert (await db.get(Giveaway, uuid.UUID(stuck["id"]))).status == GiveawayStatus.SCHEDULED


def test_periods() -> None:
    assert giveaway_service.next_period(date(2026, 10, 1), date(2026, 10, 31)) == (
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert giveaway_service.next_period(date(2026, 12, 1), date(2026, 12, 31)) == (date(2027, 1, 1), date(2027, 1, 31))
    assert giveaway_service.next_period(date(2026, 1, 15), date(2026, 1, 31)) == (date(2026, 2, 15), date(2026, 2, 28))
    assert giveaway_service.period_label(date(2026, 10, 1), date(2026, 10, 31)) == "2026-yil oktabr"
    assert giveaway_service.period_label(date(2026, 10, 5), date(2026, 10, 12)) == "05.10.2026 — 12.10.2026"
