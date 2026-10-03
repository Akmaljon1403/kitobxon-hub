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
from app.services.notifications import app_button, enqueue_notification, render

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
            payload=app_button("rewards", "🎁 Sovg'alarim"),
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
