"""Round F1–F2: «Sizning foydangiz» (what the invited friends did) and referral contests with
per-place prizes and the club's choice of what members see."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    BookRead,
    Notification,
    PremiumSubscription,
    ReferralContest,
    Reward,
    ScoreTransaction,
    UserReward,
)
from app.models.enums import (
    AttendanceMethod,
    ContestStatus,
    NotificationType,
    ReadingStatus,
    RewardStatus,
    RewardType,
    ScoreCategory,
)
from app.security.permissions import Perm
from app.services import contests
from app.services.scoring import award_points
from app.services.settings import update_setting
from tests.factories import create_book, create_event, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(1_900_000)
NOW = datetime.now(UTC)


async def _came(db: AsyncSession, user: Any, when: datetime | None = None) -> None:
    event = await create_event(db, starts_at=(when or NOW) - timedelta(minutes=10))
    db.add(
        AttendanceRecord(event_id=event.id, user_id=user.id, method=AttendanceMethod.CODE, checked_in_at=when or NOW)
    )
    await db.flush()


async def _manager(db: AsyncSession) -> Any:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.REWARD_MANAGE)
    return admin


# ---------------------------------------------------------------------------- «Sizning foydangiz»


async def test_my_impact_friends_and_the_inviters_table(client: httpx.AsyncClient, db: AsyncSession) -> None:
    inviter = await create_user(db, first_name="Aziza", last_name="Karimova")
    reader = await create_user(db, first_name="Bobur", last_name="Aliyev", referred_by=inviter.id)
    newcomer = await create_user(db, first_name="Dilnoza", last_name="Rasulova", referred_by=inviter.id)
    other = await create_user(db)
    await create_user(db, referred_by=other.id)  # registered, never came: not counted by default
    await _came(db, reader)
    await award_points(db, user_id=reader.id, amount=30, category=ScoreCategory.TEST, idempotency_key=f"t:{reader.id}")
    book = await create_book(db)
    db.add(BookRead(book_id=book.id, user_id=newcomer.id, status=ReadingStatus.COMPLETED, completed_at=NOW))
    await award_points(
        db,
        user_id=inviter.id,
        amount=20,
        category=ScoreCategory.CAMPAIGN,
        idempotency_key=f"referral:{reader.id}",
        source_type="REFERRAL",
        source_id=reader.id,
    )
    await db.commit()

    body = (await client.get("/api/v1/me/referrals", headers=member_headers(inviter))).json()
    impact = body["impact"]
    assert (impact["invited"], impact["came_to_events"], impact["active"]) == (2, 1, 2)
    assert (impact["friends_points"], impact["friends_books"], impact["friends_visits"]) == (30, 1, 1)
    assert impact["earned_points"] == 20
    friends = {friend["name"]: friend for friend in body["friends"]}
    assert friends["Bobur A."]["points"] == 30 and friends["Bobur A."]["came_to_event"]
    assert friends["Dilnoza R."]["books"] == 1 and not friends["Dilnoza R."]["came_to_event"]
    board = body["leaderboard"]
    assert board["my_place"] == 1 and board["items"][0]["me"] and board["items"][0]["friends"] == 1
    assert len(board["items"]) == 1  # the other inviter's friend never came

    await update_setting(db, key="referral.friend_details", value="NAMES", actor_id=None)
    await update_setting(db, key="referral.leaderboard_rule", value="REGISTERED", actor_id=None)
    body = (await client.get("/api/v1/me/referrals", headers=member_headers(inviter))).json()
    assert all(friend["points"] is None for friend in body["friends"])
    assert len(body["leaderboard"]["items"]) == 2 and body["leaderboard"]["items"][0]["friends"] == 2

    await update_setting(db, key="referral.friend_details", value="COUNT", actor_id=None)
    await update_setting(db, key="referral.leaderboard_size", value=0, actor_id=None)
    body = (await client.get("/api/v1/me/referrals", headers=member_headers(inviter))).json()
    assert body["friends"] == [] and body["leaderboard"] is None and body["impact"]["invited"] == 2


# ---------------------------------------------------------------------------- contests


async def _setup(db: AsyncSession) -> dict[str, Any]:
    start = NOW - timedelta(days=1)
    leader = await create_user(db, first_name="Aziza", last_name="Karimova")
    second = await create_user(db, first_name="Bobur", last_name="Aliyev")
    late = await create_user(db, first_name="Jasur", last_name="Toshev")
    staff = await create_user(db)
    await db.commit()
    await grant_role(db, staff, "ADMIN")
    for _ in range(2):
        friend = await create_user(db, referred_by=leader.id, registered_at=NOW - timedelta(hours=5))
        await _came(db, friend)
    friend = await create_user(db, referred_by=second.id, registered_at=NOW - timedelta(hours=3))
    await _came(db, friend)
    await create_user(db, referred_by=second.id, registered_at=NOW - timedelta(hours=2))  # never came
    before = await create_user(db, referred_by=late.id, registered_at=start - timedelta(days=3))
    await _came(db, before)  # joined before the contest: does not count
    staff_friend = await create_user(db, referred_by=staff.id, registered_at=NOW - timedelta(hours=1))
    await _came(db, staff_friend)
    reward = Reward(title="Kitob do'konidan 20% chegirma", type=RewardType.OTHER, status=RewardStatus.ACTIVE)
    db.add(reward)
    await db.commit()
    return {"leader": leader, "second": second, "late": late, "staff": staff, "reward": reward, "start": start}


def _payload(setup: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "title": "Kim ko'p do'st olib keladi?",
        "description": "Oktabr tanlovi",
        "starts_at": setup["start"].isoformat(),
        "ends_at": (NOW + timedelta(days=2)).isoformat(),
        "rule": "ATTENDED",
        "winners_count": 2,
        "prizes": [
            {"place": 1, "points": 100, "premium_days": 7, "reward_id": str(setup["reward"].id)},
            {"place": 2, "text": "«O'tkan kunlar» kitobi"},
        ],
        "participation_points": 5,
        "name_format": "HIDDEN",
        **extra,
    }


async def test_a_contest_from_draft_to_prizes(client: httpx.AsyncClient, db: AsyncSession) -> None:
    setup = await _setup(db)
    admin = await _manager(db)
    headers = admin_headers(admin)
    created = await client.post("/api/v1/admin/referral-contests", json=_payload(setup), headers=headers)
    assert created.status_code == 201, created.text
    contest_id = created.json()["id"]
    assert created.json()["state"] == "draft"

    second = setup["second"]
    assert (await client.get("/api/v1/me/referral-contests", headers=member_headers(second))).json() == []

    published = await client.post(f"/api/v1/admin/referral-contests/{contest_id}/publish", headers=headers)
    assert published.status_code == 200 and published.json()["state"] == "running"
    told = set(
        await db.scalars(
            select(Notification.user_id).where(Notification.dedup_key.like(f"contest:{contest_id}:start:%"))
        )
    )
    assert second.id in told and setup["staff"].id not in told  # administrators never take part

    view = (await client.get("/api/v1/me/referral-contests", headers=member_headers(second))).json()[0]
    assert view["state"] == "running" and view["eligible"]
    assert [(row["place"], row["name"], row["friends"]) for row in view["leaderboard"]] == [
        (1, "Ishtirokchi", 2),
        (2, "Siz", 1),
    ]
    assert (view["my_place"], view["my_friends"]) == (2, 1)
    assert view["prizes"][0]["text"].startswith("+100 ball + 7 kunlik 💎 Premium + 🎁 Kitob do'konidan")

    # Rules are locked once it runs; what members see is not.
    locked = await client.patch(
        f"/api/v1/admin/referral-contests/{contest_id}", json={"winners_count": 5}, headers=headers
    )
    assert locked.status_code == 409
    changed = await client.patch(
        f"/api/v1/admin/referral-contests/{contest_id}", json={"show_counts": False}, headers=headers
    )
    assert changed.status_code == 200
    view = (await client.get("/api/v1/me/referral-contests", headers=member_headers(second))).json()[0]
    assert view["leaderboard"][0]["friends"] is None and not view["show_counts"]
    await client.patch(f"/api/v1/admin/referral-contests/{contest_id}", json={"freeze_hours": 72}, headers=headers)
    view = (await client.get("/api/v1/me/referral-contests", headers=member_headers(second))).json()[0]
    assert view["leaderboard_hidden"] and view["leaderboard"] == [] and view["my_place"] is None
    assert view["my_friends"] == 1  # one's own number is always shown
    await client.patch(f"/api/v1/admin/referral-contests/{contest_id}", json={"freeze_hours": 0}, headers=headers)

    # The administrator checks the friends and can take a participant out.
    friends = (
        await client.get(
            f"/api/v1/admin/referral-contests/{contest_id}/participants/{second.id}/friends", headers=headers
        )
    ).json()
    assert sorted(friend["counts"] for friend in friends) == [False, True]
    leader = setup["leader"]
    out = await client.post(
        f"/api/v1/admin/referral-contests/{contest_id}/participants/{leader.id}/exclude",
        json={"reason": "Soxta akkauntlar"},
        headers=headers,
    )
    assert out.status_code == 200
    table = (await client.get(f"/api/v1/admin/referral-contests/{contest_id}/standings", headers=headers)).json()
    assert [row["user_id"] for row in table] == [str(second.id)]
    await client.post(f"/api/v1/admin/referral-contests/{contest_id}/participants/{leader.id}/include", headers=headers)
    table = (await client.get(f"/api/v1/admin/referral-contests/{contest_id}/standings", headers=headers)).json()
    assert [(row["name"], row["friends"], row["winner"]) for row in table] == [
        ("Karimova Aziza", 2, True),
        ("Aliyev Bobur", 1, True),
    ]

    finished = await client.post(f"/api/v1/admin/referral-contests/{contest_id}/finish", headers=headers)
    assert finished.status_code == 200, finished.text
    results = finished.json()["results"]
    assert [(item["place"], item["user_id"], item["winner"]) for item in results] == [
        (1, str(leader.id), True),
        (2, str(second.id), True),
    ]
    assert results[0]["given"] == {"points": 100, "premium_days": 7, "reward_id": str(setup["reward"].id)}
    assert not results[1]["handed_over"]
    points = await db.scalar(
        select(func.sum(ScoreTransaction.amount)).where(
            ScoreTransaction.user_id == leader.id, ScoreTransaction.source_type == "REFERRAL_CONTEST"
        )
    )
    assert points == 105  # place prize and the prize for taking part
    assert await db.scalar(select(func.count()).where(PremiumSubscription.user_id == leader.id)) == 1
    assert await db.scalar(select(func.count()).where(UserReward.user_id == leader.id)) == 1
    wins = list(
        await db.scalars(select(Notification.user_id).where(Notification.dedup_key.like(f"contest:{contest_id}:win:%")))
    )
    assert set(wins) == {leader.id, second.id}
    announced = await db.scalar(
        select(Notification.text).where(Notification.dedup_key == f"contest:{contest_id}:results:{second.id}")
    )
    assert announced is not None and "Aziza K." in announced and "2 ta do'st" in announced

    handed = await client.post(
        f"/api/v1/admin/referral-contests/{contest_id}/winners/{second.id}/handed-over", headers=headers
    )
    assert handed.json()["results"][1]["handed_over"]
    again = await client.post(f"/api/v1/admin/referral-contests/{contest_id}/finish", headers=headers)
    assert again.status_code == 409

    view = (await client.get("/api/v1/me/referral-contests", headers=member_headers(second))).json()[0]
    assert view["state"] == "finished" and view["my_place"] == 2
    assert [row["name"] for row in view["leaderboard"]] == ["Aziza K.", "Siz"]

    top = (await client.get("/api/v1/admin/referral-contests/top-inviters", headers=headers)).json()
    assert top[0]["name"] == "Karimova Aziza" and top[0]["attended"] == 2


async def test_the_job_announces_reminds_and_finishes(db: AsyncSession) -> None:
    setup = await _setup(db)
    contest = ReferralContest(
        title="Hafta tanlovi",
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(days=3),
        winners_count=1,
        prizes=[{"place": 1, "points": 50}],
        status=ContestStatus.PUBLISHED,
        remind_hours=24,
    )
    db.add(contest)
    await db.commit()
    assert await contests.run_due(db, NOW) == 0  # not started yet
    contest.starts_at = NOW - timedelta(days=1)
    await db.commit()
    assert await contests.run_due(db, NOW) == 1
    assert contest.announced_at is not None
    assert await contests.run_due(db, NOW + timedelta(days=2, hours=1)) == 1  # the day before the end
    reminder = await db.scalar(
        select(Notification.text).where(Notification.dedup_key == f"contest:{contest.id}:remind:{setup['second'].id}")
    )
    assert reminder is not None and "2-o'rindasiz" in reminder
    assert await contests.run_due(db, NOW + timedelta(days=4)) == 1
    await db.refresh(contest)
    assert contest.status == ContestStatus.FINISHED and contest.results[0]["user_id"] == str(setup["leader"].id)
    assert await contests.run_due(db, NOW + timedelta(days=5)) == 0


async def test_contest_checks_and_cancelling(client: httpx.AsyncClient, db: AsyncSession) -> None:
    setup = await _setup(db)
    admin = await _manager(db)
    headers = admin_headers(admin)
    wrong_place = _payload(setup, prizes=[{"place": 3, "points": 10}])
    assert (await client.post("/api/v1/admin/referral-contests", json=wrong_place, headers=headers)).status_code == 400
    backwards = _payload(setup, ends_at=(setup["start"] - timedelta(days=1)).isoformat())
    assert (await client.post("/api/v1/admin/referral-contests", json=backwards, headers=headers)).status_code == 422
    no_points = _payload(setup, rule="POINTS", min_friend_points=0)
    assert (await client.post("/api/v1/admin/referral-contests", json=no_points, headers=headers)).status_code == 400
    member = await create_user(db)
    await db.commit()
    assert (
        await client.post("/api/v1/admin/referral-contests", json=_payload(setup), headers=admin_headers(member))
    ).status_code == 403

    by_points = await client.post(
        "/api/v1/admin/referral-contests",
        json=_payload(setup, rule="POINTS", min_friend_points=10, min_friends=1),
        headers=headers,
    )
    contest_id = by_points.json()["id"]
    await client.post(f"/api/v1/admin/referral-contests/{contest_id}/publish", headers=headers)
    table = (await client.get(f"/api/v1/admin/referral-contests/{contest_id}/standings", headers=headers)).json()
    assert table == []  # nobody's friends earned 10 points yet
    cancelled = await client.post(
        f"/api/v1/admin/referral-contests/{contest_id}/cancel", json={"reason": "Sana o'zgardi"}, headers=headers
    )
    assert cancelled.json()["state"] == "cancelled"
    note = await db.scalar(
        select(Notification).where(Notification.dedup_key == f"contest:{contest_id}:cancelled:{setup['second'].id}")
    )
    assert note is not None and note.type == NotificationType.ANNOUNCEMENT and "Sana o'zgardi" in note.text
    assert (
        await client.patch(f"/api/v1/admin/referral-contests/{contest_id}", json={"title": "Yangi"}, headers=headers)
    ).status_code == 409


async def test_inviting_friends_unlocks_achievements(db: AsyncSession) -> None:
    from app.models import Achievement, UserAchievement
    from app.services import referrals

    inviter = await create_user(db)
    friend = await create_user(db, referred_by=inviter.id)
    await db.commit()
    await _came(db, friend)
    await referrals.on_first_attendance(db, friend.id)
    await db.commit()
    codes = set(
        await db.scalars(
            select(Achievement.code)
            .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
            .where(UserAchievement.user_id == inviter.id)
        )
    )
    assert "FIRST_FRIEND" in codes and "FIVE_FRIENDS" not in codes


async def test_the_bot_shows_my_impact_and_the_running_contest(db: AsyncSession) -> None:
    from tests.bot_helpers import BotHarness

    setup = await _setup(db)
    contest = ReferralContest(
        title="Oktabr tanlovi",
        starts_at=NOW - timedelta(days=1),
        ends_at=NOW + timedelta(days=2),
        winners_count=1,
        status=ContestStatus.PUBLISHED,
    )
    db.add(contest)
    await db.commit()
    harness = BotHarness(setup["leader"].telegram_id)
    await harness.send("/taklif")
    text = harness.last_text()
    assert "Sizning foydangiz" in text and "Oktabr tanlovi" in text and "<b>2</b> ta do'st, 1-o'rin" in text
