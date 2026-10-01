"""Admin Panel: achievement definitions, holders, manual grant and revoke."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentAdminDep, CurrentUser, DbSession, require_permissions
from app.models import Achievement
from app.schemas.achievement import (
    AchievementAdminOut,
    AchievementCreateIn,
    AchievementHolderOut,
    AchievementUpdateIn,
    GrantIn,
)
from app.schemas.common import ReasonIn
from app.security.permissions import Perm
from app.services import achievements as achievement_service

router = APIRouter(prefix="/admin", tags=["admin: achievements"])
SettingsManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))]
ScoreManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SCORE_VIEW, Perm.SCORE_MANAGE))]


def _out(achievement: Achievement, holders: int) -> AchievementAdminOut:
    return AchievementAdminOut(
        id=achievement.id,
        code=achievement.code,
        title=achievement.title,
        description=achievement.description,
        icon=achievement.icon,
        criteria=achievement.criteria,
        threshold=achievement.threshold,
        points=achievement.points,
        is_active=achievement.is_active,
        sort_order=achievement.sort_order,
        holders=holders,
    )


@router.get("/achievements", response_model=list[AchievementAdminOut], summary="Achievement definitions")
async def list_achievements(_: CurrentAdminDep, db: DbSession) -> list[AchievementAdminOut]:
    return [_out(achievement, holders) for achievement, holders in await achievement_service.list_admin(db)]


@router.post(
    "/achievements",
    response_model=AchievementAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an achievement",
)
async def create_achievement(
    payload: AchievementCreateIn, current: SettingsManager, db: DbSession
) -> AchievementAdminOut:
    achievement = await achievement_service.create(db, actor_id=current.user.id, data=payload.model_dump())
    return _out(achievement, 0)


@router.patch("/achievements/{achievement_id}", response_model=AchievementAdminOut, summary="Edit an achievement")
async def update_achievement(
    achievement_id: uuid.UUID, payload: AchievementUpdateIn, current: SettingsManager, db: DbSession
) -> AchievementAdminOut:
    achievement = await achievement_service.update(
        db, actor_id=current.user.id, achievement_id=achievement_id, changes=payload.model_dump(exclude_unset=True)
    )
    holders = len(await achievement_service.holders(db, achievement.id))
    return _out(achievement, holders)


@router.get(
    "/achievements/{achievement_id}/holders",
    response_model=list[AchievementHolderOut],
    summary="Members who unlocked it",
)
async def achievement_holders(
    achievement_id: uuid.UUID, _: CurrentAdminDep, db: DbSession
) -> list[AchievementHolderOut]:
    return [
        AchievementHolderOut(
            id=row.id,
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            group_name=user.group_name,
            unlocked_at=row.unlocked_at,
            granted=bool(row.context and row.context.get("granted_by")),
        )
        for row, user in await achievement_service.holders(db, achievement_id)
    ]


@router.post(
    "/achievements/{achievement_id}/grant",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Give an achievement to a member (reason required)",
)
async def grant(achievement_id: uuid.UUID, payload: GrantIn, current: ScoreManager, db: DbSession) -> Response:
    await achievement_service.grant(
        db, actor_id=current.user.id, achievement_id=achievement_id, user_id=payload.user_id, reason=payload.reason
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/user-achievements/{user_achievement_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Take an achievement back (its bonus points are reversed)",
)
async def revoke(user_achievement_id: uuid.UUID, payload: ReasonIn, current: ScoreManager, db: DbSession) -> Response:
    await achievement_service.revoke(
        db, actor_id=current.user.id, user_achievement_id=user_achievement_id, reason=payload.reason
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
