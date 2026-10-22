"""Admin Panel: members (search, details, corrections, approve / block)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models import User
from app.models.enums import UserStatus
from app.schemas.common import Page, ReasonIn
from app.schemas.user import AdminUserDetailOut, AdminUserOut, AdminUserUpdateIn, EraseIn, UserStatusIn
from app.security.permissions import Perm
from app.services import membership
from app.services import passport as passport_service
from app.services import users as user_service
from app.services.audit import record_audit
from app.services.rbac import get_role_codes

router = APIRouter(prefix="/admin/users", tags=["admin: members"])
Viewer = Annotated[CurrentUser, Depends(require_permissions(Perm.USER_VIEW))]
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.USER_VIEW, Perm.USER_MANAGE))]


def _out(user: User, faculty_name: str | None, current: CurrentUser) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_username=user.telegram_username,
        phone=user.phone if current.has(Perm.USER_CONTACT_VIEW) else None,
        faculty_id=user.faculty_id,
        faculty_name=faculty_name,
        course=user.course,
        group_name=user.group_name,
        status=user.status,
        registered_at=user.registered_at,
        last_seen_at=user.last_seen_at,
        left_at=user.left_at,
        left_reason=user.left_reason,
        restore_requested_at=user.restore_requested_at,
        graduated_at=user.graduated_at,
    )


async def _detail(db, user: User, current: CurrentUser) -> AdminUserDetailOut:
    base = _out(user, await user_service.faculty_name(db, user.faculty_id), current)
    return AdminUserDetailOut(**base.model_dump(), roles=sorted(await get_role_codes(db, user.id)))


@router.get("", response_model=Page[AdminUserOut], summary="Search members")
async def list_users(
    current: Viewer,
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    status: UserStatus | None = None,
    faculty_id: uuid.UUID | None = None,
    course: Annotated[int | None, Query(ge=1, le=8)] = None,
    group_name: Annotated[str | None, Query(max_length=16)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminUserOut]:
    filters = user_service.UserFilters(
        search=search, status=status, faculty_id=faculty_id, course=course, group_name=group_name
    )
    rows, total = await user_service.list_users(
        db, filters=filters, limit=limit, offset=offset, allow_phone_search=current.has(Perm.USER_CONTACT_VIEW)
    )
    return Page[AdminUserOut](
        items=[_out(user, faculty, current) for user, faculty in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{user_id}", response_model=AdminUserDetailOut, summary="Member details")
async def get_user(user_id: uuid.UUID, current: Viewer, db: DbSession) -> AdminUserDetailOut:
    return await _detail(db, await user_service.get_user(db, user_id), current)


@router.get("/{user_id}/overview", summary="A member's whole picture: points, activity, premium, support")
async def member_overview(user_id: uuid.UUID, _: Viewer, db: DbSession) -> dict:
    from app.services import member_overview as overview_service

    await user_service.get_user(db, user_id)  # 404 for an unknown member
    return await overview_service.overview(db, user_id)


@router.patch("/{user_id}", response_model=AdminUserDetailOut, summary="Correct a member's data")
async def update_user(
    user_id: uuid.UUID, payload: AdminUserUpdateIn, current: Manager, db: DbSession
) -> AdminUserDetailOut:
    user = await user_service.admin_update_user(
        db, actor_id=current.user.id, user_id=user_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _detail(db, user, current)


@router.post("/{user_id}/status", response_model=AdminUserDetailOut, summary="Approve, block or deactivate")
async def change_status(
    user_id: uuid.UUID, payload: UserStatusIn, current: Manager, db: DbSession
) -> AdminUserDetailOut:
    user = await user_service.change_user_status(
        db,
        actor_id=current.user.id,
        actor_roles=current.roles,
        user_id=user_id,
        status=payload.status,
        reason=payload.reason,
    )
    return await _detail(db, user, current)


@router.delete(
    "/{user_id}/passport-photo",
    status_code=204,
    summary="Remove an unsuitable passport photo (the Telegram picture is used again)",
)
async def remove_passport_photo(user_id: uuid.UUID, current: Manager, db: DbSession) -> Response:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    record_audit(db, actor_id=current.user.id, action="PASSPORT_PHOTO_REMOVE", entity_type="user", entity_id=user.id)
    await passport_service.clear_photo(db, user)
    return Response(status_code=204)


@router.post(
    "/{user_id}/cancel-membership",
    response_model=AdminUserDetailOut,
    summary="Cancel the membership (the data is kept 30 days; the member can ask to come back)",
)
async def cancel_membership(
    user_id: uuid.UUID, payload: ReasonIn, current: Manager, db: DbSession
) -> AdminUserDetailOut:
    user = await membership.admin_cancel(db, actor_id=current.user.id, user_id=user_id, reason=payload.reason)
    return await _detail(db, user, current)


@router.post("/{user_id}/restore", response_model=AdminUserDetailOut, summary="Bring back a member who left")
async def restore_membership(user_id: uuid.UUID, current: Manager, db: DbSession) -> AdminUserDetailOut:
    user = await user_service.get_user(db, user_id)
    await membership.restore(db, user, actor_id=current.user.id)
    return await _detail(db, user, current)


@router.post(
    "/{user_id}/erase",
    status_code=204,
    summary="Erase the member's personal data for good (super admin; type O'CHIRISH to confirm)",
)
async def erase_member(user_id: uuid.UUID, payload: EraseIn, current: Manager, db: DbSession) -> Response:
    if "SUPER_ADMIN" not in current.roles:
        raise ForbiddenError("SUPER_ADMIN_ONLY", "Ma'lumotlarni faqat bosh administrator o'chira oladi.")
    if payload.confirm.strip().upper() not in ("O'CHIRISH", "OCHIRISH"):
        raise BadRequestError("CONFIRM_REQUIRED", "Tasdiqlash uchun «O'CHIRISH» deb yozing.")
    await membership.admin_erase(db, actor_id=current.user.id, user_id=user_id, reason=payload.reason)
    return Response(status_code=204)
