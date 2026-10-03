"""Members' rewards. A promo code is revealed only to the member it was given to."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession, feature_required
from app.schemas.giveaway import MemberGiveawaysOut
from app.schemas.reward import MemberRewardOut, RevealedCodeOut
from app.services import giveaways as giveaway_service
from app.services import rewards as reward_service

router = APIRouter(tags=["rewards"], dependencies=[feature_required("rewards")])


def _out(row, reward, has_code: bool) -> MemberRewardOut:
    return MemberRewardOut(
        id=row.id,
        title=reward.title,
        description=reward.description,
        type=reward.type,
        value=reward.value,
        expires_at=reward.expires_at,
        status=row.status,
        has_code=has_code,
        assigned_at=row.assigned_at,
        redeemed_at=row.redeemed_at,
    )


@router.get("/me/rewards", response_model=list[MemberRewardOut], summary="My rewards")
async def my_rewards(current: CurrentUserDep, db: DbSession) -> list[MemberRewardOut]:
    return [_out(*item) for item in await reward_service.member_rewards(db, current.user.id)]


@router.post("/me/rewards/{user_reward_id}/code", response_model=RevealedCodeOut, summary="Show my promo code")
async def reveal_code(user_reward_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> RevealedCodeOut:
    code, expires_at = await reward_service.reveal_code(db, user_id=current.user.id, user_reward_id=user_reward_id)
    return RevealedCodeOut(code=code, expires_at=expires_at)


@router.post("/me/rewards/{user_reward_id}/redeemed", response_model=MemberRewardOut, summary="I have used it")
async def mark_redeemed(user_reward_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> MemberRewardOut:
    row = await reward_service.mark_redeemed(db, user_id=current.user.id, user_reward_id=user_reward_id)
    reward = await reward_service.get_reward(db, row.reward_id)
    return _out(row, reward, row.reward_code_id is not None)


@router.get("/me/giveaways", response_model=MemberGiveawaysOut, summary="Upcoming giveaways and recent winners")
async def giveaways(_: CurrentUserDep, db: DbSession) -> MemberGiveawaysOut:
    return MemberGiveawaysOut(**await giveaway_service.for_members(db))
