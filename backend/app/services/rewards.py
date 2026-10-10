"""Rewards: admin-defined prizes (books, certificates, partner discounts, subscription codes).

Promo codes are entered by administrators (the system never invents or "generates" working
codes). They are stored encrypted, admins only ever see them masked, and a code is revealed
only to the member it was assigned to. Every assignment and status change is audited.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Reward, RewardCode, User, UserReward
from app.models.enums import NotificationType, RewardCodeStatus, RewardStatus, UserRewardStatus, UserStatus
from app.security.crypto import decrypt_secret, encrypt_secret, keyed_hash
from app.services.audit import record_audit
from app.services.notifications import app_button, celebrate, enqueue_notification, render

CODE_PURPOSE = "reward-code"
_FIELDS = ("title", "description", "type", "value", "expires_at", "status")
ACTIVE_ASSIGNMENT = (UserRewardStatus.ASSIGNED, UserRewardStatus.DELIVERED, UserRewardStatus.REDEEMED)


def mask(code: str) -> str:
    if len(code) <= 4:
        return "•" * len(code)
    return f"{code[:2]}{'•' * min(len(code) - 4, 8)}{code[-2:]}"


def _snapshot(reward: Reward) -> dict[str, Any]:
    return {
        "title": reward.title,
        "type": str(reward.type),
        "value": reward.value,
        "status": str(reward.status),
        "expires_at": reward.expires_at.isoformat() if reward.expires_at else None,
    }


async def get_reward(session: AsyncSession, reward_id: uuid.UUID) -> Reward:
    reward = await session.get(Reward, reward_id)
    if reward is None or reward.deleted_at is not None:
        raise NotFoundError("REWARD_NOT_FOUND", "Sovg'a topilmadi.")
    return reward


async def list_rewards(session: AsyncSession) -> list[tuple[Reward, dict[str, int]]]:
    rewards = list(
        await session.scalars(select(Reward).where(Reward.deleted_at.is_(None)).order_by(Reward.created_at.desc()))
    )
    ids = [reward.id for reward in rewards]
    codes: dict[tuple[uuid.UUID, str], int] = {}
    assigned: dict[uuid.UUID, int] = {}
    if ids:
        for reward_id, status, count in await session.execute(
            select(RewardCode.reward_id, RewardCode.status, func.count())
            .where(RewardCode.reward_id.in_(ids))
            .group_by(RewardCode.reward_id, RewardCode.status)
        ):
            codes[(reward_id, str(status))] = int(count)
        assigned = dict(
            (
                await session.execute(
                    select(UserReward.reward_id, func.count())
                    .where(UserReward.reward_id.in_(ids), UserReward.status.in_(ACTIVE_ASSIGNMENT))
                    .group_by(UserReward.reward_id)
                )
            ).all()
        )
    result = []
    for reward in rewards:
        counts = {status.value.lower(): codes.get((reward.id, status.value), 0) for status in RewardCodeStatus}
        counts["codes_total"] = sum(counts.values())
        counts["recipients"] = int(assigned.get(reward.id, 0))
        result.append((reward, counts))
    return result


async def create_reward(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Reward:
    reward = Reward(**{key: value for key, value in data.items() if key in _FIELDS}, created_by=actor_id)
    session.add(reward)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="REWARD_CREATE",
        entity_type="reward",
        entity_id=reward.id,
        after=_snapshot(reward),
    )
    await session.commit()
    return reward


async def update_reward(
    session: AsyncSession, *, actor_id: uuid.UUID, reward_id: uuid.UUID, changes: dict[str, Any]
) -> Reward:
    reward = await get_reward(session, reward_id)
    before = _snapshot(reward)
    for field, value in changes.items():
        if field in _FIELDS:
            setattr(reward, field, value)
    record_audit(
        session,
        actor_id=actor_id,
        action="REWARD_UPDATE",
        entity_type="reward",
        entity_id=reward.id,
        before=before,
        after=_snapshot(reward),
    )
    await session.commit()
    return reward


async def add_codes(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    reward_id: uuid.UUID,
    codes: list[str],
    expires_at: datetime | None,
) -> tuple[int, int]:
    """Store legitimate codes provided by the admin. Returns (added, skipped duplicates)."""
    reward = await get_reward(session, reward_id)
    cleaned = list(dict.fromkeys(code.strip() for code in codes if code.strip()))
    if not cleaned:
        raise BadRequestError("NO_CODES", "Kamida bitta kod kiriting.")
    if any(len(code) > 128 for code in cleaned):
        raise BadRequestError("CODE_TOO_LONG", "Kod 128 belgidan oshmasligi kerak.")
    added = 0
    for code in cleaned:
        inserted = await session.scalar(
            insert(RewardCode)
            .values(
                reward_id=reward.id,
                code_encrypted=encrypt_secret(CODE_PURPOSE, code),
                code_hash=keyed_hash(CODE_PURPOSE, f"{reward.id}:{code}"),
                expires_at=expires_at,
                created_by=actor_id,
            )
            .on_conflict_do_nothing(index_elements=[RewardCode.reward_id, RewardCode.code_hash])
            .returning(RewardCode.id)
        )
        added += 1 if inserted else 0
    record_audit(
        session,
        actor_id=actor_id,
        action="REWARD_CODES_ADD",
        entity_type="reward",
        entity_id=reward.id,
        after={"added": added, "duplicates": len(cleaned) - added},
    )
    await session.commit()
    return added, len(cleaned) - added


async def list_codes(session: AsyncSession, reward_id: uuid.UUID) -> list[tuple[RewardCode, str, str | None]]:
    """(code, masked value, recipient name)."""
    await get_reward(session, reward_id)
    rows = await session.execute(
        select(RewardCode, User.first_name, User.last_name)
        .outerjoin(UserReward, UserReward.reward_code_id == RewardCode.id)
        .outerjoin(User, User.id == UserReward.user_id)
        .where(RewardCode.reward_id == reward_id)
        .order_by(RewardCode.created_at)
    )
    return [
        (code, mask(decrypt_secret(CODE_PURPOSE, code.code_encrypted)), f"{first} {last}" if first else None)
        for code, first, last in rows
    ]


async def revoke_code(session: AsyncSession, *, actor_id: uuid.UUID, reward_id: uuid.UUID, code_id: uuid.UUID) -> None:
    code = await session.get(RewardCode, code_id)
    if code is None or code.reward_id != reward_id:
        raise NotFoundError("CODE_NOT_FOUND", "Kod topilmadi.")
    if code.status != RewardCodeStatus.AVAILABLE:
        raise ConflictError("CODE_IN_USE", "Faqat hali berilmagan kodni bekor qilish mumkin.")
    code.status = RewardCodeStatus.REVOKED
    record_audit(session, actor_id=actor_id, action="REWARD_CODE_REVOKE", entity_type="reward", entity_id=reward_id)
    await session.commit()


async def _has_codes(session: AsyncSession, reward_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(select(func.count()).select_from(RewardCode).where(RewardCode.reward_id == reward_id))
    )


async def assign(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    reward_id: uuid.UUID,
    user_id: uuid.UUID,
    note: str | None,
    idempotency_key: str | None = None,
    allow_repeat: bool = False,
    message: str | None = None,
) -> UserReward:
    """Give a reward to a member. Rewards with codes hand out the next unused, unexpired code.

    ``allow_repeat``: the member may already hold this reward (a giveaway won again next month).
    ``message``: plain text sent instead of the standard «Sizga sovg'a berildi» notification.
    """
    if idempotency_key:
        existing = await session.scalar(select(UserReward).where(UserReward.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    reward = await get_reward(session, reward_id)
    now = datetime.now(UTC)
    if reward.status != RewardStatus.ACTIVE or (reward.expires_at and reward.expires_at <= now):
        raise ConflictError("REWARD_NOT_ACTIVE", "Bu sovg'a faol emas yoki muddati o'tgan.")
    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None or member.status != UserStatus.ACTIVE:
        raise BadRequestError("USER_NOT_ACTIVE", "Sovg'ani faqat faol a'zoga berish mumkin.")
    # Serialize parallel assignments of the same reward to the same member.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"reward:{reward.id}:{user_id}"))))
    duplicate = await session.scalar(
        select(UserReward.id).where(
            UserReward.reward_id == reward.id, UserReward.user_id == user_id, UserReward.status.in_(ACTIVE_ASSIGNMENT)
        )
    )
    if duplicate is not None and not allow_repeat:
        raise ConflictError("ALREADY_ASSIGNED", "Bu a'zoga bu sovg'a allaqachon berilgan.")

    code: RewardCode | None = None
    if await _has_codes(session, reward.id):
        code = await session.scalar(
            select(RewardCode)
            .where(
                RewardCode.reward_id == reward.id,
                RewardCode.status == RewardCodeStatus.AVAILABLE,
                or_(RewardCode.expires_at.is_(None), RewardCode.expires_at > now),
            )
            .order_by(RewardCode.expires_at.asc().nulls_last(), RewardCode.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if code is None:
            raise ConflictError("NO_CODES_LEFT", "Bu sovg'a uchun bo'sh kod qolmagan. Yangi kodlar qo'shing.")
        code.status = RewardCodeStatus.ASSIGNED

    user_reward = UserReward(
        user_id=user_id,
        reward_id=reward.id,
        reward_code_id=code.id if code else None,
        status=UserRewardStatus.ASSIGNED,
        assigned_by=actor_id,
        assigned_at=now,
        note=note.strip() if note and note.strip() else None,
        idempotency_key=idempotency_key or f"reward:{reward.id}:user:{user_id}:{uuid.uuid4()}",
    )
    session.add(user_reward)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="REWARD_ASSIGN",
        entity_type="reward",
        entity_id=reward.id,
        after={"user_id": str(user_id), "with_code": code is not None},
        reason=user_reward.note,
    )
    if message is not None:
        text = await render(session, NotificationType.SYSTEM, message=message)
    else:
        text = await render(session, NotificationType.REWARD, reward_title=reward.title)
    if text is not None:
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.REWARD,
            text=text,
            dedup_key=f"reward:{user_reward.id}",
            payload=celebrate(app_button("rewards", "🎁 Sovg'alarim")),
            priority=2,
        )
    await session.commit()
    return user_reward


async def recipients(session: AsyncSession, reward_id: uuid.UUID) -> list[tuple[UserReward, User]]:
    await get_reward(session, reward_id)
    rows = await session.execute(
        select(UserReward, User)
        .join(User, User.id == UserReward.user_id)
        .where(UserReward.reward_id == reward_id)
        .order_by(UserReward.assigned_at.desc())
    )
    return [(row, user) for row, user in rows]


_TRANSITIONS = {
    UserRewardStatus.ASSIGNED: (UserRewardStatus.DELIVERED, UserRewardStatus.REDEEMED, UserRewardStatus.REVOKED),
    UserRewardStatus.DELIVERED: (UserRewardStatus.REDEEMED, UserRewardStatus.REVOKED),
    UserRewardStatus.REDEEMED: (UserRewardStatus.REVOKED,),
    UserRewardStatus.REVOKED: (),
}


async def _apply_status(session: AsyncSession, row: UserReward, status: UserRewardStatus) -> None:
    if status not in _TRANSITIONS[UserRewardStatus(row.status)]:
        raise ConflictError("INVALID_REWARD_STATUS", "Bu holatga o'tkazib bo'lmaydi.")
    now = datetime.now(UTC)
    row.status = status
    code = await session.get(RewardCode, row.reward_code_id) if row.reward_code_id else None
    if status == UserRewardStatus.DELIVERED:
        row.delivered_at = row.delivered_at or now
    elif status == UserRewardStatus.REDEEMED:
        row.delivered_at = row.delivered_at or now
        row.redeemed_at = now
        if code is not None:
            code.status = RewardCodeStatus.REDEEMED
    elif status == UserRewardStatus.REVOKED and code is not None:
        # The member may already have seen the code, so it is never handed out again.
        code.status = RewardCodeStatus.REVOKED


async def set_status(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_reward_id: uuid.UUID,
    status: UserRewardStatus,
    note: str | None,
) -> UserReward:
    row = await session.get(UserReward, user_reward_id)
    if row is None:
        raise NotFoundError("USER_REWARD_NOT_FOUND", "Berilgan sovg'a topilmadi.")
    previous = row.status
    await _apply_status(session, row, status)
    record_audit(
        session,
        actor_id=actor_id,
        action="REWARD_STATUS",
        entity_type="user_reward",
        entity_id=row.id,
        before={"status": str(previous)},
        after={"status": str(status)},
        reason=note,
    )
    await session.commit()
    return row


# ---------------------------------------------------------------------------- members


async def member_rewards(session: AsyncSession, user_id: uuid.UUID) -> list[tuple[UserReward, Reward, bool]]:
    """(assignment, reward, has a code)."""
    rows = await session.execute(
        select(UserReward, Reward)
        .join(Reward, Reward.id == UserReward.reward_id)
        .where(UserReward.user_id == user_id, UserReward.status != UserRewardStatus.REVOKED)
        .order_by(UserReward.assigned_at.desc())
    )
    return [(row, reward, row.reward_code_id is not None) for row, reward in rows]


async def reveal_code(
    session: AsyncSession, *, user_id: uuid.UUID, user_reward_id: uuid.UUID
) -> tuple[str, datetime | None]:
    """Only the recipient can see the code. Opening it marks the reward as delivered."""
    row = await session.scalar(
        select(UserReward).where(
            and_(
                UserReward.id == user_reward_id,
                UserReward.user_id == user_id,
                UserReward.status != UserRewardStatus.REVOKED,
            )
        )
    )
    if row is None or row.reward_code_id is None:
        raise NotFoundError("CODE_NOT_FOUND", "Kod topilmadi.")
    code = await session.get(RewardCode, row.reward_code_id)
    assert code is not None
    if row.status == UserRewardStatus.ASSIGNED:
        await _apply_status(session, row, UserRewardStatus.DELIVERED)
        await session.commit()
    return decrypt_secret(CODE_PURPOSE, code.code_encrypted), code.expires_at


async def mark_redeemed(session: AsyncSession, *, user_id: uuid.UUID, user_reward_id: uuid.UUID) -> UserReward:
    row = await session.scalar(select(UserReward).where(UserReward.id == user_reward_id, UserReward.user_id == user_id))
    if row is None:
        raise NotFoundError("USER_REWARD_NOT_FOUND", "Sovg'a topilmadi.")
    if row.status != UserRewardStatus.REDEEMED:
        await _apply_status(session, row, UserRewardStatus.REDEEMED)
        await session.commit()
    return row


# ---------------------------------------------------------------------------- test winners


def test_place_key(test_id: uuid.UUID, place: int) -> str:
    """One reward per place of a test, whatever the reward: prevents giving the same place twice."""
    return f"test-place:{test_id}:{place}"


async def test_winners(session: AsyncSession, *, days: int = 60) -> list[dict[str, Any]]:
    """Places 1-3 of the tests closed in the last ``days`` days, with what each place already got."""
    from datetime import timedelta

    from app.models import Event, Test
    from app.models.enums import TestStatus
    from app.services import quizzes

    tests = list(
        await session.scalars(
            select(Test)
            .where(
                Test.deleted_at.is_(None),
                Test.status == TestStatus.CLOSED,
                Test.ends_at >= datetime.now(UTC) - timedelta(days=days),
            )
            .order_by(Test.ends_at.desc())
        )
    )
    given = {
        ":".join(row.idempotency_key.split(":")[:3]): (row, title)  # without a re-give suffix
        for row, title in (
            await session.execute(
                select(UserReward, Reward.title)
                .join(Reward, Reward.id == UserReward.reward_id)
                .where(UserReward.idempotency_key.like("test-place:%"), UserReward.status.in_(ACTIVE_ASSIGNMENT))
            )
        ).all()
    }
    result = []
    for test in tests:
        places = await quizzes.official_places(session, test)
        if not places:
            continue
        users = {
            u.id: u for u in await session.scalars(select(User).where(User.id.in_([p["user_id"] for p in places])))
        }
        event = await session.get(Event, test.event_id) if test.event_id else None
        rows = []
        for place in places:
            user = users[place["user_id"]]
            done = given.get(test_place_key(test.id, place["place"]))
            rows.append(
                {
                    "place": place["place"],
                    "user_id": user.id,
                    "name": f"{user.last_name} {user.first_name}",
                    "group_name": user.group_name,
                    "score": place["score"],
                    "max_score": test.max_score,
                    "given_reward": done[1] if done else None,
                    "given_at": done[0].assigned_at if done else None,
                }
            )
        result.append(
            {
                "test_id": test.id,
                "title": test.title,
                "event_title": event.title if event else None,
                "closed_at": test.ends_at,
                "places": rows,
            }
        )
    return result


async def assign_test_place(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    reward_id: uuid.UUID,
    test_id: uuid.UUID,
    place: int,
    message: str | None = None,
) -> UserReward:
    """Give the reward to the member who took ``place`` in the test — once per place."""
    from app.models import Test
    from app.services import quizzes

    test = await session.get(Test, test_id)
    if test is None or test.deleted_at is not None:
        raise NotFoundError("TEST_NOT_FOUND", "Test topilmadi.")
    holder = next((row for row in await quizzes.official_places(session, test) if row["place"] == place), None)
    if holder is None:
        raise NotFoundError("PLACE_NOT_FOUND", "Bu o'rinni egallagan a'zo yo'q.")
    key = test_place_key(test.id, place)
    same_place = or_(UserReward.idempotency_key == key, UserReward.idempotency_key.like(f"{key}:%"))
    existing = await session.scalar(
        select(UserReward).where(same_place, UserReward.status.in_(ACTIVE_ASSIGNMENT)).limit(1)
    )
    if existing is not None:
        given = await session.get(Reward, existing.reward_id)
        raise ConflictError(
            "PLACE_ALREADY_REWARDED",
            f"Bu o'ringa allaqachon sovg'a berilgan: «{given.title if given else '—'}».",
        )
    revoked = await session.scalar(select(UserReward.id).where(same_place).limit(1))
    return await assign(
        session,
        actor_id=actor_id,
        reward_id=reward_id,
        user_id=holder["user_id"],
        note=f"«{test.title}» testi — {place}-o'rin",
        # A revoked earlier gift keeps its key; the new one gets a fresh suffix.
        idempotency_key=key if revoked is None else f"{key}:{uuid.uuid4().hex[:8]}",
        allow_repeat=True,
        message=message,
    )


def place_message(first_name: str, test_title: str, place: int, reward_title: str, usage: str | None) -> str:
    text = (
        f"🎁 Tabriklaymiz, {first_name}! «{test_title}» testida {place}-o'rinni egallaganingiz uchun sizga "
        f"«{reward_title}» promokodi sovg'a qilindi."
    )
    if usage and usage.strip():
        text += f"\n\n📍 Qayerda ishlatiladi: {usage.strip()}"
    return text + "\n\nKodni ilovadagi «🎁 Sovg'alarim» bo'limida ko'rasiz. Omad! 🍀"


async def distribution_plan(
    session: AsyncSession,
    *,
    test_ids: list[uuid.UUID] | None = None,
    days: int = 60,
    reward_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Who gets a code, in order: every 1st place first (older tests first), then 2nd places, then 3rd.
    Places already rewarded are skipped, and a member gets one code of a reward even with several places.
    For a test of an event only members who attended hold places."""
    winners = await test_winners(session, days=days)
    if test_ids:
        wanted = set(test_ids)
        winners = [test for test in winners if test["test_id"] in wanted]
    slots = [
        {
            "test_id": test["test_id"],
            "test_title": test["title"],
            "closed_at": test["closed_at"],
            "place": place["place"],
            "user_id": place["user_id"],
            "name": place["name"],
        }
        for test in winners
        for place in test["places"]
        if place["given_reward"] is None
    ]
    slots.sort(key=lambda slot: (slot["place"], slot["closed_at"]))
    plan: list[dict[str, Any]] = []
    seen: set[uuid.UUID] = set()
    if reward_id is not None:  # members who already hold this reward get no second code
        seen = set(
            await session.scalars(
                select(UserReward.user_id).where(
                    UserReward.reward_id == reward_id, UserReward.status.in_(ACTIVE_ASSIGNMENT)
                )
            )
        )
    for slot in slots:
        if slot["user_id"] in seen:
            continue
        seen.add(slot["user_id"])
        plan.append(slot)
    return plan


