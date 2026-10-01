"""Admin Panel: own session info, admins, roles, permissions and the audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select

from app.api.deps import CurrentAdminDep, CurrentUser, DbSession, SuperAdminDep, require_permissions
from app.models import Permission
from app.schemas.admin import (
    AdminOut,
    AdminPermissionsIn,
    AdminRolesIn,
    AdminSelfOut,
    AppointAdminIn,
    AuditLogOut,
    PermissionOut,
    RoleCreateIn,
    RoleOut,
    RoleUpdateIn,
)
from app.schemas.common import Page, ReasonIn
from app.security.permissions import Perm
from app.services import admins as admin_service
from app.services.admins import AdminView
from app.services.audit import list_audit_logs

router = APIRouter(prefix="/admin", tags=["admin: access control"])


def _admin_out(view: AdminView) -> AdminOut:
    return AdminOut(
        user_id=view.user.id,
        first_name=view.user.first_name,
        last_name=view.user.last_name,
        telegram_username=view.user.telegram_username,
        roles=view.roles,
        direct_permissions=view.direct_permissions,
        effective_permissions=view.effective_permissions,
    )


@router.get("/me", response_model=AdminSelfOut, summary="Current admin with effective permissions")
async def admin_me(current: CurrentAdminDep) -> AdminSelfOut:
    return AdminSelfOut(
        id=current.user.id,
        first_name=current.user.first_name,
        last_name=current.user.last_name,
        roles=sorted(current.roles),
        permissions=sorted(current.permissions),
        is_super_admin="SUPER_ADMIN" in current.roles,
    )


@router.get("/permissions", response_model=list[PermissionOut], summary="Permission catalogue")
async def permission_catalogue(_: CurrentAdminDep, db: DbSession) -> list[PermissionOut]:
    rows = await db.scalars(select(Permission).order_by(Permission.group, Permission.code))
    return [PermissionOut(code=row.code, group=row.group, description=row.description) for row in rows]


# ---------------------------------------------------------------------------- admins


@router.get("/admins", response_model=list[AdminOut], summary="List admins")
async def list_admins(_: SuperAdminDep, db: DbSession) -> list[AdminOut]:
    return [_admin_out(view) for view in await admin_service.list_admins(db)]


@router.post("/admins", response_model=AdminOut, status_code=status.HTTP_201_CREATED, summary="Appoint an admin")
async def appoint_admin(payload: AppointAdminIn, current: SuperAdminDep, db: DbSession) -> AdminOut:
    view = await admin_service.appoint_admin(
        db,
        actor_id=current.user.id,
        user_id=payload.user_id,
        permissions=payload.permissions,
        extra_roles=payload.extra_roles,
    )
    return _admin_out(view)


@router.get("/admins/{user_id}", response_model=AdminOut, summary="Admin details")
async def get_admin(user_id: uuid.UUID, _: SuperAdminDep, db: DbSession) -> AdminOut:
    return _admin_out(await admin_service.get_admin_view(db, user_id))


@router.put("/admins/{user_id}/permissions", response_model=AdminOut, summary="Replace an admin's own permissions")
async def set_admin_permissions(
    user_id: uuid.UUID, payload: AdminPermissionsIn, current: SuperAdminDep, db: DbSession
) -> AdminOut:
    view = await admin_service.set_admin_permissions(
        db, actor_id=current.user.id, user_id=user_id, permissions=payload.permissions
    )
    return _admin_out(view)


@router.put("/admins/{user_id}/roles", response_model=AdminOut, summary="Replace an admin's roles")
async def set_admin_roles(user_id: uuid.UUID, payload: AdminRolesIn, current: SuperAdminDep, db: DbSession) -> AdminOut:
    view = await admin_service.set_admin_roles(db, actor_id=current.user.id, user_id=user_id, roles=payload.roles)
    return _admin_out(view)


@router.post("/admins/{user_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT, summary="Remove admin rights")
async def dismiss_admin(user_id: uuid.UUID, payload: ReasonIn, current: SuperAdminDep, db: DbSession) -> Response:
    await admin_service.dismiss_admin(db, actor_id=current.user.id, user_id=user_id, reason=payload.reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- roles


@router.get("/roles", response_model=list[RoleOut], summary="List roles")
async def list_roles(_: SuperAdminDep, db: DbSession) -> list[RoleOut]:
    return [
        RoleOut(
            id=role.id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=permissions,
        )
        for role, permissions in await admin_service.list_roles(db)
    ]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED, summary="Create a custom role")
async def create_role(payload: RoleCreateIn, current: SuperAdminDep, db: DbSession) -> RoleOut:
    role = await admin_service.create_role(
        db,
        actor_id=current.user.id,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions,
    )
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=False,
        permissions=sorted(set(payload.permissions)),
    )


@router.patch("/roles/{role_id}", response_model=RoleOut, summary="Update a custom role")
async def update_role(role_id: uuid.UUID, payload: RoleUpdateIn, current: SuperAdminDep, db: DbSession) -> RoleOut:
    await admin_service.update_role(
        db,
        actor_id=current.user.id,
        role_id=role_id,
        name=payload.name,
        description=payload.description,
        permissions=payload.permissions,
    )
    for role, permissions in await admin_service.list_roles(db):
        if role.id == role_id:
            return RoleOut(
                id=role.id,
                code=role.code,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                permissions=permissions,
            )
    raise AssertionError("updated role disappeared")  # pragma: no cover


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a custom role")
async def delete_role(role_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> Response:
    await admin_service.delete_role(db, actor_id=current.user.id, role_id=role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------- audit log


@router.get("/audit-logs", response_model=Page[AuditLogOut], summary="Audit log (newest first)")
async def audit_logs(
    _: Annotated[CurrentUser, Depends(require_permissions(Perm.AUDIT_LOG_VIEW))],
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=64)] = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    actor_id: uuid.UUID | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Page[AuditLogOut]:
    rows, total = await list_audit_logs(
        db,
        limit=limit,
        offset=offset,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        since=since,
        until=until,
    )
    items = [
        AuditLogOut(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_name=name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before=log.before,
            after=log.after,
            reason=log.reason,
            request_id=log.request_id,
            created_at=log.created_at,
        )
        for log, name in rows
    ]
    return Page[AuditLogOut](items=items, total=total, limit=limit, offset=offset)
