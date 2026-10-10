"""Admin Panel: rewards, their promo codes (always masked) and recipients."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import Reward, User
from app.schemas.reward import (
    AssignIn,
    CodesAddedOut,
    CodesIn,
    DistributeIn,
    DistributionOut,
    DistributionSlotOut,
    RecipientOut,
    RewardCodeOut,
    RewardIn,
    RewardOut,
    RewardStatusIn,
    RewardUpdateIn,
    TestPlaceIn,
    TestWinnersOut,
)
from app.security.permissions import Perm
from app.services import rewards as reward_service

router = APIRouter(prefix="/admin", tags=["admin: rewards"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.REWARD_MANAGE))]


def _out(reward: Reward, counts: dict[str, int]) -> RewardOut:
    return RewardOut(
        id=reward.id,
        title=reward.title,
        description=reward.description,
        type=reward.type,
        value=reward.value,
        expires_at=reward.expires_at,
        status=reward.status,
        codes_total=counts.get("codes_total", 0),
        codes_available=counts.get("available", 0),
        recipients=counts.get("recipients", 0),
        created_at=reward.created_at,
    )


async def _one(db, reward_id: uuid.UUID) -> RewardOut:
    for reward, counts in await reward_service.list_rewards(db):
        if reward.id == reward_id:
            return _out(reward, counts)
    raise AssertionError("reward disappeared")


@router.get("/rewards", response_model=list[RewardOut], summary="Rewards with code and recipient counts")
async def list_rewards(_: Manager, db: DbSession) -> list[RewardOut]:
    return [_out(reward, counts) for reward, counts in await reward_service.list_rewards(db)]


@router.post("/rewards", response_model=RewardOut, status_code=status.HTTP_201_CREATED, summary="Create a reward")
async def create_reward(payload: RewardIn, current: Manager, db: DbSession) -> RewardOut:
    reward = await reward_service.create_reward(db, actor_id=current.user.id, data=payload.model_dump())
    return await _one(db, reward.id)


@router.patch("/rewards/{reward_id}", response_model=RewardOut, summary="Edit a reward")
async def update_reward(reward_id: uuid.UUID, payload: RewardUpdateIn, current: Manager, db: DbSession) -> RewardOut:
    await reward_service.update_reward(
        db, actor_id=current.user.id, reward_id=reward_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _one(db, reward_id)


@router.post("/rewards/{reward_id}/codes", response_model=CodesAddedOut, summary="Add promo codes (stored encrypted)")
async def add_codes(reward_id: uuid.UUID, payload: CodesIn, current: Manager, db: DbSession) -> CodesAddedOut:
    added, duplicates = await reward_service.add_codes(
        db, actor_id=current.user.id, reward_id=reward_id, codes=payload.codes, expires_at=payload.expires_at
    )
    return CodesAddedOut(added=added, duplicates=duplicates)


@router.get("/rewards/{reward_id}/codes", response_model=list[RewardCodeOut], summary="Codes (masked)")
async def list_codes(reward_id: uuid.UUID, _: Manager, db: DbSession) -> list[RewardCodeOut]:
    return [
        RewardCodeOut(
            id=code.id,
            masked=masked,
            status=code.status,
            expires_at=code.expires_at,
            assigned_to=assigned_to,
            created_at=code.created_at,
        )
        for code, masked, assigned_to in await reward_service.list_codes(db, reward_id)
    ]


@router.post(
    "/rewards/{reward_id}/codes/{code_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw an unused code",
)
async def revoke_code(reward_id: uuid.UUID, code_id: uuid.UUID, current: Manager, db: DbSession) -> Response:
    await reward_service.revoke_code(db, actor_id=current.user.id, reward_id=reward_id, code_id=code_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/rewards/{reward_id}/assign",
    response_model=RecipientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Give the reward to a member",
)
async def assign(reward_id: uuid.UUID, payload: AssignIn, current: Manager, db: DbSession) -> RecipientOut:
    row = await reward_service.assign(
        db,
        actor_id=current.user.id,
        reward_id=reward_id,
        user_id=payload.user_id,
        note=payload.note,
        idempotency_key=payload.idempotency_key,
        allow_repeat=payload.allow_repeat,
    )
    return await _recipient_of(db, reward_id, row.id)


async def _recipient_of(db, reward_id: uuid.UUID, user_reward_id: uuid.UUID) -> RecipientOut:
    for recipient, user in await reward_service.recipients(db, reward_id):
        if recipient.id == user_reward_id:
            return _recipient(recipient, user)
    raise AssertionError("assignment disappeared")


@router.get(
    "/rewards/test-winners",
    response_model=list[TestWinnersOut],
    summary="Places 1-3 of recently closed tests, with the rewards they already got",
)
async def test_winners(_: Manager, db: DbSession, days: int = 60) -> list[TestWinnersOut]:
    return [TestWinnersOut(**item) for item in await reward_service.test_winners(db, days=min(max(days, 1), 365))]


@router.get(
    "/rewards/distribution-plan",
    response_model=DistributionOut,
    summary="Who would get codes, in order (1st places first, then 2nd, then 3rd; one per member)",
)
async def distribution_plan(
    _: Manager, db: DbSession, days: int = 60, reward_id: uuid.UUID | None = None
) -> DistributionOut:
    plan = await reward_service.distribution_plan(db, days=min(max(days, 1), 365), reward_id=reward_id)
    return DistributionOut(given=[], waiting=[DistributionSlotOut(**slot) for slot in plan])


@router.post(
    "/rewards/{reward_id}/distribute-test-places",
    response_model=DistributionOut,
    summary="Add codes (one per line) and give them to test places: 1st places first, then 2nd, then 3rd",
)
async def distribute_test_places(
    reward_id: uuid.UUID, payload: DistributeIn, current: Manager, db: DbSession
) -> DistributionOut:
    result = await reward_service.distribute_test_places(
        db,
        actor_id=current.user.id,
        reward_id=reward_id,
        codes=payload.codes.splitlines(),
        usage=payload.usage,
        test_ids=payload.test_ids,
        days=payload.days,
    )
    return DistributionOut(
        codes_added=result["codes_added"],
        duplicates=result["duplicates"],
        given=[DistributionSlotOut(**slot) for slot in result["given"]],
        waiting=[DistributionSlotOut(**slot) for slot in result["waiting"]],
    )


@router.post(
    "/rewards/{reward_id}/assign-test-place",
    response_model=RecipientOut,
    status_code=status.HTTP_201_CREATED,
    summary="Give the reward to a test place (once per place)",
)
async def assign_test_place(
    reward_id: uuid.UUID, payload: TestPlaceIn, current: Manager, db: DbSession
) -> RecipientOut:
    row = await reward_service.assign_test_place(
        db, actor_id=current.user.id, reward_id=reward_id, test_id=payload.test_id, place=payload.place
    )
    return await _recipient_of(db, reward_id, row.id)


def _recipient(row, user) -> RecipientOut:
    return RecipientOut(
        id=row.id,
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        group_name=user.group_name,
        status=row.status,
        has_code=row.reward_code_id is not None,
        note=row.note,
        assigned_at=row.assigned_at,
        delivered_at=row.delivered_at,
        redeemed_at=row.redeemed_at,
    )


@router.get("/rewards/{reward_id}/recipients", response_model=list[RecipientOut], summary="Who received it")
async def recipients(reward_id: uuid.UUID, _: Manager, db: DbSession) -> list[RecipientOut]:
    return [_recipient(row, user) for row, user in await reward_service.recipients(db, reward_id)]


@router.post(
    "/user-rewards/{user_reward_id}/status", response_model=RecipientOut, summary="Delivered / redeemed / revoked"
)
async def set_status(
    user_reward_id: uuid.UUID, payload: RewardStatusIn, current: Manager, db: DbSession
) -> RecipientOut:
    row = await reward_service.set_status(
        db, actor_id=current.user.id, user_reward_id=user_reward_id, status=payload.status, note=payload.note
    )
    user = await db.get(User, row.user_id)
    return _recipient(row, user)
