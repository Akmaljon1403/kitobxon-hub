"""Phase 3: Telegram initData validation, access tokens, admin login links, logout, rate limits."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, LoginToken, UserRole
from app.models.enums import UserStatus
from app.security.crypto import derive_key
from app.security.telegram import InitDataError, InitDataExpiredError, validate_init_data
from app.services.auth import create_admin_login_link
from tests.factories import create_user
from tests.helpers import admin_headers, auth_header, grant_role, login, make_init_data, member_headers

BOT_TOKEN = "123456789:TEST-bot-token-AAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

# ---------------------------------------------------------------------------- initData validation (unit)


def test_valid_init_data_is_accepted() -> None:
    data = validate_init_data(make_init_data(42, first_name="Dilnoza"), BOT_TOKEN, max_age_seconds=3600)
    assert data.user.id == 42
    assert data.user.first_name == "Dilnoza"
    assert data.user.username == "akmal_reader"


def test_tampered_user_id_is_rejected() -> None:
    init_data = make_init_data(42).replace("%22id%22%3A42", "%22id%22%3A43")
    assert "%22id%22%3A43" in init_data
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


def test_signature_from_another_bot_is_rejected() -> None:
    init_data = make_init_data(42, bot_token="987654321:OTHER-bot-token-BBBBBBBBBBBBBBBBBBBBBBBBBBB")
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


def test_missing_hash_is_rejected() -> None:
    init_data = "&".join(part for part in make_init_data(42).split("&") if not part.startswith("hash="))
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)


@pytest.mark.parametrize("garbage", ["", "not-a-query", "a=1&a=2", "x" * 5000])
def test_malformed_init_data_is_rejected(garbage: str) -> None:
    with pytest.raises(InitDataError):
        validate_init_data(garbage, BOT_TOKEN, max_age_seconds=3600)


def test_expired_init_data_is_rejected() -> None:
    old = int(time.time()) - 7200
    with pytest.raises(InitDataExpiredError):
        validate_init_data(make_init_data(42, auth_date=old), BOT_TOKEN, max_age_seconds=3600)


def test_future_auth_date_is_rejected() -> None:
    future = int(time.time()) + 3600
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(42, auth_date=future), BOT_TOKEN, max_age_seconds=3600)


def test_extra_signed_fields_are_part_of_signature() -> None:
    init_data = make_init_data(42, extra={"start_param": "att_abc", "signature": "xyz"})
    data = validate_init_data(init_data, BOT_TOKEN, max_age_seconds=3600)
    assert data.start_param == "att_abc"
    with pytest.raises(InitDataError):
        validate_init_data(init_data.replace("att_abc", "att_evil"), BOT_TOKEN, max_age_seconds=3600)


# ---------------------------------------------------------------------------- login endpoint


async def test_registered_member_can_log_in(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db, telegram_id=7001)
    await db.commit()

    response = await login(client, 7001)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "member"
    assert body["user"]["id"] == str(user.id)
    assert body["user"]["is_admin"] is False

    me = await client.get("/api/v1/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["first_name"] == user.first_name
    assert me.json()["phone"] == user.phone


async def test_login_updates_telegram_username(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db, telegram_id=7002, telegram_username=None)
    await db.commit()
    assert (await login(client, 7002)).status_code == 200
    await db.refresh(user)
    assert user.telegram_username == "akmal_reader"
    assert user.last_seen_at is not None


async def test_unregistered_user_gets_clear_error(client: httpx.AsyncClient) -> None:
    response = await login(client, 7999)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "USER_NOT_REGISTERED"


async def test_forged_init_data_rejected_by_api(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, telegram_id=7003)
    await db.commit()
    forged = make_init_data(7003, bot_token="111:forged-forged-forged-forged-forged-forged")
    response = await client.post("/api/v1/auth/telegram", json={"init_data": forged})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INIT_DATA_INVALID"


async def test_expired_init_data_rejected_by_api(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, telegram_id=7004)
    await db.commit()
    response = await login(client, 7004, auth_date=int(time.time()) - 3 * 86400)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INIT_DATA_EXPIRED"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (UserStatus.BLOCKED, "USER_BLOCKED"),
        (UserStatus.PENDING, "USER_PENDING"),
        (UserStatus.INACTIVE, "USER_INACTIVE"),
    ],
)
async def test_non_active_users_cannot_log_in(
    client: httpx.AsyncClient, db: AsyncSession, status: UserStatus, code: str
) -> None:
    await create_user(db, telegram_id=7005, status=status)
    await db.commit()
    response = await login(client, 7005)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == code


async def test_deleted_user_cannot_log_in(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, telegram_id=7006, deleted_at=datetime.now(UTC))
    await db.commit()
    assert (await login(client, 7006)).json()["error"]["code"] == "USER_NOT_REGISTERED"


# ---------------------------------------------------------------------------- access tokens


async def test_me_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
async def test_malformed_tokens_rejected(client: httpx.AsyncClient, token: str) -> None:
    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_token_signed_with_other_key_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    payload = {
        "iss": "kitobxon-hub",
        "sub": str(user.id),
        "ver": 0,
        "scope": "member",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    forged = jwt.encode(payload, "attacker-key-attacker-key-attacker-key", algorithm="HS256")
    response = await client.get("/api/v1/me", headers=auth_header(forged))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"


async def test_unsigned_token_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    payload = {
        "iss": "kitobxon-hub",
        "sub": str(user.id),
        "ver": 0,
        "scope": "member",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    unsigned = jwt.encode(payload, None, algorithm="none")
    assert (await client.get("/api/v1/me", headers=auth_header(unsigned))).status_code == 401


async def test_expired_token_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    payload = {
        "iss": "kitobxon-hub",
        "sub": str(user.id),
        "ver": 0,
        "scope": "member",
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,
    }
    expired = jwt.encode(payload, derive_key("jwt-access"), algorithm="HS256")
    response = await client.get("/api/v1/me", headers=auth_header(expired))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_EXPIRED"


async def test_token_for_unknown_user_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from app.security.tokens import create_access_token

    token, _ = create_access_token(uuid.uuid4(), 0, "member")
    assert (await client.get("/api/v1/me", headers=auth_header(token))).status_code == 401


async def test_blocking_user_invalidates_existing_session(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    headers = member_headers(user)
    assert (await client.get("/api/v1/me", headers=headers)).status_code == 200

    user.status = UserStatus.BLOCKED
    await db.commit()
    response = await client.get("/api/v1/me", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "USER_BLOCKED"


async def test_logout_invalidates_all_tokens(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await create_user(db)
    await db.commit()
    headers = member_headers(user)
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert (await client.get("/api/v1/me", headers=headers)).status_code == 401


# ---------------------------------------------------------------------------- admin access


async def test_member_cannot_request_admin_scope(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, telegram_id=7100)
    await db.commit()
    response = await login(client, 7100, scope="admin")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "NOT_ADMIN"


async def test_super_admin_bootstrap_from_environment(client: httpx.AsyncClient, db: AsyncSession) -> None:
    # 900000001 is listed in SUPER_ADMIN_TELEGRAM_IDS by the test configuration.
    user = await create_user(db, telegram_id=900000001)
    await db.commit()

    response = await login(client, 900000001, scope="admin")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "admin"
    assert body["user"]["roles"] == ["SUPER_ADMIN"]

    actions = set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_id == str(user.id))))
    assert {"SUPER_ADMIN_BOOTSTRAP", "ADMIN_LOGIN"} <= actions

    # A second login does not grant the role twice.
    assert (await login(client, 900000001)).status_code == 200
    assert await db.scalar(select(func.count()).select_from(UserRole).where(UserRole.user_id == user.id)) == 1


async def test_admin_login_link_flow(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")

    raw, expires_at = await create_admin_login_link(db, admin)
    assert expires_at > datetime.now(UTC)
    stored = await db.scalar(select(LoginToken.token_hash))
    assert stored != raw  # only a hash is stored

    response = await client.post("/api/v1/auth/admin/exchange", json={"token": raw})
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "admin"

    # One-time use.
    reused = await client.post("/api/v1/auth/admin/exchange", json={"token": raw})
    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "LOGIN_LINK_INVALID"


async def test_expired_admin_login_link_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    raw, _ = await create_admin_login_link(db, admin)
    token = await db.scalar(select(LoginToken))
    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    assert (await client.post("/api/v1/auth/admin/exchange", json={"token": raw})).status_code == 401


async def test_login_link_only_for_admins(db: AsyncSession) -> None:
    from app.services.auth import NotAdminError

    member = await create_user(db)
    await db.commit()
    with pytest.raises(NotAdminError):
        await create_admin_login_link(db, member)


async def test_admin_token_still_requires_admin_role(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """An admin-scoped token is useless once the admin role is removed (checked on every request)."""
    from app.api.deps import get_current_admin  # noqa: F401 - documents the dependency under test

    admin = await create_user(db)
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    headers = admin_headers(admin)
    await db.execute(UserRole.__table__.delete().where(UserRole.user_id == admin.id))
    await db.commit()
    response = await client.get("/api/v1/admin/me", headers=headers)
    assert response.status_code == 403


# ---------------------------------------------------------------------------- rate limiting


async def test_login_is_rate_limited(client: httpx.AsyncClient) -> None:
    statuses = []
    for _ in range(25):
        response = await client.post("/api/v1/auth/telegram", json={"init_data": "hash=bad&user=x"})
        statuses.append(response.status_code)
    assert statuses[:20] == [401] * 20
    assert statuses[-1] == 429
    last = response
    assert last.json()["error"]["code"] == "RATE_LIMITED"
    assert int(last.headers["Retry-After"]) > 0
