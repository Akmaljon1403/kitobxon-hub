"""Admin Panel: system settings (score rules etc.), dashboard statistics and system status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.deps import CurrentAdminDep, CurrentUser, DbSession, require_permissions
from app.schemas.settings import SettingOut, SettingUpdateIn
from app.security.permissions import Perm
from app.services import settings as settings_service
from app.services import system_status
from app.services.statistics import dashboard

router = APIRouter(prefix="/admin", tags=["admin: system"])


@router.get("/settings", response_model=list[SettingOut], summary="All settings with current values")
async def list_settings(_: CurrentAdminDep, db: DbSession) -> list[SettingOut]:
    values = await settings_service.get_all_settings(db)
    return [
        SettingOut(
            key=d.key,
            group=d.group,
            kind=d.kind,
            value=values[d.key],
            default=d.default,
            description=d.description,
            choices=list(d.choices),
        )
        for d in settings_service.SETTING_DEFINITIONS
    ]


@router.put("/settings/{key}", response_model=SettingOut, summary="Change a setting (audited)")
async def update_setting(
    key: str,
    payload: SettingUpdateIn,
    current: Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))],
    db: DbSession,
) -> SettingOut:
    definition = settings_service.get_definition(key)
    value = await settings_service.update_setting(db, key=key, value=payload.value, actor_id=current.user.id)
    return SettingOut(
        key=definition.key,
        group=definition.group,
        kind=definition.kind,
        value=value,
        default=definition.default,
        description=definition.description,
        choices=list(definition.choices),
    )


@router.get("/statistics", summary="Dashboard numbers")
async def statistics(
    _: Annotated[CurrentUser, Depends(require_permissions(Perm.ANALYTICS_VIEW))], db: DbSession
) -> dict[str, Any]:
    return await dashboard(db)


@router.get("/system/status", summary="Production readiness checks (database, bot, storage, worker, owners)")
async def system_status_view(
    _: Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))], db: DbSession
) -> dict[str, Any]:
    return await system_status.collect(db)
