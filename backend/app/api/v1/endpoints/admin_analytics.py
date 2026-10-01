"""Admin Panel: club analytics (aggregates) and the inactive-members list."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.security.permissions import Perm
from app.services import analytics

router = APIRouter(prefix="/admin/analytics", tags=["admin: analytics"])
Viewer = Annotated[CurrentUser, Depends(require_permissions(Perm.ANALYTICS_VIEW))]
MemberViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.ANALYTICS_VIEW, Perm.USER_VIEW))]


@router.get("", summary="Monthly activity, faculties, groups, tests, reading campaigns")
async def overview(_: Viewer, db: DbSession, months: Annotated[int, Query(ge=3, le=24)] = 6) -> dict[str, Any]:
    return await analytics.overview(db, months=months)


@router.get("/inactive", summary="Members without activity for N days (names: USER_VIEW)")
async def inactive(
    _: MemberViewer, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30
) -> list[dict[str, Any]]:
    return await analytics.inactive_members(db, days=days)
