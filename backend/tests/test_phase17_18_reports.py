"""Phases 17-18: official event reports — database facts, number cross-check, AI or template
draft, approval, PDF, photos and versions."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AttendanceRecord, AuditLog, EventRegistration, TestAttempt, User
from app.models.enums import (
    AttemptStatus,
    AttendanceMethod,
    AttendanceStatus,
    BookStatus,
    RegistrationStatus,
)
from app.security.permissions import Perm
from app.services import report_ai
from app.services.storage import get_storage
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

REPORT_PERMS = (Perm.REPORT_VIEW, Perm.REPORT_CREATE, Perm.REPORT_APPROVE)


async def _admin(db: AsyncSession, *permissions: Perm, **fields: Any) -> User:
    user = await create_user(db, **fields)
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


async def _event_with_activity(db: AsyncSession, responsible: User) -> uuid.UUID:
    """3 registered members, 2 of them came, plus 1 walk-in; a book test with 2 participants."""
    book = await create_book(db, title="O'tkan kunlar", status=BookStatus.ACTIVE)
    event = await create_event(
        db, title="O'tkan kunlar — muhokama", book_id=book.id, responsible_admin_id=responsible.id
    )
    members = [await create_user(db) for _ in range(4)]
    for member in members[:3]:
        db.add(EventRegistration(event_id=event.id, user_id=member.id, status=RegistrationStatus.REGISTERED))
    for member in (members[0], members[1], members[3]):
        db.add(
            AttendanceRecord(
                event_id=event.id, user_id=member.id, method=AttendanceMethod.QR, status=AttendanceStatus.VERIFIED
            )
        )
    test = await create_test(db, book_id=book.id, title="O'tkan kunlar testi", max_score=20, passing_score=10)
    now = datetime.now(UTC)
    for member, score in ((members[0], 18), (members[1], 8)):
        db.add(
            TestAttempt(
                test_id=test.id,
                user_id=member.id,
                status=AttemptStatus.SUBMITTED,
                started_at=now - timedelta(minutes=10),
                deadline_at=now,
                submitted_at=now - timedelta(minutes=2),
                question_order=[],
                option_order={},
                score=score,
            )
        )
    await db.commit()
    return event.id


async def _create(client: httpx.AsyncClient, admin: User, event_id: uuid.UUID) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/reports", json={"event_id": str(event_id)}, headers=admin_headers(admin)
    )
    assert response.status_code == 201, response.text
    return response.json()


def _pdf_text(content: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


async def test_facts_come_from_the_database(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *REPORT_PERMS, first_name="Akmal", last_name="Bahodirov")
    event_id = await _event_with_activity(db, admin)
    report = await _create(client, admin, event_id)
    facts = report["facts"]
    assert facts["organization"] == "Farg'ona jamoat salomatligi tibbiyot instituti"
    assert facts["event"]["responsible"] == "Akmal Bahodirov"
    assert facts["event"]["book_title"] == "O'tkan kunlar"
    assert facts["attendance"] == {
        "registered": 3,
        "attended": 3,
        "attended_registered": 2,
        "walk_ins": 1,
        "rate_percent": 66.7,
        "suspicious": 0,
    }
    assert facts["tests"] == [
        {"title": "O'tkan kunlar testi", "participants": 2, "average_score": 13.0, "max_score": 20, "passed": 1}
    ]
    assert report["status"] == "DRAFT"
    assert report["version"] == 1
    assert report["ai_available"] is False


async def test_report_permissions(client: httpx.AsyncClient, db: AsyncSession) -> None:
    viewer = await _admin(db, Perm.REPORT_VIEW)
    creator = await _admin(db, Perm.REPORT_VIEW, Perm.REPORT_CREATE)
    event_id = await _event_with_activity(db, creator)
    body = {"event_id": str(event_id)}
    assert (await client.post("/api/v1/admin/reports", json=body, headers=admin_headers(viewer))).status_code == 403
    report = await _create(client, creator, event_id)
    await client.post(
        f"/api/v1/admin/reports/{report['id']}/generate", json={"use_ai": False}, headers=admin_headers(creator)
    )
    approve = await client.post(f"/api/v1/admin/reports/{report['id']}/approve", headers=admin_headers(creator))
    assert approve.status_code == 403
    assert (await client.get("/api/v1/admin/reports", headers=admin_headers(viewer))).json()["total"] == 1


async def test_template_draft_approval_and_official_pdf(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report = await _create(client, admin, event_id)
    report_id = report["id"]
    headers = admin_headers(admin)
    await client.patch(
        f"/api/v1/admin/reports/{report_id}",
        json={"objective": "Talabalarda mutolaa madaniyatini oshirish", "conclusion": "Tadbir samarali o'tdi."},
        headers=headers,
    )
    drafted = (
        await client.post(f"/api/v1/admin/reports/{report_id}/generate", json={"use_ai": False}, headers=headers)
    ).json()
    assert drafted["status"] == "REVIEW"
    assert "jami 3 nafar" in drafted["body_text"]
    assert "66.7 foiz" in drafted["body_text"]
    assert drafted["number_issues"] == []

    assert (await client.get(f"/api/v1/admin/reports/{report_id}/pdf", headers=headers)).status_code == 409
    approved = await client.post(f"/api/v1/admin/reports/{report_id}/approve", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "PDF_GENERATED"
    assert approved.json()["pdf_ready"] is True

    pdf = await client.get(f"/api/v1/admin/reports/{report_id}/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    text = _pdf_text(pdf.content)
    for expected in (
        "HISOBOT",
        "JAMOAT SALOMATLIGI",
        "Davomat statistikasi",
        "Test natijalari",
        "mutolaa madaniyatini",
    ):
        assert expected in text, expected
    assert "QORALAMA" not in text

    actions = set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_id == report_id)))
    assert {"REPORT_CREATE", "REPORT_TEMPLATE_DRAFT", "REPORT_APPROVE", "REPORT_PDF"} <= actions


async def test_unknown_numbers_block_approval(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report_id = (await _create(client, admin, event_id))["id"]
    headers = admin_headers(admin)
    body = "## Kirish\n\nTadbirda 45 nafar kitobxon qatnashdi, ulardan 3 nafari faol bo'ldi."
    edited = (
        await client.patch(f"/api/v1/admin/reports/{report_id}", json={"body_text": body}, headers=headers)
    ).json()
    assert edited["status"] == "REVIEW"
    assert edited["number_issues"] == ["45"]
    blocked = await client.post(f"/api/v1/admin/reports/{report_id}/approve", headers=headers)
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "REPORT_UNVERIFIED_NUMBERS"
    assert blocked.json()["error"]["details"] == {"numbers": ["45"]}
    # A number the admin typed into their own fields counts as confirmed by the admin.
    confirmed = await client.patch(
        f"/api/v1/admin/reports/{report_id}", json={"results": "Ko'rgazmaga 45 nafar mehmon keldi."}, headers=headers
    )
    assert confirmed.json()["number_issues"] == []


class _FakeMessages:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


def _fake_client(monkeypatch: pytest.MonkeyPatch, response: Any) -> _FakeMessages:
    messages = _FakeMessages(response)
    monkeypatch.setattr(report_ai, "_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=messages)))
    monkeypatch.setattr(get_settings(), "ai_api_key", "test-key")
    return messages


async def test_ai_draft_uses_only_facts_and_is_checked(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report_id = (await _create(client, admin, event_id))["id"]
    headers = admin_headers(admin)

    not_configured = await client.post(
        f"/api/v1/admin/reports/{report_id}/generate", json={"use_ai": True}, headers=headers
    )
    assert not_configured.status_code == 503
    assert not_configured.json()["error"]["code"] == "AI_NOT_CONFIGURED"

    text = "## Kirish\n\nTadbirda jami 3 nafar kitobxon ishtirok etdi, 120 nafar mehmon keldi."
    response = SimpleNamespace(
        stop_reason="end_turn",
        model="claude-opus-5-5",
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
    )
    fake = _fake_client(monkeypatch, response)
    drafted = await client.post(f"/api/v1/admin/reports/{report_id}/generate", json={"use_ai": True}, headers=headers)
    assert drafted.status_code == 200, drafted.text
    body = drafted.json()
    assert body["status"] == "AI_GENERATED"
    assert body["ai_model"] == "claude-opus-5-5"
    assert body["body_text"] == text
    assert body["number_issues"] == ["120"]  # the invented number is caught

    call = fake.calls[0]
    assert call["model"] == get_settings().ai_model
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    prompt = call["messages"][0]["content"]
    assert '"registered": 3' in prompt and "O'tkan kunlar" in prompt
    assert "o'ylab topmang" in call["system"]


async def test_ai_refusal_is_reported(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report_id = (await _create(client, admin, event_id))["id"]
    _fake_client(monkeypatch, SimpleNamespace(stop_reason="refusal", model="claude-opus-5-5", content=[]))
    refused = await client.post(
        f"/api/v1/admin/reports/{report_id}/generate", json={"use_ai": True}, headers=admin_headers(admin)
    )
    assert refused.status_code == 503
    assert refused.json()["error"]["code"] == "AI_REFUSED"


async def test_approved_reports_are_locked_and_versioned(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report_id = (await _create(client, admin, event_id))["id"]
    headers = admin_headers(admin)
    await client.post(f"/api/v1/admin/reports/{report_id}/generate", json={"use_ai": False}, headers=headers)
    await client.post(f"/api/v1/admin/reports/{report_id}/approve", headers=headers)

    locked = await client.patch(f"/api/v1/admin/reports/{report_id}", json={"title": "Boshqa nom"}, headers=headers)
    assert locked.status_code == 409
    second = await client.post(f"/api/v1/admin/reports/{report_id}/new-version", headers=headers)
    assert second.status_code == 201
    assert second.json()["version"] == 2
    assert second.json()["status"] == "REVIEW"
    assert second.json()["body_text"]

    archived = await client.post(f"/api/v1/admin/reports/{report_id}/archive", headers=headers)
    assert archived.json()["status"] == "ARCHIVED"
    # The official PDF stays downloadable from the archive, and is rebuilt if the file was lost.
    stored = await client.get(f"/api/v1/admin/reports/{report_id}", headers=headers)
    assert stored.json()["pdf_ready"] is True
    from app.models import Report

    key = (await db.get(Report, uuid.UUID(report_id))).pdf_object_key
    await get_storage().delete(key)
    rebuilt = await client.get(f"/api/v1/admin/reports/{report_id}/pdf", headers=headers)
    assert rebuilt.status_code == 200
    assert rebuilt.content.startswith(b"%PDF")


async def test_photos_and_draft_preview(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, *REPORT_PERMS)
    event_id = await _event_with_activity(db, admin)
    report_id = (await _create(client, admin, event_id))["id"]
    headers = admin_headers(admin)

    image = io.BytesIO()
    Image.new("RGB", (2400, 1600), (30, 120, 90)).save(image, format="PNG")
    uploaded = await client.post(
        f"/api/v1/admin/reports/{report_id}/photos",
        files={"file": ("tadbir.png", image.getvalue(), "image/png")},
        data={"caption": "Muhokama jarayoni"},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    photo_id = uploaded.json()["id"]
    served = await client.get(f"/api/v1/admin/reports/{report_id}/photos/{photo_id}", headers=headers)
    assert served.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(served.content)) as stored:
        assert max(stored.size) == 1600  # shrunk for the PDF

    fake = await client.post(
        f"/api/v1/admin/reports/{report_id}/photos",
        files={"file": ("virus.png", b"not an image", "image/png")},
        headers=headers,
    )
    assert fake.status_code == 400
    wrong_type = await client.post(
        f"/api/v1/admin/reports/{report_id}/photos",
        files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        headers=headers,
    )
    assert wrong_type.status_code == 400

    preview = await client.get(f"/api/v1/admin/reports/{report_id}/preview.pdf", headers=headers)
    assert preview.status_code == 200
    reader = PdfReader(io.BytesIO(preview.content))
    assert "QORALAMA" in _pdf_text(preview.content)
    assert any(page.images for page in reader.pages)  # the photo is embedded

    removed = await client.delete(f"/api/v1/admin/reports/{report_id}/photos/{photo_id}", headers=headers)
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/admin/reports/{report_id}", headers=headers)).json()["photos"] == []
