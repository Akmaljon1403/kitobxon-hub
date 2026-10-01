"""Access tokens (JWT, HS256) issued after Telegram authentication.

Tokens are short-lived and carry the user's ``token_version``: blocking a user or
logging out increments the version in the database and immediately invalidates every
token issued before. The signing key is derived from ``SECRET_KEY`` for this purpose only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.security.crypto import derive_key

TokenScope = Literal["member", "admin"]
_ALGORITHM = "HS256"
_ISSUER = "kitobxon-hub"


@dataclass(frozen=True)
class TokenClaims:
    user_id: uuid.UUID
    token_version: int
    scope: TokenScope
    expires_at: datetime


class TokenExpiredError(UnauthorizedError):
    code = "TOKEN_EXPIRED"
    message = "Sessiya muddati tugadi. Qaytadan kiring."


class TokenInvalidError(UnauthorizedError):
    code = "TOKEN_INVALID"
    message = "Avtorizatsiya ma'lumotlari yaroqsiz. Qaytadan kiring."


def _key() -> bytes:
    return derive_key("jwt-access")


def create_access_token(user_id: uuid.UUID, token_version: int, scope: TokenScope) -> tuple[str, datetime]:
    settings = get_settings()
    ttl = settings.admin_token_ttl_minutes if scope == "admin" else settings.access_token_ttl_minutes
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=ttl)
    payload = {
        "iss": _ISSUER,
        "sub": str(user_id),
        "ver": token_version,
        "scope": scope,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _key(), algorithm=_ALGORITHM), expires_at


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            _key(),
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
            leeway=30,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
        scope = payload.get("scope")
        if scope not in ("member", "admin"):
            raise TokenInvalidError()
        return TokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            token_version=int(payload["ver"]),
            scope=scope,
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidError() from exc
