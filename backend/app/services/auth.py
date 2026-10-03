"""Authentication: Telegram Mini App login, Admin Panel one-time login links, logout."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ForbiddenError, ServiceUnavailableError, UnauthorizedError
from app.models import LoginToken, User
from app.models.enums import UserStatus
from app.security.crypto import random_token, sha256_hex
from app.security.telegram import InitData, validate_init_data
from app.security.tokens import TokenScope, create_access_token
from app.services.audit import record_audit
from app.services.rbac import ensure_bootstrap_super_admin, get_role_codes, is_admin_role_set


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    expires_at: datetime
    scope: TokenScope
    user: User
    roles: set[str]


class UserNotRegisteredError(ForbiddenError):
    code = "USER_NOT_REGISTERED"
    message = "Siz hali ro'yxatdan o'tmagansiz. Botga /start buyrug'ini yuborib ro'yxatdan o'ting."


class NotAdminError(ForbiddenError):
    code = "NOT_ADMIN"
    message = "Admin panelga kirish huquqingiz yo'q."


class LoginLinkInvalidError(UnauthorizedError):
    code = "LOGIN_LINK_INVALID"
    message = "Kirish havolasi yaroqsiz yoki muddati o'tgan. Botdan yangi havola oling."


_STATUS_ERRORS: dict[UserStatus, tuple[str, str]] = {
    UserStatus.BLOCKED: ("USER_BLOCKED", "Hisobingiz bloklangan. Savollar bo'lsa, klub rahbariyatiga murojaat qiling."),
    UserStatus.PENDING: ("USER_PENDING", "Arizangiz ko'rib chiqilmoqda. Tasdiqlangach, sizga xabar beramiz."),
    UserStatus.INACTIVE: ("USER_INACTIVE", "Hisobingiz faol emas. Klub rahbariyatiga murojaat qiling."),
    UserStatus.LEFT: ("USER_LEFT", "Siz klubdan chiqqansiz. Qaytish uchun botda /start bosing."),
}


def ensure_user_can_sign_in(user: User) -> None:
    """Raises a 403 error with a clear Uzbek message when the account may not be used."""
    if user.deleted_at is not None:
        raise UserNotRegisteredError()
    if user.status != UserStatus.ACTIVE:
        code, message = _STATUS_ERRORS.get(user.status, ("USER_INACTIVE", "Hisobingiz faol emas."))
        raise ForbiddenError(code, message)


def _bot_token() -> str:
    token = get_settings().bot_token
    if token is None:
        raise ServiceUnavailableError("AUTH_NOT_CONFIGURED", "Telegram orqali kirish hali sozlanmagan.")
    return token.get_secret_value()


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def authenticate_telegram(session: AsyncSession, init_data: str, scope: TokenScope = "member") -> AuthResult:
    settings = get_settings()
    data: InitData = validate_init_data(init_data, _bot_token(), settings.init_data_max_age_seconds)

    user = await get_user_by_telegram_id(session, data.user.id)
    if user is None:
        raise UserNotRegisteredError()

    # The bootstrap grant must happen before the status check so the owner can always get in.
    await ensure_bootstrap_super_admin(session, user)
    ensure_user_can_sign_in(user)

    roles = await get_role_codes(session, user.id)
    if scope == "admin" and not is_admin_role_set(roles):
        raise NotAdminError()

    # Keep public Telegram profile details fresh (they can change at any time).
    user.telegram_username = data.user.username
    if data.user.photo_url:
        user.photo_url = data.user.photo_url
    user.last_seen_at = datetime.now(UTC)
    if scope == "admin":
        record_audit(
            session,
            actor_id=user.id,
            action="ADMIN_LOGIN",
            entity_type="user",
            entity_id=user.id,
            after={"method": "telegram_webapp"},
        )
    await session.commit()

    token, expires_at = create_access_token(user.id, user.token_version, scope)
    return AuthResult(token, expires_at, scope, user, roles)


async def create_admin_login_link(session: AsyncSession, user: User) -> tuple[str, datetime]:
    """Create a one-time Admin Panel login token for an admin. Returns (raw token, expiry).

    Only the SHA-256 hash is stored, so the link cannot be reconstructed from the database.
    """
    ensure_user_can_sign_in(user)
    roles = await get_role_codes(session, user.id)
    if not is_admin_role_set(roles):
        raise NotAdminError()
    raw = random_token(32)
    expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().admin_login_link_ttl_seconds)
    session.add(LoginToken(user_id=user.id, token_hash=sha256_hex(raw), expires_at=expires_at))
    await session.commit()
    return raw, expires_at


def admin_login_url(raw_token: str) -> str | None:
    base = get_settings().public_base_url
    if not base:
        return None
    # The token travels in the URL fragment, which browsers never send to servers or in Referer headers.
    return f"{base.rstrip('/')}/admin/#/login?token={raw_token}"


async def exchange_admin_login_token(session: AsyncSession, raw_token: str) -> AuthResult:
    if not raw_token or len(raw_token) > 128:
        raise LoginLinkInvalidError()
    now = datetime.now(UTC)
    # Atomically mark the token as used: a second request with the same token finds nothing.
    login_token_id = await session.scalar(
        update(LoginToken)
        .where(
            LoginToken.token_hash == sha256_hex(raw_token),
            LoginToken.used_at.is_(None),
            LoginToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(LoginToken.user_id)
    )
    if login_token_id is None:
        await session.rollback()
        raise LoginLinkInvalidError()

    user = await session.get(User, login_token_id)
    if user is None:
        await session.rollback()
        raise LoginLinkInvalidError()
    ensure_user_can_sign_in(user)
    roles = await get_role_codes(session, user.id)
    if not is_admin_role_set(roles):
        await session.rollback()
        raise NotAdminError()

    user.last_seen_at = now
    record_audit(
        session,
        actor_id=user.id,
        action="ADMIN_LOGIN",
        entity_type="user",
        entity_id=user.id,
        after={"method": "login_link"},
    )
    await session.commit()
    token, expires_at = create_access_token(user.id, user.token_version, "admin")
    return AuthResult(token, expires_at, "admin", user, roles)


async def logout_everywhere(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Invalidate every access token of the user."""
    await session.execute(update(User).where(User.id == user_id).values(token_version=User.token_version + 1))
    await session.commit()