async def distribute_test_places(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    reward_id: uuid.UUID,
    codes: list[str],
    usage: str | None,
    test_ids: list[uuid.UUID] | None = None,
    days: int = 60,
) -> dict[str, Any]:
    """Add the codes (one per line) and hand them out by :func:`distribution_plan` until they run out."""
    reward = await get_reward(session, reward_id)
    reward_title = reward.title  # a rollback below would expire the object
    added = duplicates = 0
    if any(code.strip() for code in codes):
        added, duplicates = await add_codes(
            session, actor_id=actor_id, reward_id=reward_id, codes=codes, expires_at=None
        )
    plan = await distribution_plan(session, test_ids=test_ids, days=days, reward_id=reward_id)
    given: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    for slot in plan:
        member = await session.get(User, slot["user_id"])
        try:
            await assign_test_place(
                session,
                actor_id=actor_id,
                reward_id=reward_id,
                test_id=slot["test_id"],
                place=slot["place"],
                message=place_message(
                    member.first_name if member else "", slot["test_title"], slot["place"], reward_title, usage
                ),
            )
        except ConflictError as error:
            await session.rollback()
            if error.code == "NO_CODES_LEFT":
                waiting = [slot, *plan[plan.index(slot) + 1 :]]
                break
            continue
        except BadRequestError:  # the member left the club meanwhile
            await session.rollback()
            continue
        given.append(slot)
    return {"codes_added": added, "duplicates": duplicates, "given": given, "waiting": waiting}
