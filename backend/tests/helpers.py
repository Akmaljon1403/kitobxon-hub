"""Test helpers: forge *correctly signed* Telegram initData and obtain tokens."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Role, User, UserPermission, UserRole
from app.security.permissions import Perm
from app.security.telegram import sign_init_data
from app.security.tokens import create_access_token


def make_init_data(
    telegram_id: int,
    *,
    first_name: str = "Akmal",
    auth_date: int | None = None,
    bot_token: str | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    user = {"id": telegram_id, "first_name": first_name, "username": "akmal_reader", "language_code": "uz"}
    fields = {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        **(extra or {}),
    }
    token = bot_token or get_settings().bot_token.get_secret_value()
    fields["hash"] = sign_init_data(fields, token)
    return urlencode(fields)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def member_headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.token_version, "member")
    return auth_header(token)


def admin_headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.id, user.token_version, "admin")
    return auth_header(token)


async def grant_role(session: AsyncSession, user: User, role_code: str) -> None:
    role = (await session.execute(Role.__table__.select().where(Role.code == role_code))).one()
    session.add(UserRole(user_id=user.id, role_id=role.id))
    await session.commit()


async def grant_permissions(session: AsyncSession, user: User, *permissions: Perm) -> None:
    for permission in permissions:
        session.add(UserPermission(user_id=user.id, permission_code=permission.value))
    await session.commit()


async def login(client: httpx.AsyncClient, telegram_id: int, **kwargs: Any) -> httpx.Response:
    scope = kwargs.pop("scope", "member")
    return await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data(telegram_id, **kwargs), "scope": scope}
    )
