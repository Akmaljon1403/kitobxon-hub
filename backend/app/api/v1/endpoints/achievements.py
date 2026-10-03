"""Members' achievements with progress."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession, feature_required
from app.schemas.achievement import AchievementOut
from app.services import achievements as achievement_service

router = APIRouter(tags=["achievements"], dependencies=[feature_required("achievements")])


@router.get("/me/achievements", response_model=list[AchievementOut], summary="My achievements and progress")
async def my_achievements(current: CurrentUserDep, db: DbSession) -> list[AchievementOut]:
    rows = await achievement_service.member_achievements(db, current.user.id)
    return [AchievementOut(**row) for row in rows]
