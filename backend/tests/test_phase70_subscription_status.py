"""Round N6: the panel can see whether the «majburiy obuna» gate is actually enforceable.

The gate was already enforced in the bot and the Mini App, but when the bot is not an administrator
of the required channel it cannot check membership and silently lets everyone in. This endpoint makes
that state visible so the owner knows to make the bot an admin.
"""

from __future__ import annotations

import itertools

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import settings as settings_service
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(4_700_000)


async def test_status_reports_not_enforceable_without_bot_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await settings_service.update_setting(db, key="subscription.required", value=True, actor_id=boss.id)
    await settings_service.update_setting(db, key="subscription.channels", value="@fjstimutolaaxona", actor_id=boss.id)

    response = await client.get("/api/v1/admin/subscription/status", headers=admin_headers(boss))
    assert response.status_code == 200
    body = response.json()
    assert body["required"] is True
    assert body["channels"] and body["channels"][0]["chat_id"] == "@fjstimutolaaxona"
    # no bot runtime in tests → the bot cannot verify the channel → the gate is not enforceable
    assert body["channels"][0]["ok"] is False
    assert body["enforceable"] is False


async def test_status_reports_disabled(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await settings_service.update_setting(db, key="subscription.required", value=False, actor_id=boss.id)

    response = await client.get("/api/v1/admin/subscription/status", headers=admin_headers(boss))
    assert response.status_code == 200 and response.json()["required"] is False
