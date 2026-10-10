"""Certificates, round two: 12 designs taking turns, the club's own background, the app-only copy with
download and design-change limits, and the design pictures."""

from __future__ import annotations

import io
import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Certificate
from app.models.enums import CertificateKind, TestStatus
from app.security.permissions import Perm
from app.services import certificate_designs as designs
from app.services import certificates as certificate_service
from app.services import premium as premium_service
from app.services import quizzes as quiz_service
from tests.factories import create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers
from tests.test_phase25_documents import _attempt

_ids = itertools.count(1_300_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")


def _picture(width: int = 1200, height: int = 850) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (width, height), (40, 90, 160)).save(output, format="PNG")
    return output.getvalue()


async def _admin(db: AsyncSession, *roles: str) -> Any:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    for role in roles:
        await grant_role(db, admin, role)
    await grant_permissions(db, admin, Perm.EVENT_VIEW, Perm.EVENT_EDIT, Perm.TEST_VIEW, Perm.TEST_EDIT)
    return admin


async def _manual(db: AsyncSession, user_id: Any, key: str) -> Certificate:
    certificate = await certificate_service.issue(
        db,
        user_id=user_id,
        kind=CertificateKind.MANUAL,
        title="Faol kitobxon",
        description="Klub hayotidagi faol ishtiroki uchun taqdim etiladi.",
        dedup_key=key,
    )
    await db.commit()
    assert certificate is not None
    return certificate


def test_there_are_twelve_designs_taking_turns() -> None:
    codes = [design.code for design in designs.DESIGNS]
    assert len(codes) >= 10 and len(set(codes)) == len(codes)
    assert designs.next_after(None).code == codes[0]
    assert designs.next_after(codes[0]).code == codes[1]
    assert designs.next_after(codes[-1]).code == codes[0]  # round and round
    assert designs.next_after("unknown").code == codes[0]
    assert designs.get(designs.CUSTOM).code == codes[0]  # a fallback palette for drawing


async def test_each_test_takes_the_next_design_and_keeps_it(db: AsyncSession) -> None:
    members = [await create_user(db) for _ in range(3)]
    first, second = await create_test(db, title="Birinchi"), await create_test(db, title="Ikkinchi")
    first_id, second_id = first.id, second.id
    for test_id in (first_id, second_id):
        for score, member in zip((20, 15, 10), members, strict=True):
            await _attempt(db, test_id, member, score)
    await db.commit()

    await quiz_service.close_test(db, actor_id=None, test_id=first_id)
    await quiz_service.close_test(db, actor_id=None, test_id=second_id)
    rows = (await db.execute(select(Certificate.test_id, Certificate.design))).all()
    by_test: dict[Any, set[str]] = {}
    for test_id, design in rows:
        by_test.setdefault(test_id, set()).add(design)
    assert len(by_test[first_id]) == 1 and len(by_test[second_id]) == 1  # all winners of a test look alike
    one, two = by_test[first_id].pop(), by_test[second_id].pop()
    assert two == designs.next_after(one).code  # the next test, the next design

    third = await _manual(db, members[0].id, "manual:after")
    assert third.design == designs.next_after(two).code


