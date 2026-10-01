"""Phase 19: rewards and promo codes — encrypted storage, masked for admins, revealed only to
the recipient, one code per member, audited assignments."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.exceptions import InvalidTag
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Notification, RewardCode, User, UserReward
from app.models.enums import NotificationType, RewardCodeStatus, UserStatus
from app.security.crypto import decrypt_secret, encrypt_secret
from app.security.permissions import Perm
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


async def _reward(client: httpx.AsyncClient, admin: User, **fields: Any) -> dict[str, Any]:
    body = {"title": "Kitob do'koniga 20% chegirma", "type": "PARTNER_DISCOUNT", "value": "20%", **fields}
    response = await client.post("/api/v1/admin/rewards", json=body, headers=admin_headers(admin))
    assert response.status_code == 201, response.text
    return response.json()


async def _assign(client: httpx.AsyncClient, admin: User, reward_id: str, member: User, **extra: Any) -> httpx.Response:
    return await client.post(
        f"/api/v1/admin/rewards/{reward_id}/assign",
        json={"user_id": str(member.id), "note": "Oy yetakchisi", **extra},
        headers=admin_headers(admin),
    )


def test_secret_encryption_roundtrip_and_tamper_detection() -> None:
    token = encrypt_secret("reward-code", "PROMO-2026-XYZ")
    assert "PROMO" not in token
    assert decrypt_secret("reward-code", token) == "PROMO-2026-XYZ"
    assert encrypt_secret("reward-code", "PROMO-2026-XYZ") != token  # random nonce
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises((InvalidTag, ValueError)):
        decrypt_secret("reward-code", tampered)
    with pytest.raises(InvalidTag):
        decrypt_secret("other-purpose", token)


async def test_rewards_require_permission(client: httpx.AsyncClient, db: AsyncSession) -> None:
    viewer = await _admin(db, Perm.USER_VIEW)
    member = await create_user(db)
    await db.commit()
    assert (await client.get("/api/v1/admin/rewards", headers=admin_headers(viewer))).status_code == 403
    assert (await client.get("/api/v1/admin/rewards", headers=member_headers(member))).status_code == 403


async def test_codes_are_encrypted_masked_and_deduplicated(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.REWARD_MANAGE)
    reward = await _reward(client, admin)
    added = await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes",
        json={"codes": ["KITOB-AAA111", " KITOB-BBB222 ", "KITOB-AAA111", ""]},
        headers=admin_headers(admin),
    )
    assert added.json() == {"added": 2, "duplicates": 0}
    again = await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes", json={"codes": ["KITOB-AAA111"]}, headers=admin_headers(admin)
    )
    assert again.json() == {"added": 0, "duplicates": 1}

    stored = list(await db.scalars(select(RewardCode.code_encrypted)))
    assert all("KITOB" not in value for value in stored)
    listing = await client.get(f"/api/v1/admin/rewards/{reward['id']}/codes", headers=admin_headers(admin))
    masks = [row["masked"] for row in listing.json()]
    assert masks == ["KI••••••••11", "KI••••••••22"]
    assert "KITOB-AAA111" not in listing.text
    summary = (await client.get("/api/v1/admin/rewards", headers=admin_headers(admin))).json()[0]
    assert (summary["codes_total"], summary["codes_available"], summary["recipients"]) == (2, 2, 0)


async def test_assignment_reveal_and_redeem(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.REWARD_MANAGE)
    member, other = await create_user(db), await create_user(db)
    await db.commit()
    reward = await _reward(client, admin)
    soon_expired = datetime.now(UTC) - timedelta(days=1)
    await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes",
        json={"codes": ["OLD-CODE-1"], "expires_at": soon_expired.isoformat()},
        headers=admin_headers(admin),
    )
    await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes", json={"codes": ["FRESH-CODE-2"]}, headers=admin_headers(admin)
    )

    assigned = await _assign(client, admin, reward["id"], member)
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["has_code"] is True
    assert assigned.json()["status"] == "ASSIGNED"
    duplicate = await _assign(client, admin, reward["id"], member)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALREADY_ASSIGNED"
    # The only remaining code is expired, so there is nothing left to give.
    empty = await _assign(client, admin, reward["id"], other)
    assert empty.json()["error"]["code"] == "NO_CODES_LEFT"

    note = await db.scalar(select(Notification).where(Notification.type == NotificationType.REWARD))
    assert "chegirma" in note.text and "FRESH" not in note.text  # the code never travels in a message

    mine = (await client.get("/api/v1/me/rewards", headers=member_headers(member))).json()
    assert len(mine) == 1 and mine[0]["has_code"] is True
    assert "FRESH-CODE-2" not in str(mine)
    user_reward_id = mine[0]["id"]
    stolen = await client.post(f"/api/v1/me/rewards/{user_reward_id}/code", headers=member_headers(other))
    assert stolen.status_code == 404
    revealed = await client.post(f"/api/v1/me/rewards/{user_reward_id}/code", headers=member_headers(member))
    assert revealed.json()["code"] == "FRESH-CODE-2"
    recipients = await client.get(f"/api/v1/admin/rewards/{reward['id']}/recipients", headers=admin_headers(admin))
    assert recipients.json()[0]["status"] == "DELIVERED"

    redeemed = await client.post(f"/api/v1/me/rewards/{user_reward_id}/redeemed", headers=member_headers(member))
    assert redeemed.json()["status"] == "REDEEMED"
    code = await db.scalar(select(RewardCode).where(RewardCode.status == RewardCodeStatus.REDEEMED))
    assert code is not None
    audit = await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "REWARD_ASSIGN"))
    assert audit == 1


async def test_revoked_reward_burns_its_code(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.REWARD_MANAGE)
    first, second = await create_user(db), await create_user(db)
    await db.commit()
    reward = await _reward(client, admin)
    await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes", json={"codes": ["ONLY-ONE"]}, headers=admin_headers(admin)
    )
    assignment = (await _assign(client, admin, reward["id"], first)).json()
    revoked = await client.post(
        f"/api/v1/admin/user-rewards/{assignment['id']}/status",
        json={"status": "REVOKED", "note": "Xato berilgan"},
        headers=admin_headers(admin),
    )
    assert revoked.json()["status"] == "REVOKED"
    assert (await client.get("/api/v1/me/rewards", headers=member_headers(first))).json() == []
    # The member may have seen the code, so it is never given to someone else.
    assert (await _assign(client, admin, reward["id"], second)).json()["error"]["code"] == "NO_CODES_LEFT"
    back = await client.post(
        f"/api/v1/admin/user-rewards/{assignment['id']}/status",
        json={"status": "DELIVERED"},
        headers=admin_headers(admin),
    )
    assert back.status_code == 409


async def test_reward_without_codes_and_idempotency(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.REWARD_MANAGE)
    member = await create_user(db)
    blocked = await create_user(db, status=UserStatus.BLOCKED)
    await db.commit()
    reward = await _reward(client, admin, title="«O'tkan kunlar» kitobi", type="BOOK", value=None)
    key = f"monthly-top:{uuid.uuid4()}"
    first = await _assign(client, admin, reward["id"], member, idempotency_key=key)
    repeat = await _assign(client, admin, reward["id"], member, idempotency_key=key)
    assert first.status_code == 201 and repeat.status_code == 201
    assert first.json()["id"] == repeat.json()["id"]
    assert first.json()["has_code"] is False
    no_code = await client.post(f"/api/v1/me/rewards/{first.json()['id']}/code", headers=member_headers(member))
    assert no_code.status_code == 404
    assert (await _assign(client, admin, reward["id"], blocked)).status_code == 400

    await client.patch(
        f"/api/v1/admin/rewards/{reward['id']}", json={"status": "INACTIVE"}, headers=admin_headers(admin)
    )
    other = await create_user(db)
    await db.commit()
    assert (await _assign(client, admin, reward["id"], other)).json()["error"]["code"] == "REWARD_NOT_ACTIVE"


async def test_parallel_assignments_give_one_reward(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.REWARD_MANAGE)
    member = await create_user(db)
    await db.commit()
    reward = await _reward(client, admin)
    await client.post(
        f"/api/v1/admin/rewards/{reward['id']}/codes",
        json={"codes": [f"CODE-{i}" for i in range(5)]},
        headers=admin_headers(admin),
    )
    responses = await asyncio.gather(*[_assign(client, admin, reward["id"], member) for _ in range(5)])
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]
    assert await db.scalar(select(func.count()).select_from(UserReward)) == 1
    assert (
        await db.scalar(
            select(func.count()).select_from(RewardCode).where(RewardCode.status == RewardCodeStatus.ASSIGNED)
        )
        == 1
    )
