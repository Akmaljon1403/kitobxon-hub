"""Shared FastAPI dependencies: database session, current user, admin and permission checks."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.models import User
from app.security.permissions import Perm
from app.security.tokens import TokenInvalidError, TokenScope, decode_access_token
from app.services.auth import NotAdminError, ensure_user_can_sign_in
from app.services.rbac import get_effective_permissions, get_role_codes, is_admin_role_set

DbSession = Annotated[AsyncSession, Depends(get_db)]

_bearer = HTTPBearer(auto_error=False, description="Access token from /api/v1/auth/telegram")


@dataclass
class CurrentUser:
    user: User
    scope: TokenScope
    roles: set[str]
    permissions: set[str] = field(default_factory=set)

    @property
    def id(self):
        return self.user.id

    @property
    def is_admin(self) -> bool:
        return is_admin_role_set(self.roles)

    def has(self, permission: Perm) -> bool:
        return permission.value in self.permissions


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Authenticated, active member. 401 without a valid token, 403 for blocked/inactive accounts."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthorizedError()
    claims = decode_access_token(credentials.credentials)
    user = await db.get(User, claims.user_id)
    if user is None or user.token_version != claims.token_version:
        raise TokenInvalidError()
    ensure_user_can_sign_in(user)
    roles = await get_role_codes(db, user.id)
    return CurrentUser(user=user, scope=claims.scope, roles=roles)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def get_current_admin(db: DbSession, current: CurrentUserDep) -> CurrentUser:
    """Admin Panel session: admin-scoped token and an admin role that is still assigned."""
    if current.scope != "admin":
        raise ForbiddenError("ADMIN_SESSION_REQUIRED", "Bu amal faqat admin panel orqali bajariladi.")
    if not current.is_admin:
        raise NotAdminError()
    current.permissions = await get_effective_permissions(db, current.user.id, current.roles)
    return current


CurrentAdminDep = Annotated[CurrentUser, Depends(get_current_admin)]


def require_permissions(*permissions: Perm) -> Callable[..., Coroutine[Any, Any, CurrentUser]]:
    """Dependency factory: the admin must hold every listed permission (SUPER_ADMIN holds all)."""

    async def dependency(current: CurrentAdminDep) -> CurrentUser:
        missing = [perm.value for perm in permissions if perm.value not in current.permissions]
        if missing:
            raise ForbiddenError("PERMISSION_DENIED", "Bu amal uchun ruxsatingiz yo'q.", details={"required": missing})
        return current

    return dependency


async def require_super_admin(current: CurrentAdminDep) -> CurrentUser:
    """Managing admins, roles and permissions is reserved for SUPER_ADMIN (spec section 7)."""
    if "SUPER_ADMIN" not in current.roles:
        raise ForbiddenError("SUPER_ADMIN_REQUIRED", "Bu amal faqat bosh administrator uchun.")
    return current


SuperAdminDep = Annotated[CurrentUser, Depends(require_super_admin)]
