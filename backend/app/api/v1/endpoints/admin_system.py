"""Admin Panel: system settings (score rules etc.), dashboard statistics and system status."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

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


class SearchItem(BaseModel):
    kind: str
    title: str
    subtitle: str | None
    route: str | None


@router.get("/search", response_model=list[SearchItem], summary="Search everything: members, books, settings, pages")
async def search_everything(
    current: CurrentAdminDep, db: DbSession, q: Annotated[str, Query(min_length=1, max_length=64)]
) -> list[SearchItem]:
    from app.services import search

    return [
        SearchItem(**item) for item in await search.search(db, q, permissions=current.permissions, roles=current.roles)
    ]


class LicenceOut(BaseModel):
    required: bool
    valid: bool
    organization: str | None
    expires: str | None
    max_members: int | None
    days_left: int | None
    members_paused: bool
    problem: str | None


@router.get("/system/licence", response_model=LicenceOut, summary="Licence of this copy (rented copies only)")
async def licence_view(_: CurrentAdminDep) -> LicenceOut:
    from app.core import licence

    current = licence.status()
    info = current.licence
    return LicenceOut(
        required=current.required,
        valid=current.valid,
        organization=info.organization if info else None,
        expires=info.expires.isoformat() if info else None,
        max_members=info.max_members if info else None,
        days_left=current.days_left,
        members_paused=current.blocks_members,
        problem=current.problem,
    )


SettingsManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SETTINGS_MANAGE))]


@router.get("/bot-profile", summary="The bot's name, descriptions and avatar: here and in Telegram")
async def bot_profile_view(_: SettingsManager, db: DbSession) -> dict[str, Any]:
    from app.services import bot_profile
    from app.services.delivery import optional_bot

    return await bot_profile.describe(optional_bot(), db)


@router.post("/bot-profile/apply", summary="Send the name, descriptions, command menus and rights to Telegram")
async def bot_profile_apply(_: SettingsManager, db: DbSession) -> dict[str, Any]:
    from app.core.config import get_settings
    from app.services import bot_profile
    from app.services.delivery import runtime_bot

    bot = runtime_bot()
    result = await bot_profile.apply_all(bot, db, get_settings().webapp_url)
    return {"result": result, **await bot_profile.describe(bot, db)}


@router.post("/bot-profile/avatar", summary="Put the club's brand avatar on the bot")
async def bot_profile_avatar(current: SettingsManager, db: DbSession) -> dict[str, Any]:
    from app.core.errors import ServiceUnavailableError
    from app.services import bot_profile
    from app.services.audit import record_audit
    from app.services.delivery import runtime_bot

    bot = runtime_bot()
    try:
        done = await bot_profile.set_avatar(bot)
    except Exception as exc:
        raise ServiceUnavailableError(
            "AVATAR_REFUSED", "Telegram rasmni qabul qilmadi. Birozdan keyin qayta urinib ko'ring."
        ) from exc
    if done:
        record_audit(db, actor_id=current.user.id, action="BOT_AVATAR_SET", entity_type="bot", entity_id="avatar")
        await db.commit()
    return {"ok": done, **await bot_profile.describe(bot, db)}
