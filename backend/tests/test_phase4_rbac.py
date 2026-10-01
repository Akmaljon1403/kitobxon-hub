"""Phase 4: role-based access control, admin management and the audit log."""

from __future__ import annotations

import re
import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User
from app.security.permissions import Perm
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _super_admin(db: AsyncSession) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "SUPER_ADMIN")
    return user


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    if permissions:
        await grant_permissions(db, user, *permissions)
    return user


# ---------------------------------------------------------------------------- blanket checks


def _admin_operations(app: FastAPI) -> list[tuple[str, str]]:
    operations = []
    for path, methods in app.openapi()["paths"].items():
        if not path.startswith("/api/v1/admin"):
            continue
        concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        operations.extend((method.upper(), concrete) for method in methods)
    return operations


async def test_every_admin_route_requires_authentication(app: FastAPI, client: httpx.AsyncClient) -> None:
    operations = _admin_operations(app)
    assert len(operations) >= 10
    for method, path in operations:
        response = await client.request(method, path, json={})
        assert response.status_code == 401, f"{method} {path} returned {response.status_code}"


async def test_every_admin_route_rejects_member_tokens(
    app: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    member = await create_user(db)
    await db.commit()
    headers = member_headers(member)
    for method, path in _admin_operations(app):
        response = await client.request(method, path, json={}, headers=headers)
        assert response.status_code == 403, f"{method} {path} returned {response.status_code}"


async def test_admin_with_member_scoped_token_is_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    response = await client.get("/api/v1/admin/me", headers=member_headers(admin))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ADMIN_SESSION_REQUIRED"


# ---------------------------------------------------------------------------- permission checks


async def test_admin_without_permission_gets_403(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    response = await client.get("/api/v1/admin/audit-logs", headers=admin_headers(admin))
    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "PERMISSION_DENIED"
    assert body["details"] == {"required": ["AUDIT_LOG_VIEW"]}


async def test_direct_permission_grants_access(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.AUDIT_LOG_VIEW)
    response = await client.get("/api/v1/admin/audit-logs", headers=admin_headers(admin))
    assert response.status_code == 200


async def test_super_admin_has_every_permission(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    response = await client.get("/api/v1/admin/me", headers=admin_headers(owner))
    assert response.status_code == 200
    body = response.json()
    assert body["is_super_admin"] is True
    assert set(body["permissions"]) == {perm.value for perm in Perm}


async def test_admin_cannot_manage_admins(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *Perm)  # even with every grantable permission
    member = await create_user(db)
    await db.commit()
    response = await client.post("/api/v1/admin/admins", json={"user_id": str(member.id)}, headers=admin_headers(admin))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SUPER_ADMIN_REQUIRED"


# ---------------------------------------------------------------------------- admin lifecycle


async def test_appoint_and_configure_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    member = await create_user(db)
    await db.commit()
    headers = admin_headers(owner)

    created = await client.post(
        "/api/v1/admin/admins",
        json={"user_id": str(member.id), "permissions": ["EVENT_VIEW", "EVENT_CREATE"]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["roles"] == ["ADMIN"]
    assert created.json()["effective_permissions"] == ["EVENT_CREATE", "EVENT_VIEW"]

    again = await client.post("/api/v1/admin/admins", json={"user_id": str(member.id)}, headers=headers)
    assert again.status_code == 409

    updated = await client.put(
        f"/api/v1/admin/admins/{member.id}/permissions",
        json={"permissions": ["ATTENDANCE_VIEW", "ATTENDANCE_MANAGE"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["direct_permissions"] == ["ATTENDANCE_MANAGE", "ATTENDANCE_VIEW"]

    listing = await client.get("/api/v1/admin/admins", headers=headers)
    assert {item["user_id"] for item in listing.json()} == {str(owner.id), str(member.id)}

    audit = await db.execute(
        select(AuditLog.action, AuditLog.before, AuditLog.after, AuditLog.actor_user_id)
        .where(AuditLog.entity_id == str(member.id))
        .order_by(AuditLog.created_at)
    )
    rows = audit.all()
    assert [row.action for row in rows] == ["ADMIN_CREATE", "ADMIN_PERMISSIONS_CHANGE"]
    assert rows[1].before == {"permissions": ["EVENT_CREATE", "EVENT_VIEW"]}
    assert rows[1].after == {"permissions": ["ATTENDANCE_MANAGE", "ATTENDANCE_VIEW"]}
    assert all(row.actor_user_id == owner.id for row in rows)


async def test_unknown_permission_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    member = await create_user(db)
    await db.commit()
    response = await client.post(
        "/api/v1/admin/admins",
        json={"user_id": str(member.id), "permissions": ["DO_ANYTHING"]},
        headers=admin_headers(owner),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_PERMISSION"


async def test_dismissed_admin_loses_access_immediately(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    admin = await _admin(db, Perm.AUDIT_LOG_VIEW)
    admin_session = admin_headers(admin)
    assert (await client.get("/api/v1/admin/me", headers=admin_session)).status_code == 200

    no_reason = await client.post(f"/api/v1/admin/admins/{admin.id}/dismiss", json={}, headers=admin_headers(owner))
    assert no_reason.status_code == 422

    response = await client.post(
        f"/api/v1/admin/admins/{admin.id}/dismiss",
        json={"reason": "Klubdagi vazifasi tugadi"},
        headers=admin_headers(owner),
    )
    assert response.status_code == 204
    assert (await client.get("/api/v1/admin/me", headers=admin_session)).status_code == 401

    entry = await db.scalar(select(AuditLog).where(AuditLog.action == "ADMIN_DEACTIVATE"))
    assert entry is not None
    assert entry.reason == "Klubdagi vazifasi tugadi"
    assert entry.before == {"roles": ["ADMIN"], "permissions": ["AUDIT_LOG_VIEW"]}


async def test_last_super_admin_cannot_be_removed(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    response = await client.post(
        f"/api/v1/admin/admins/{owner.id}/dismiss",
        json={"reason": "Tasodifan o'zimni o'chirmoqchiman"},
        headers=admin_headers(owner),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LAST_SUPER_ADMIN"

    demote = await client.put(
        f"/api/v1/admin/admins/{owner.id}/roles", json={"roles": ["ADMIN"]}, headers=admin_headers(owner)
    )
    assert demote.status_code == 403


async def test_second_super_admin_allows_demotion(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    deputy = await _super_admin(db)
    response = await client.put(
        f"/api/v1/admin/admins/{deputy.id}/roles", json={"roles": ["ADMIN"]}, headers=admin_headers(owner)
    )
    assert response.status_code == 200
    assert response.json()["roles"] == ["ADMIN"]


# ---------------------------------------------------------------------------- custom roles


async def test_custom_role_grants_permissions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    admin = await _admin(db)
    headers = admin_headers(owner)

    role = await client.post(
        "/api/v1/admin/roles",
        json={"code": "AUDITOR", "name": "Auditor", "permissions": ["AUDIT_LOG_VIEW", "ANALYTICS_VIEW"]},
        headers=headers,
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["id"]

    assert (await client.get("/api/v1/admin/audit-logs", headers=admin_headers(admin))).status_code == 403
    assigned = await client.put(
        f"/api/v1/admin/admins/{admin.id}/roles", json={"roles": ["ADMIN", "AUDITOR"]}, headers=headers
    )
    assert assigned.status_code == 200
    assert (await client.get("/api/v1/admin/audit-logs", headers=admin_headers(admin))).status_code == 200

    renamed = await client.patch(f"/api/v1/admin/roles/{role_id}", json={"permissions": []}, headers=headers)
    assert renamed.json()["permissions"] == []
    assert (await client.get("/api/v1/admin/audit-logs", headers=admin_headers(admin))).status_code == 403

    assert (await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)).status_code == 204


async def test_system_roles_are_protected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    headers = admin_headers(owner)
    roles = (await client.get("/api/v1/admin/roles", headers=headers)).json()
    super_role = next(role for role in roles if role["code"] == "SUPER_ADMIN")
    response = await client.delete(f"/api/v1/admin/roles/{super_role['id']}", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SYSTEM_ROLE"


@pytest.mark.parametrize("bad_code", ["auditor", "A", "AUDITOR-1", "X" * 40])
async def test_role_code_validation(client: httpx.AsyncClient, db: AsyncSession, bad_code: str) -> None:
    owner = await _super_admin(db)
    response = await client.post(
        "/api/v1/admin/roles", json={"code": bad_code, "name": "Test"}, headers=admin_headers(owner)
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------- audit log listing


async def test_audit_log_filters_and_pagination(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _super_admin(db)
    headers = admin_headers(owner)
    for _ in range(3):
        member = await create_user(db)
        await db.commit()
        await client.post("/api/v1/admin/admins", json={"user_id": str(member.id)}, headers=headers)

    page = await client.get("/api/v1/admin/audit-logs?action=ADMIN_CREATE&limit=2", headers=headers)
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["items"][0]["actor_name"] == f"{owner.first_name} {owner.last_name}"

    second = await client.get("/api/v1/admin/audit-logs?action=ADMIN_CREATE&limit=2&offset=2", headers=headers)
    assert len(second.json()["items"]) == 1
