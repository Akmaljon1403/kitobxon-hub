"""Role and permission resolution.

Effective permissions of a user = permissions of all their roles + permissions granted to
them directly. SUPER_ADMIN implicitly holds every permission. Access to the Admin Panel
requires the ADMIN or SUPER_ADMIN role.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Select, and_, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Role, RolePermission, User, UserPermission, UserRole
from app.models.enums import SystemRole, UserStatus
from app.security.permissions import Perm
from app.services.audit import record_audit

ADMIN_ROLES = frozenset({SystemRole.SUPER_ADMIN.value, SystemRole.ADMIN.value})
ALL_PERMISSIONS = frozenset(perm.value for perm in Perm)


async def get_role_codes(session: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    return set(rows)


async def get_effective_permissions(
    session: AsyncSession, user_id: uuid.UUID, roles: set[str] | None = None
) -> set[str]:
    roles = roles if roles is not None else await get_role_codes(session, user_id)
    if SystemRole.SUPER_ADMIN.value in roles:
        return set(ALL_PERMISSIONS)
    via_roles = (
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    direct = select(UserPermission.permission_code).where(UserPermission.user_id == user_id)
    rows = await session.execute(union(via_roles, direct))
    return {row[0] for row in rows}


def is_admin_role_set(roles: set[str]) -> bool:
    return bool(roles & ADMIN_ROLES)


async def get_role_by_code(session: AsyncSession, code: str) -> Role | None:
    return await session.scalar(select(Role).where(Role.code == code))


async def ensure_bootstrap_super_admin(session: AsyncSession, user: User) -> bool:
    """Grant SUPER_ADMIN to users listed in ``SUPER_ADMIN_TELEGRAM_IDS``. Returns True if granted now.

    The caller commits. Removing an ID from the variable does not revoke the role
    automatically; that is done explicitly from the Admin Panel so it is audited.
    """
    if user.telegram_id not in get_settings().super_admin_telegram_ids:
        return False
    role = await get_role_by_code(session, SystemRole.SUPER_ADMIN)
    if role is None:
        return False
    existing = await session.get(UserRole, (user.id, role.id))
    if existing is not None:
        return False
    session.add(UserRole(user_id=user.id, role_id=role.id, granted_by=None))
    record_audit(
        session,
        actor_id=None,
        action="SUPER_ADMIN_BOOTSTRAP",
        entity_type="user",
        entity_id=user.id,
        after={"role": SystemRole.SUPER_ADMIN.value},
        reason="Telegram ID listed in SUPER_ADMIN_TELEGRAM_IDS",
    )
    await session.flush()
    return True


def admins_with_permission(permission: Perm) -> Select[tuple[uuid.UUID]]:
    """Active administrators who hold ``permission`` (super admins hold every permission)."""
    super_admins = (
        select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code == SystemRole.SUPER_ADMIN)
    )
    admins = select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code == SystemRole.ADMIN)
    via_roles = (
        select(UserRole.user_id)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .where(RolePermission.permission_code == permission.value)
    )
    direct = select(UserPermission.user_id).where(UserPermission.permission_code == permission.value)
    return select(User.id).where(
        User.status == UserStatus.ACTIVE,
        User.deleted_at.is_(None),
        or_(User.id.in_(super_admins), and_(User.id.in_(admins), or_(User.id.in_(via_roles), User.id.in_(direct)))),
    )


def super_admins() -> Select[tuple[uuid.UUID]]:
    """Active super administrators (money matters such as card payments go only to them)."""
    holders = (
        select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(Role.code == SystemRole.SUPER_ADMIN)
    )
    return select(User.id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), User.id.in_(holders))


def all_admins() -> Select[tuple[uuid.UUID]]:
    """Active administrators of any kind (super admins and ordinary admins) — the «Adminlarga» broadcast."""
    holders = (
        select(UserRole.user_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.code.in_((SystemRole.SUPER_ADMIN, SystemRole.ADMIN)))
    )
    return select(User.id).where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), User.id.in_(holders))
