"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUserDep, DbSession
from app.schemas.auth import AdminLinkExchangeRequest, AuthUser, TelegramAuthRequest, TokenResponse
from app.security.rate_limit import ADMIN_LOGIN_LIMIT, AUTH_LIMIT, limit_by_ip
from app.services.auth import AuthResult, authenticate_telegram, exchange_admin_login_token, logout_everywhere
from app.services.rbac import is_admin_role_set

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(result: AuthResult) -> TokenResponse:
    return TokenResponse(
        access_token=result.access_token,
        expires_at=result.expires_at,
        scope=result.scope,
        user=AuthUser(
            id=result.user.id,
            first_name=result.user.first_name,
            last_name=result.user.last_name,
            is_admin=is_admin_role_set(result.roles),
            roles=sorted(result.roles),
        ),
    )


@router.post(
    "/telegram",
    response_model=TokenResponse,
    dependencies=[Depends(limit_by_ip(AUTH_LIMIT))],
    summary="Sign in with Telegram Mini App initData",
    description=(
        "Validates the signed `initData` string that Telegram passes to the Mini App and returns an "
        "access token. Use `scope=admin` from the Admin Panel opened inside Telegram."
    ),
)
async def telegram_login(payload: TelegramAuthRequest, db: DbSession) -> TokenResponse:
    return _token_response(await authenticate_telegram(db, payload.init_data, payload.scope))


@router.post(
    "/admin/exchange",
    response_model=TokenResponse,
    dependencies=[Depends(limit_by_ip(ADMIN_LOGIN_LIMIT))],
    summary="Exchange a one-time Admin Panel login link for an admin token",
)
async def admin_link_login(payload: AdminLinkExchangeRequest, db: DbSession) -> TokenResponse:
    return _token_response(await exchange_admin_login_token(db, payload.token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out on every device")
async def logout(current: CurrentUserDep, db: DbSession) -> Response:
    await logout_everywhere(db, current.user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
