"""Administration of admins, roles and permissions (SUPER_ADMIN only).

Every change is written to the audit log with the previous and the new value.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import Role, RolePermission, User, UserPermission, UserRole
from app.models.enums import SystemRole, UserStatus
from app.security.permissions import Perm
from app.services.audit import record_audit
from app.services.rbac import ADMIN_ROLES, get_effective_permissions, get_role_by_code, get_role_codes


@dataclass(frozen=True)
class AdminView:
    user: User
    roles: list[str]
    direct_permissions: list[str]
    effective_permissions: list[str]


def _validate_permissions(codes: Iterable[str]) -> list[str]:
    valid = {perm.value for perm in Perm}
    unique = sorted(set(codes))
    unknown = [code for code in unique if code not in valid]
    if unknown:
        raise BadRequestError("UNKNOWN_PERMISSION", "Noma'lum ruxsat ko'rsatildi.", details={"unknown": unknown})
    return unique


async def _get_active_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    return user


async def _direct_permissions(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await session.scalars(select(UserPermission.permission_code).where(UserPermission.user_id == user_id))
    return sorted(rows)


async def get_admin_view(session: AsyncSession, user_id: uuid.UUID) -> AdminView:
    user = await _get_active_user(session, user_id)
    roles = await get_role_codes(session, user_id)
    if not roles & ADMIN_ROLES:
        raise NotFoundError("ADMIN_NOT_FOUND", "Bu foydalanuvchi admin emas.")
    return AdminView(
        user=user,
        roles=sorted(roles),
        direct_permissions=await _direct_permissions(session, user_id),
        effective_permissions=sorted(await get_effective_permissions(session, user_id, roles)),
    )


async def list_admins(session: AsyncSession) -> list[AdminView]:
    admin_ids = await session.scalars(
        select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code.in_(ADMIN_ROLES)).distinct()
    )
    views = [await get_admin_view(session, user_id) for user_id in admin_ids]
    return sorted(views, key=lambda view: (view.user.first_name.lower(), view.user.last_name.lower()))


async def _set_direct_permissions(session: AsyncSession, user_id: uuid.UUID, codes: list[str], actor_id: uuid.UUID):
    await session.execute(delete(UserPermission).where(UserPermission.user_id == user_id))
    session.add_all(UserPermission(user_id=user_id, permission_code=code, granted_by=actor_id) for code in codes)


async def _count_super_admins(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count())
        .select_from(UserRole)
        .join(Role, Role.id == UserRole.role_id)
        .join(User, User.id == UserRole.user_id)
        .where(Role.code == SystemRole.SUPER_ADMIN, User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
    )


async def _resolve_roles(session: AsyncSession, codes: Iterable[str]) -> list[Role]:
    roles: list[Role] = []
    for code in sorted(set(codes)):
        if code == SystemRole.USER:
            continue  # every member implicitly has the USER role
        role = await get_role_by_code(session, code)
        if role is None:
            raise BadRequestError("UNKNOWN_ROLE", "Noma'lum rol ko'rsatildi.", details={"role": code})
        roles.append(role)
    return roles


async def appoint_admin(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    permissions: list[str],
    extra_roles: list[str] | None = None,
) -> AdminView:
    """Give a registered, active member the ADMIN role with an explicit set of permissions."""
    user = await _get_active_user(session, user_id)
    if user.status != UserStatus.ACTIVE:
        raise BadRequestError("USER_NOT_ACTIVE", "Faqat faol a'zoni admin qilish mumkin.")
    current_roles = await get_role_codes(session, user_id)
    if current_roles & ADMIN_ROLES:
        raise ConflictError("ALREADY_ADMIN", "Bu foydalanuvchi allaqachon admin.")
    codes = _validate_permissions(permissions)
    roles = await _resolve_roles(session, [SystemRole.ADMIN, *(extra_roles or [])])

    session.add_all(UserRole(user_id=user_id, role_id=role.id, granted_by=actor_id) for role in roles)
    await _set_direct_permissions(session, user_id, codes, actor_id)
    record_audit(
        session,
        actor_id=actor_id,
        action="ADMIN_CREATE",
        entity_type="user",
        entity_id=user_id,
        before={"roles": sorted(current_roles)},
        after={"roles": sorted(role.code for role in roles), "permissions": codes},
    )
    await session.commit()
    return await get_admin_view(session, user_id)


async def set_admin_permissions(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, permissions: list[str]
) -> AdminView:
    before = await get_admin_view(session, user_id)
    codes = _validate_permissions(permissions)
    await _set_direct_permissions(session, user_id, codes, actor_id)
    record_audit(
        session,
        actor_id=actor_id,
        action="ADMIN_PERMISSIONS_CHANGE",
        entity_type="user",
        entity_id=user_id,
        before={"permissions": before.direct_permissions},
        after={"permissions": codes},
    )
    await session.commit()
    return await get_admin_view(session, user_id)


async def set_admin_roles(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, roles: list[str]
) -> AdminView:
    """Replace the roles of an admin. The result must still contain ADMIN or SUPER_ADMIN."""
    before = await get_admin_view(session, user_id)
    new_roles = await _resolve_roles(session, roles)
    new_codes = {role.code for role in new_roles}
    if not new_codes & ADMIN_ROLES:
        raise BadRequestError(
            "ADMIN_ROLE_REQUIRED",
            "Admin rolini olib tashlash uchun adminni o'chirish amalidan foydalaning.",
        )
    if SystemRole.SUPER_ADMIN in before.roles and SystemRole.SUPER_ADMIN not in new_codes:
        await _ensure_not_last_super_admin(session)

    await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    session.add_all(UserRole(user_id=user_id, role_id=role.id, granted_by=actor_id) for role in new_roles)
    record_audit(
        session,
        actor_id=actor_id,
        action="ADMIN_ROLES_CHANGE",
        entity_type="user",
        entity_id=user_id,
        before={"roles": before.roles},
        after={"roles": sorted(new_codes)},
    )
    await session.commit()
    return await get_admin_view(session, user_id)


async def _ensure_not_last_super_admin(session: AsyncSession) -> None:
    if await _count_super_admins(session) <= 1:
        raise ForbiddenError(
            "LAST_SUPER_ADMIN", "Oxirgi bosh administratorni olib tashlab bo'lmaydi: tizim boshqaruvsiz qoladi."
        )


async def dismiss_admin(session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> None:
    """Remove all admin roles and permissions; the person stays a regular member."""
    before = await get_admin_view(session, user_id)
    if SystemRole.SUPER_ADMIN in before.roles:
        await _ensure_not_last_super_admin(session)
    await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    await session.execute(delete(UserPermission).where(UserPermission.user_id == user_id))
    # End every Admin Panel session of this person immediately.
    await session.execute(update(User).where(User.id == user_id).values(token_version=User.token_version + 1))
    record_audit(
        session,
        actor_id=actor_id,
        action="ADMIN_DEACTIVATE",
        entity_type="user",
        entity_id=user_id,
        before={"roles": before.roles, "permissions": before.direct_permissions},
        after={"roles": [], "permissions": []},
        reason=reason,
    )
    await session.commit()


# ---------------------------------------------------------------------------- custom roles


async def list_roles(session: AsyncSession) -> list[tuple[Role, list[str]]]:
    roles = list(await session.scalars(select(Role).order_by(Role.is_system.desc(), Role.name)))
    rows = await session.execute(select(RolePermission.role_id, RolePermission.permission_code))
    by_role: dict[uuid.UUID, list[str]] = {}
    for role_id, code in rows:
        by_role.setdefault(role_id, []).append(code)
    return [(role, sorted(by_role.get(role.id, []))) for role in roles]


async def create_role(
    session: AsyncSession, *, actor_id: uuid.UUID, code: str, name: str, description: str | None, permissions: list[str]
) -> Role:
    if await get_role_by_code(session, code) is not None:
        raise ConflictError("ROLE_EXISTS", "Bunday kodli rol allaqachon mavjud.")
    codes = _validate_permissions(permissions)
    role = Role(code=code, name=name, description=description, is_system=False)
    session.add(role)
    await session.flush()
    session.add_all(RolePermission(role_id=role.id, permission_code=code_) for code_ in codes)
    record_audit(
        session,
        actor_id=actor_id,
        action="ROLE_CREATE",
        entity_type="role",
        entity_id=role.id,
        after={"code": code, "name": name, "permissions": codes},
    )
    await session.commit()
    return role


async def _get_custom_role(session: AsyncSession, role_id: uuid.UUID) -> Role:
    role = await session.get(Role, role_id)
    if role is None:
        raise NotFoundError("ROLE_NOT_FOUND", "Rol topilmadi.")
    if role.is_system:
        raise ForbiddenError("SYSTEM_ROLE", "Tizim rollarini o'zgartirib bo'lmaydi.")
    return role


async def update_role(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    role_id: uuid.UUID,
    name: str | None,
    description: str | None,
    permissions: list[str] | None,
) -> Role:
    role = await _get_custom_role(session, role_id)
    old_permissions = sorted(
        await session.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role_id))
    )
    before = {"name": role.name, "description": role.description, "permissions": old_permissions}
    if name is not None:
        role.name = name
    if description is not None:
        role.description = description
    new_permissions = old_permissions
    if permissions is not None:
        new_permissions = _validate_permissions(permissions)
        await session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        session.add_all(RolePermission(role_id=role_id, permission_code=code) for code in new_permissions)
    record_audit(
        session,
        actor_id=actor_id,
        action="ROLE_UPDATE",
        entity_type="role",
        entity_id=role_id,
        before=before,
        after={"name": role.name, "description": role.description, "permissions": new_permissions},
    )
    await session.commit()
    return role


async def delete_role(session: AsyncSession, *, actor_id: uuid.UUID, role_id: uuid.UUID) -> None:
    role = await _get_custom_role(session, role_id)
    record_audit(
        session,
        actor_id=actor_id,
        action="ROLE_DELETE",
        entity_type="role",
        entity_id=role_id,
        before={"code": role.code, "name": role.name},
    )
    await session.delete(role)
    await session.commit()
