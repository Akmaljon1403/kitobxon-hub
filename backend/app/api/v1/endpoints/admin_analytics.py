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


@router.get("", summary="Monthly activity, faculties, groups, tests, books")
async def overview(_: Viewer, db: DbSession, months: Annotated[int, Query(ge=3, le=24)] = 6) -> dict[str, Any]:
    return await analytics.overview(db, months=months)


@router.get("/inactive", summary="Members without activity for N days (names: USER_VIEW)")
async def inactive(
    _: MemberViewer, db: DbSession, days: Annotated[int, Query(ge=7, le=365)] = 30
) -> list[dict[str, Any]]:
    return await analytics.inactive_members(db, days=days)


@router.get("/engagement", summary="Active, new, returning and stopped members by month; reading tools in use")
async def engagement(_: Viewer, db: DbSession, months: Annotated[int, Query(ge=3, le=12)] = 6) -> dict[str, Any]:
    return await analytics.engagement(db, months=months)


# ---------------------------------------------------------------------------- «🛡 Ishonch markazi»

Auditor = Annotated[CurrentUser, Depends(require_permissions(Perm.AUDIT_LOG_VIEW))]
trust_router = APIRouter(prefix="/admin/trust", tags=["admin: trust"])


@trust_router.get("", summary="What may need a second look: fast perfect tests, many manual changes, odd numbers")
async def trust_overview(_: Auditor, db: DbSession, days: Annotated[int, Query(ge=7, le=180)] = 30) -> dict[str, Any]:
    from app.services import trust

    return await trust.overview(db, days=days)


@trust_router.get("/certificate", summary="Check a certificate by the code under its QR code")
async def certificate_check(
    _: Auditor, db: DbSession, code: Annotated[str, Query(min_length=4, max_length=32)]
) -> dict[str, Any]:
    from app.core.errors import NotFoundError
    from app.services import trust

    found = await trust.certificate(db, code)
    if found is None:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", "Bunday kodli sertifikat topilmadi — u soxta bo'lishi mumkin.")
    return found
