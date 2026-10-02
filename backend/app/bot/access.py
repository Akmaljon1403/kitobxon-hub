"""Who is an administrator, for the bot's menu and admin-only buttons."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.security.permissions import Perm
from app.services.rbac import get_effective_permissions, get_role_codes, is_admin_role_set


async def is_admin(db: AsyncSession, member: User | None) -> bool:
    if member is None:
        return False
    return is_admin_role_set(await get_role_codes(db, member.id))


async def has_permission(db: AsyncSession, member: User | None, permission: Perm) -> bool:
    if member is None:
        return False
    roles = await get_role_codes(db, member.id)
    if not is_admin_role_set(roles):
        return False
    return permission.value in await get_effective_permissions(db, member.id, roles)
