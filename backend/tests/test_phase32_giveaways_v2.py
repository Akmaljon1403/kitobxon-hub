"""Giveaways, round two: Premium days and Premium discounts as prizes, «the first N who join the bot»."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Giveaway, Notification, PremiumDiscount, PremiumSubscription, User
from app.models.enums import GiveawayStatus, PremiumSource, ScoreCategory
from app.security.permissions import Perm
from app.services import giveaways as giveaway_service
from app.services import members as member_service
from app.services import premium as premium_service
from app.services.scoring import award_points
from app.utils.timezone import local_tz
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role


async def _manager(db: AsyncSession) -> User:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.REWARD_MANAGE)
    return admin


def _today() -> str:
    return str(datetime.now(local_tz()).date())


async def test_premium_days_and_discount_prizes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _manager(db)
    readers = [await create_user(db, first_name=f"O'quvchi{i}") for i in range(3)]
    for index, reader in enumerate(readers):
        await award_points(
            db, user_id=reader.id, amount=10 * (index + 1), category=ScoreCategory.TEST, idempotency_key=f"p{index}"
        )
    await db.commit()
    headers = admin_headers(admin)
    base = {"period_start": _today(), "period_end": _today()}

    no_reward = await client.post(
        "/api/v1/admin/giveaways",
        json={"title": "Kodsiz", "rule": "TEST_TOP", "winners_count": 1, **base},
        headers=headers,
    )
    assert no_reward.status_code == 400 and no_reward.json()["error"]["code"] == "REWARD_REQUIRED"
    too_much = await client.post(
        "/api/v1/admin/giveaways",
        json={
            "title": "Katta",
            "rule": "TEST_TOP",
            "winners_count": 1,
            "prize": "PREMIUM_DISCOUNT",
            "prize_value": 95,
            **base,
        },
        headers=headers,
    )
    assert too_much.status_code == 400

    days = (
        await client.post(
            "/api/v1/admin/giveaways",
            json={
                "title": "Test chempioni",
                "rule": "TEST_TOP",
                "winners_count": 1,
                "prize": "PREMIUM_DAYS",
                "prize_value": 30,
                **base,
            },
            headers=headers,
        )
    ).json()
    assert days["reward_title"] == "💎 30 kunlik Premium" and days["codes_available"] is None
    drawn = (await client.post(f"/api/v1/admin/giveaways/{days['id']}/draw", headers=headers)).json()
    champion = uuid.UUID(drawn["winners"][0]["user_id"])
    assert champion == readers[2].id
    subscription = await db.scalar(select(PremiumSubscription).where(PremiumSubscription.user_id == champion))
    assert subscription.source == PremiumSource.GIVEAWAY and (subscription.ends_at - subscription.starts_at).days == 30
    message = await db.scalar(select(Notification.text).where(Notification.dedup_key == f"giveaway:{days['id']}:win:0"))
    assert "30 kunlik Premium" in message

    discount = (
        await client.post(
            "/api/v1/admin/giveaways",
            json={
                "title": "Chegirma",
                "rule": "TEST_TOP",
                "winners_count": 2,
                "prize": "PREMIUM_DISCOUNT",
                "prize_value": 40,
                **base,
            },
            headers=headers,
        )
    ).json()
    await client.post(f"/api/v1/admin/giveaways/{discount['id']}/draw", headers=headers)
    given = list(await db.scalars(select(PremiumDiscount).order_by(PremiumDiscount.created_at)))
    assert [d.percent for d in given] == [40, 40] and given[0].giveaway_id == uuid.UUID(discount["id"])
    assert (await premium_service.active_discount(db, readers[1].id)).percent == 40


async def test_first_members_who_join_get_the_prize_at_once(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _manager(db)
    early = await create_user(db, registered_at=datetime.now(UTC) - timedelta(days=3))  # before the period
    await db.commit()
    headers = admin_headers(admin)
    body = {
        "title": "Birinchi 2 kishiga −50%",
        "rule": "NEW_MEMBERS",
        "winners_count": 2,
        "prize": "PREMIUM_DISCOUNT",
        "prize_value": 50,
        "period_start": _today(),
        "period_end": _today(),
        "scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    created = (await client.post("/api/v1/admin/giveaways", json=body, headers=headers)).json()
    assert created["status"] == "SCHEDULED" and created["rule_title"].startswith("🆕")

    newcomers = [await create_user(db, first_name=f"Yangi{i}") for i in range(3)]
    await db.commit()
    ids = [user.id for user in newcomers]
    for user_id in ids:
        await member_service.after_registration(db, user_id)
    await member_service.after_registration(db, ids[0])  # running it again changes nothing
    winners = {d.user_id for d in await db.scalars(select(PremiumDiscount))}
    assert winners == set(ids[:2])  # the third came too late
    giveaway = await db.get(Giveaway, uuid.UUID(created["id"]))
    await db.refresh(giveaway)
    assert [entry["user_id"] for entry in giveaway.results] == [str(i) for i in ids[:2]]
    note = await db.scalar(
        select(Notification.text).where(Notification.dedup_key == f"giveaway:{created['id']}:win:new:{ids[0]}")
    )
    assert "Botga qo'shilgan 1-a'zo" in note and "−50%" in note

    # The end of the period: the giveaway closes without giving anything twice.
    await db.execute(update(Giveaway).where(Giveaway.id == giveaway.id).values(scheduled_at=datetime.now(UTC)))
    await db.commit()
    assert await giveaway_service.run_due(db) == 1
    assert await db.scalar(select(func.count()).select_from(PremiumDiscount)) == 2
    await db.refresh(giveaway)
    assert giveaway.status == GiveawayStatus.DONE and len(giveaway.results) == 2
    assert str(early.id) not in [entry["user_id"] for entry in giveaway.results]
    public = (await client.get("/api/v1/me/giveaways", headers=headers)).json()
    assert public["recent"][0]["reward"] == "🎟 Premium'ga −50% chegirma"


async def test_rewards_for_test_places_once_per_place(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from app.models import AttendanceRecord, TestAttempt
    from app.models.enums import AttemptStatus, AttendanceMethod, RewardType, TestStatus
    from app.services import rewards as reward_service
    from tests.factories import create_event, create_test

    admin = await _manager(db)
    a, b, c = [await create_user(db, first_name=name, last_name="Karimov") for name in ("Aziz", "Bobur", "Komil")]
    now = datetime.now(UTC)
    event = await create_event(db, title="Kitob kechasi", starts_at=now - timedelta(days=2))
    first = await create_test(
        db, title="Birinchi test", event_id=event.id, status=TestStatus.CLOSED, starts_at=now - timedelta(days=2)
    )
    second = await create_test(db, title="Ikkinchi test", status=TestStatus.CLOSED, starts_at=now - timedelta(days=1))
    for member in (a, b):
        db.add(AttendanceRecord(event_id=event.id, user_id=member.id, method=AttendanceMethod.CODE))
    started = now - timedelta(hours=3)
    for test, member, score in ((first, c, 20), (first, a, 18), (first, b, 15), (second, a, 19), (second, c, 12)):
        db.add(
            TestAttempt(
                test_id=test.id,
                user_id=member.id,
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
    await db.commit()
    reward = await reward_service.create_reward(
        db, actor_id=admin.id, data={"title": "Kitob ilovasi", "type": RewardType.SUBSCRIPTION_CODE}
    )
    await reward_service.add_codes(
        db, actor_id=admin.id, reward_id=reward.id, codes=["K1", "K2", "K3"], expires_at=None
    )
    other = await reward_service.create_reward(db, actor_id=admin.id, data={"title": "Kitob", "type": RewardType.BOOK})
    headers = admin_headers(admin)

    winners = (await client.get("/api/v1/admin/rewards/test-winners", headers=headers)).json()
    assert [w["title"] for w in winners] == ["Ikkinchi test", "Birinchi test"]
    # The event test: Komil did not attend, so Aziz is first and Bobur second.
    event_places = [(p["place"], p["name"]) for p in winners[1]["places"]]
    assert event_places == [(1, "Karimov Aziz"), (2, "Karimov Bobur")]
    assert all(p["given_reward"] is None for w in winners for p in w["places"])

    url = f"/api/v1/admin/rewards/{reward.id}/assign-test-place"
    given = await client.post(url, json={"test_id": str(first.id), "place": 1}, headers=headers)
    assert given.status_code == 201 and given.json()["note"] == "«Birinchi test» testi — 1-o'rin"
    # The same member also won the other test: a second code of the same reward is fine.
    assert (await client.post(url, json={"test_id": str(second.id), "place": 1}, headers=headers)).status_code == 201
    again = await client.post(url, json={"test_id": str(first.id), "place": 1}, headers=headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "PLACE_ALREADY_REWARDED"
    other_reward = await client.post(
        f"/api/v1/admin/rewards/{other.id}/assign-test-place",
        json={"test_id": str(first.id), "place": 1},
        headers=headers,
    )
    assert other_reward.status_code == 409  # one gift per place, whatever the reward
    missing = await client.post(url, json={"test_id": str(first.id), "place": 3}, headers=headers)
    assert missing.status_code == 404

    winners = (await client.get("/api/v1/admin/rewards/test-winners", headers=headers)).json()
    first_places = {p["place"]: p for p in winners[1]["places"]}
    assert first_places[1]["given_reward"] == "Kitob ilovasi" and first_places[2]["given_reward"] is None

    # Anyone, outside tests: a repeat needs the admin's confirmation (allow_repeat).
    manual = f"/api/v1/admin/rewards/{reward.id}/assign"
    repeat = await client.post(manual, json={"user_id": str(a.id)}, headers=headers)
    assert repeat.status_code == 409 and repeat.json()["error"]["code"] == "ALREADY_ASSIGNED"
    confirmed = await client.post(manual, json={"user_id": str(a.id), "allow_repeat": True}, headers=headers)
    assert confirmed.status_code == 201
