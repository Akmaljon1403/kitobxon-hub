"""Phases 10-11: events, registrations and QR / code attendance."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceToken,
    AuditLog,
    ScoreTransaction,
    SystemSetting,
    User,
)
from app.models.enums import AttendanceSessionStatus, EventStatus, ScoreCategory
from app.security.permissions import Perm
from app.services import attendance as attendance_service
from tests.bot_helpers import BotHarness
from tests.factories import create_event, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

ATTENDANCE_PERMS = (Perm.EVENT_VIEW, Perm.EVENT_CREATE, Perm.EVENT_EDIT, Perm.ATTENDANCE_VIEW, Perm.ATTENDANCE_MANAGE)


async def _admin(db: AsyncSession, *permissions: Perm) -> User:
    user = await create_user(db)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


async def _open_event(client: httpx.AsyncClient, db: AsyncSession, **event_fields) -> tuple[str, User, dict]:
    """A published event with attendance open; returns (event id, admin, current display token)."""
    admin = await _admin(db, *ATTENDANCE_PERMS)
    event = await create_event(db, **event_fields)
    await db.commit()
    event_id = str(event.id)
    opened = await client.post(
        f"/api/v1/admin/events/{event_id}/attendance/open", json={}, headers=admin_headers(admin)
    )
    assert opened.status_code == 204, opened.text
    token = await client.get(f"/api/v1/admin/events/{event_id}/attendance/token", headers=admin_headers(admin))
    assert token.status_code == 200, token.text
    return event_id, admin, token.json()


async def _points(db: AsyncSession, user: User) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(ScoreTransaction.user_id == user.id)
        )
    )


# ---------------------------------------------------------------------------- events


async def test_admin_creates_event_with_default_attendance_window(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, Perm.EVENT_VIEW, Perm.EVENT_CREATE)
    starts = datetime(2026, 10, 15, 10, 0, tzinfo=UTC)
    response = await client.post(
        "/api/v1/admin/events",
        json={
            "title": "O'tkan kunlar muhokamasi",
            "location": "Kutubxona",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(minutes=90)).isoformat(),
        },
        headers=admin_headers(admin),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["attendance_points"] == 30  # default from settings
    assert body["attendance_opens_at"].startswith("2026-10-15T09:50")
    assert body["attendance_closes_at"].startswith("2026-10-15T10:20")

    bad = await client.post(
        "/api/v1/admin/events",
        json={"title": "Xato", "starts_at": starts.isoformat(), "ends_at": starts.isoformat()},
        headers=admin_headers(admin),
    )
    assert bad.status_code == 422


async def test_member_sees_only_published_events(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    future = datetime.now(UTC) + timedelta(days=2)
    await create_event(db, title="Qoralama", status=EventStatus.DRAFT, starts_at=future)
    await create_event(db, title="Ochiq", starts_at=future)
    await db.commit()
    listing = await client.get("/api/v1/events", headers=member_headers(member))
    assert [item["title"] for item in listing.json()["items"]] == ["Ochiq"]


async def test_registration_and_capacity(client: httpx.AsyncClient, db: AsyncSession) -> None:
    first, second = await create_user(db), await create_user(db)
    event = await create_event(db, capacity=1, starts_at=datetime.now(UTC) + timedelta(days=1))
    await db.commit()
    url = f"/api/v1/events/{event.id}/register"

    ok = await client.post(url, headers=member_headers(first))
    assert ok.status_code == 200 and ok.json()["is_registered"] is True
    again = await client.post(url, headers=member_headers(first))  # idempotent
    assert again.json()["registered_count"] == 1
    full = await client.post(url, headers=member_headers(second))
    assert full.status_code == 409 and full.json()["error"]["code"] == "EVENT_FULL"

    assert (await client.delete(url, headers=member_headers(first))).status_code == 204
    assert (await client.post(url, headers=member_headers(second))).status_code == 200


async def test_cannot_register_for_cancelled_event(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    event = await create_event(db, status=EventStatus.CANCELLED, starts_at=datetime.now(UTC) + timedelta(days=1))
    await db.commit()
    response = await client.post(f"/api/v1/events/{event.id}/register", headers=member_headers(member))
    assert response.json()["error"]["code"] == "REGISTRATION_CLOSED"


# ---------------------------------------------------------------------------- tokens


def test_tokens_rotate_and_are_unpredictable() -> None:
    import uuid

    session_id = uuid.uuid4()
    assert attendance_service.derive_token(session_id, 100) == attendance_service.derive_token(session_id, 100)
    assert attendance_service.derive_token(session_id, 100) != attendance_service.derive_token(session_id, 101)
    assert attendance_service.derive_token(session_id, 100) != attendance_service.derive_token(uuid.uuid4(), 100)
    code = attendance_service.derive_code(session_id, 100)
    assert len(code) == 6 and set(code) <= set(attendance_service.CODE_ALPHABET)
    assert len(attendance_service.derive_token(session_id, 100)) >= 22  # 128 bits


async def test_qr_payload_is_bot_deep_link(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    assert token["qr_payload"] == f"https://t.me/kitobxon_test_bot?start=att_{token['token']}"
    # Only hashes are stored.
    stored = await db.scalar(select(AttendanceToken))
    assert stored.token_hash != token["token"] and stored.code_hash != token["code"]


# ---------------------------------------------------------------------------- check-in (critical cases)


async def test_qr_check_in_awards_points(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    response = await client.post(
        "/api/v1/attendance/verify", json={"token": token["qr_payload"]}, headers=member_headers(member)
    )
    assert response.status_code == 200, response.text
    assert response.json()["points"] == 30
    assert await _points(db, member) == 30
    detail = await client.get(f"/api/v1/events/{event_id}", headers=member_headers(member))
    assert detail.json()["my_attendance"] == "VERIFIED"


async def test_code_check_in_is_case_insensitive(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db, attendance_points=45)
    member = await create_user(db)
    await db.commit()
    response = await client.post(
        "/api/v1/attendance/verify", json={"code": token["code"].lower()}, headers=member_headers(member)
    )
    assert response.status_code == 200, response.text
    assert response.json()["points"] == 45
    assert await db.scalar(select(AttendanceRecord.method)) == "CODE"


async def test_unauthenticated_check_in_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    response = await client.post("/api/v1/attendance/verify", json={"token": token["token"]})
    assert response.status_code == 401


@pytest.mark.parametrize("payload", [{"token": "att_forgedtokenforgedtoken"}, {"code": "ZZZZZZ"}, {}])
async def test_invalid_token_rejected(client: httpx.AsyncClient, db: AsyncSession, payload: dict) -> None:
    await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    response = await client.post("/api/v1/attendance/verify", json=payload, headers=member_headers(member))
    assert response.status_code == 400
    assert response.json()["error"]["code"] in {"ATTENDANCE_TOKEN_INVALID", "ATTENDANCE_TOKEN_REQUIRED"}
    assert await db.scalar(select(func.count()).select_from(AttendanceRecord)) == 0


async def test_expired_qr_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.execute(update(AttendanceToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    await db.commit()
    response = await client.post(
        "/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member)
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ATTENDANCE_EXPIRED"
    assert await _points(db, member) == 0


async def test_wrong_event_qr_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    other_event = await create_event(db)
    member = await create_user(db)
    await db.commit()
    response = await client.post(
        "/api/v1/attendance/verify",
        json={"token": token["token"], "event_id": str(other_event.id)},
        headers=member_headers(member),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ATTENDANCE_WRONG_EVENT"


async def test_closed_session_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, admin, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    await client.post(f"/api/v1/admin/events/{event_id}/attendance/close", headers=admin_headers(admin))
    response = await client.post(
        "/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member)
    )
    assert response.json()["error"]["code"] == "ATTENDANCE_CLOSED"


async def test_session_past_closing_time_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    member = await create_user(db)
    now = datetime.now(UTC)
    await db.execute(
        update(AttendanceSession).values(opened_at=now - timedelta(minutes=10), closes_at=now - timedelta(seconds=1))
    )
    await db.commit()
    response = await client.post(
        "/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member)
    )
    assert response.json()["error"]["code"] == "ATTENDANCE_CLOSED"


async def test_duplicate_check_in_rejected(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    headers = member_headers(member)
    assert (
        await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=headers)
    ).status_code == 200
    second = await client.post("/api/v1/attendance/verify", json={"code": token["code"]}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_CHECKED_IN"
    assert await _points(db, member) == 30


async def test_simultaneous_check_ins_create_one_record(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    headers = member_headers(member)
    responses = await asyncio.gather(
        *(client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=headers) for _ in range(6))
    )
    statuses = sorted(response.status_code for response in responses)
    assert statuses.count(200) == 1 and set(statuses) <= {200, 409}
    assert await db.scalar(select(func.count()).select_from(AttendanceRecord)) == 1
    assert await db.scalar(select(func.count()).select_from(ScoreTransaction)) == 1


async def test_registration_can_be_required(client: httpx.AsyncClient, db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "attendance.require_registration")
    setting.value = True
    await db.commit()
    event_id, _, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    headers = member_headers(member)
    refused = await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=headers)
    assert refused.json()["error"]["code"] == "REGISTRATION_REQUIRED"
    await client.post(f"/api/v1/events/{event_id}/register", headers=headers)
    assert (
        await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=headers)
    ).status_code == 200


async def test_check_in_rate_limited(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    statuses = [
        (
            await client.post("/api/v1/attendance/verify", json={"code": "ZZZZZZ"}, headers=member_headers(member))
        ).status_code
        for _ in range(12)
    ]
    assert statuses[:10] == [400] * 10
    assert statuses[-1] == 429


async def test_attendance_screen_requires_permission(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, _, _ = await _open_event(client, db)
    viewer = await _admin(db, Perm.EVENT_VIEW, Perm.ATTENDANCE_VIEW)
    response = await client.get(f"/api/v1/admin/events/{event_id}/attendance/token", headers=admin_headers(viewer))
    assert response.status_code == 403


# ---------------------------------------------------------------------------- corrections


async def test_revoke_and_restore_with_audit(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, admin, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member))
    record_id = await db.scalar(select(AttendanceRecord.id))

    no_reason = await client.patch(
        f"/api/v1/admin/attendance/{record_id}", json={"status": "REVOKED"}, headers=admin_headers(admin)
    )
    assert no_reason.status_code == 422

    revoked = await client.patch(
        f"/api/v1/admin/attendance/{record_id}",
        json={"status": "REVOKED", "reason": "Tadbirda yo'q edi, QR kod do'stidan olingan"},
        headers=admin_headers(admin),
    )
    assert revoked.status_code == 204
    assert await _points(db, member) == 0
    categories = list(await db.scalars(select(ScoreTransaction.category).order_by(ScoreTransaction.created_at)))
    assert categories == [ScoreCategory.ATTENDANCE, ScoreCategory.REVERSAL]

    restored = await client.patch(
        f"/api/v1/admin/attendance/{record_id}",
        json={"status": "VERIFIED", "reason": "Qayta tekshirildi, tadbirda bo'lgan"},
        headers=admin_headers(admin),
    )
    assert restored.status_code == 204
    assert await _points(db, member) == 30
    audit = list(await db.scalars(select(AuditLog.reason).where(AuditLog.action == "ATTENDANCE_CORRECTION")))
    assert len(audit) == 2

    overview = await client.get(f"/api/v1/admin/events/{event_id}/attendance", headers=admin_headers(admin))
    assert overview.json()["attended_count"] == 1


async def test_suspicious_keeps_points(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, admin, token = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member))
    record_id = await db.scalar(select(AttendanceRecord.id))
    await client.patch(
        f"/api/v1/admin/attendance/{record_id}",
        json={"status": "SUSPICIOUS", "reason": "Ekranda ko'rinmadi, tekshiriladi"},
        headers=admin_headers(admin),
    )
    assert await _points(db, member) == 30


async def test_manual_check_in(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, admin, _ = await _open_event(client, db)
    member = await create_user(db)
    await db.commit()
    body = {"user_id": str(member.id), "note": "Telefoni o'chib qolgan, shaxsan ko'rildi"}
    added = await client.post(
        f"/api/v1/admin/events/{event_id}/attendance/manual", json=body, headers=admin_headers(admin)
    )
    assert added.status_code == 204
    # An ordinary admin's addition waits for the super admin: no points yet.
    assert await _points(db, member) == 0
    again = await client.post(
        f"/api/v1/admin/events/{event_id}/attendance/manual", json=body, headers=admin_headers(admin)
    )
    assert again.status_code == 409
    boss = await create_user(db)
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    overview = (await client.get(f"/api/v1/admin/events/{event_id}/attendance", headers=admin_headers(boss))).json()
    record = overview["records"][0]
    assert record["status"] == "PENDING" and overview["can_approve"] is True and overview["attended_count"] == 0
    refused = await client.post(f"/api/v1/admin/attendance/{record['id']}/approve", headers=admin_headers(admin))
    assert refused.status_code == 403
    approved = await client.post(f"/api/v1/admin/attendance/{record['id']}/approve", headers=admin_headers(boss))
    assert approved.status_code == 204
    assert await _points(db, member) == 30
    assert (
        await db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.action == "ATTENDANCE_MANUAL_APPROVE")
        )
        == 1
    )
    # The super admin's own addition counts at once.
    other = await create_user(db)
    await db.commit()
    direct = await client.post(
        f"/api/v1/admin/events/{event_id}/attendance/manual",
        json={"user_id": str(other.id), "note": "Shaxsan ko'rdim, telefoni yo'q"},
        headers=admin_headers(boss),
    )
    assert direct.status_code == 204 and await _points(db, other) == 30


async def test_attendance_csv_export(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, admin, token = await _open_event(client, db, title="Kecha va kunduz")
    member = await create_user(db, first_name="Dilnoza", last_name="Karimova")
    await db.commit()
    await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member))
    response = await client.get(f"/api/v1/admin/events/{event_id}/attendance.csv", headers=admin_headers(admin))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    assert "Karimova;Dilnoza" in text and "QR kod;Tasdiqlangan" in text


async def test_event_with_attendance_cannot_be_deleted(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, _, token = await _open_event(client, db)
    member = await create_user(db)
    deleter = await _admin(db, Perm.EVENT_DELETE)
    await client.post("/api/v1/attendance/verify", json={"token": token["token"]}, headers=member_headers(member))
    response = await client.delete(f"/api/v1/admin/events/{event_id}", headers=admin_headers(deleter))
    assert response.status_code == 409


async def test_reopening_closes_previous_session(client: httpx.AsyncClient, db: AsyncSession) -> None:
    event_id, admin, _ = await _open_event(client, db)
    await client.post(
        f"/api/v1/admin/events/{event_id}/attendance/open", json={"minutes": 5}, headers=admin_headers(admin)
    )
    statuses = list(await db.scalars(select(AttendanceSession.status)))
    assert sorted(statuses) == [AttendanceSessionStatus.CLOSED, AttendanceSessionStatus.OPEN]


# ---------------------------------------------------------------------------- bot deep link


async def test_bot_deep_link_check_in(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db, title="Ufq muhokamasi")
    await create_user(db, telegram_id=6100)
    await db.commit()
    harness = BotHarness(6100)
    await harness.send(f"/start att_{token['token']}")
    assert "Davomatingiz qayd etildi" in harness.last_text()
    assert "Ufq muhokamasi" in harness.last_text()
    await harness.send(f"/start att_{token['token']}")
    assert "allaqachon qayd etilgansiz" in harness.last_text()


async def test_bot_deep_link_for_unregistered_person(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, token = await _open_event(client, db)
    harness = BotHarness(6101)
    await harness.send(f"/start att_{token['token']}")
    assert "avval ro'yxatdan o'ting" in harness.all_text()
    assert await db.scalar(select(func.count()).select_from(AttendanceRecord)) == 0


async def test_rsvp_decline_is_recorded_and_switchable(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    event = await create_event(db, starts_at=datetime.now(UTC) + timedelta(days=1))
    await db.commit()
    reg = f"/api/v1/events/{event.id}/register"
    dec = f"/api/v1/events/{event.id}/decline"
    headers = member_headers(member)

    # «Bu safar bora olmayman» — a recorded answer, not counted as coming
    declined = await client.post(dec, headers=headers)
    assert declined.status_code == 200
    body = declined.json()
    assert body["my_answer"] == "declined" and body["is_registered"] is False and body["registered_count"] == 0

    # switch to «Qatnashaman» — only the last answer counts
    coming = await client.post(reg, headers=headers)
    assert coming.json()["my_answer"] == "coming" and coming.json()["registered_count"] == 1

    # switch back to declined — the seat is freed again
    again = await client.post(dec, headers=headers)
    assert again.json()["my_answer"] == "declined" and again.json()["registered_count"] == 0

    # someone who never answered has no recorded answer
    other = await create_user(db)
    await db.commit()
    detail = await client.get(f"/api/v1/events/{event.id}", headers=member_headers(other))
    assert detail.json()["my_answer"] is None