async def test_the_club_background_is_used_and_locked_in_time(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    owner = await _admin(db, "SUPER_ADMIN")
    later = datetime.now(UTC) + timedelta(days=2)
    upcoming = await create_event(db, title="Kitob kechasi", starts_at=later)
    running = await create_event(db, title="Bugungi suhbat")  # started 5 minutes ago
    test = await create_test(db, title="Kecha savollari", event_id=running.id, starts_at=later)
    await db.commit()
    upcoming_id, running_id, test_id = upcoming.id, running.id, test.id
    owner_headers = admin_headers(owner)

    # An administrator may upload until the event starts...
    url = f"/api/v1/admin/events/{upcoming_id}/certificate-background"
    files = {"file": ("design.png", _picture(), "image/png")}
    assert (await client.put(url, files=files, headers=admin_headers(admin))).status_code == 204
    listed = (await client.get("/api/v1/admin/events?limit=50", headers=admin_headers(admin))).json()["items"]
    assert next(item for item in listed if item["id"] == str(upcoming_id))["certificate_background"] is True
    preview = await client.get(
        f"/api/v1/admin/events/{upcoming_id}/certificate-preview.png", headers=admin_headers(admin)
    )
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")

    # ...but not afterwards; the super admin still may (the test has not ended yet).
    url = f"/api/v1/admin/events/{running_id}/certificate-background"
    locked = await client.put(url, files=files, headers=admin_headers(admin))
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "BACKGROUND_LOCKED"
    assert (await client.put(url, files=files, headers=owner_headers)).status_code == 204

    # A portrait picture is turned and fitted to A4 landscape; a non-picture is refused.
    bad = await client.put(url, files={"file": ("x.png", b"not a picture", "image/png")}, headers=owner_headers)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "IMAGE_INVALID"
    portrait = await client.put(
        f"/api/v1/admin/tests/{test_id}/certificate-background",
        files={"file": ("p.png", _picture(800, 1200), "image/png")},
        headers=admin_headers(admin),
    )
    assert portrait.status_code == 204
    db.expire_all()
    stored = await db.get(type(test), test_id)
    from app.services.storage import get_storage

    picture = Image.open(io.BytesIO(await get_storage().get(stored.certificate_background_key)))
    assert picture.size == (2480, 1754)

    # The winners of the event's test get the test's own design (it comes before the event's).
    member = await create_user(db)
    await _attempt(db, test_id, member, 18)
    from app.models import AttendanceRecord
    from app.models.enums import AttendanceMethod

    db.add(AttendanceRecord(event_id=running_id, user_id=member.id, method=AttendanceMethod.CODE))
    await db.commit()
    await quiz_service.close_test(db, actor_id=None, test_id=test_id)
    certificate = await db.scalar(select(Certificate).where(Certificate.test_id == test_id))
    assert certificate.design == designs.CUSTOM
    assert certificate.background_key == stored.certificate_background_key
    pdf = await certificate_service.pdf_bytes(db, certificate)
    assert pdf.startswith(b"%PDF")

    # Once the test is closed, nobody changes the design any more.
    late = await client.delete(f"/api/v1/admin/tests/{test_id}/certificate-background", headers=owner_headers)
    assert late.status_code == 409


async def test_member_sees_downloads_and_changes_the_design(client: httpx.AsyncClient, db: AsyncSession) -> None:
    owner = await _admin(db, "SUPER_ADMIN")
    member = await create_user(db)
    await db.commit()
    member_id = member.id
    certificate = await _manual(db, member_id, "manual:limits")
    certificate_id = certificate.id
    headers = member_headers(member)
    base = f"/api/v1/me/certificates/{certificate.id}"

    # Looking at it is free (a picture marked «ko'rish uchun»), in any design.
    preview = await client.get(f"{base}/preview.png?design=ocean", headers=headers)
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
    assert (await client.get(f"{base}/preview.png?design=bogus", headers=headers)).status_code == 200
    names = [item["code"] for item in (await client.get("/api/v1/me/certificate-designs", headers=headers)).json()]
    assert names == [design.code for design in designs.DESIGNS]

    # One free download, then Premium.
    assert (await client.get(f"{base}/pdf", headers=headers)).status_code == 200
    detail = (await client.get(base, headers=headers)).json()
    assert detail["rights"] == {
        "can_download": False,
        "downloads_left": 0,
        "premium": False,
        "can_change_design": False,
        "design_changes_left": 0,
    }
    assert (await client.get(f"{base}/pdf", headers=headers)).status_code == 403

    # Premium: unlimited downloads and three design changes; the code stays the same.
    await premium_service.grant(db, actor_id=owner.id, user_id=member_id, days=30, note=None)
    code = certificate.verify_code
    choices = [design.code for design in designs.DESIGNS if design.code != certificate.design][:4]
    for index, choice in enumerate(choices[:3]):
        changed = await client.put(f"{base}/design", json={"design": choice}, headers=headers)
        assert changed.status_code == 200 and changed.json()["design"] == choice
        assert changed.json()["rights"]["design_changes_left"] == 2 - index
        pdf = await client.get(f"{base}/pdf", headers=headers)
        assert pdf.status_code == 200
    limit = await client.put(f"{base}/design", json={"design": choices[3]}, headers=headers)
    assert limit.status_code == 409 and limit.json()["error"]["code"] == "DESIGN_LIMIT"
    missing = await client.put(f"{base}/design", json={"design": designs.CUSTOM}, headers=headers)
    assert missing.status_code == 404  # no club background on this one
    db.expire_all()
    stored = await db.get(Certificate, certificate_id)
    assert stored.verify_code == code and stored.design == choices[2]
    assert stored.file_key == f"certificates/{stored.id}-{choices[2]}.pdf"

    # The check page says the certificate is one, whatever its design.
    page = await client.get(f"/v/{code}")
    assert page.status_code == 200 and "bitta" in page.text


async def test_settings_change_the_limits(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from app.services.settings import update_setting

    member = await create_user(db)
    await update_setting(db, key="certificates.free_downloads", value=0, actor_id=member.id)
    await db.commit()
    certificate = await _manual(db, member.id, "manual:none-free")
    blocked = await client.get(f"/api/v1/me/certificates/{certificate.id}/pdf", headers=member_headers(member))
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "PREMIUM_REQUIRED"


async def test_design_pictures_are_public_and_cached(client: httpx.AsyncClient, db: AsyncSession) -> None:
    listed = (await client.get("/api/v1/meta/certificate-designs")).json()
    assert [item["code"] for item in listed] == [design.code for design in designs.DESIGNS]
    assert all(item["title"] for item in listed)
    picture = await client.get(f"/api/v1/meta/certificate-designs/{listed[0]['code']}.png")
    assert picture.status_code == 200 and picture.content.startswith(b"\x89PNG")
    assert "max-age" in picture.headers["cache-control"]
    from app.services.storage import get_storage

    assert await get_storage().get(f"certificates/designs/{listed[0]['code']}-v1.png") == picture.content
    assert (await client.get("/api/v1/meta/certificate-designs/nope.png")).status_code == 404


async def test_admin_test_editor_sees_the_background_flag(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    test = await create_test(db, starts_at=datetime.now(UTC) + timedelta(hours=3), status=TestStatus.DRAFT)
    await db.commit()
    headers = admin_headers(admin)
    detail = (await client.get(f"/api/v1/admin/tests/{test.id}", headers=headers)).json()
    assert detail["certificate_background"] is False and detail["event_id"] is None
    files = {"file": ("design.jpg", _picture(), "image/png")}
    assert (
        await client.put(f"/api/v1/admin/tests/{test.id}/certificate-background", files=files, headers=headers)
    ).status_code == 204
    detail = (await client.get(f"/api/v1/admin/tests/{test.id}", headers=headers)).json()
    assert detail["certificate_background"] is True
    preview = await client.get(f"/api/v1/admin/tests/{test.id}/certificate-preview.png", headers=headers)
    assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
    removed = await client.delete(f"/api/v1/admin/tests/{test.id}/certificate-background", headers=headers)
    assert removed.status_code == 204
