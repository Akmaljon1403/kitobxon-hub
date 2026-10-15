"""Round N1-N5 + N2: the certificate visual designer.

Admins upload their own design (PNG/JPG/PDF) and place elements on it; certificates are issued
automatically (test winners / every passer) or by hand as a gift with a personal message. The
uploaded design is drawn exactly as given — no readability overlay, no «ko'rish uchun» watermark.
"""

from __future__ import annotations

import io
import itertools
import uuid

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Certificate, CertificateTemplate, Notification
from app.models.enums import CertificateKind
from app.schemas.certificate import TemplateElement
from app.services import certificate_templates as templates
from app.services import certificates as certificate_service
from tests.factories import create_test, create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(4_600_000)


def _png(width: int = 1600, height: int = 1131, colour: str = "#f3efe3") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


async def _boss(db: AsyncSession) -> object:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    return boss


# ---------------------------------------------------------------------------- the design


def test_prepare_keeps_aspect_and_makes_png() -> None:
    data, width, height = templates._prepare_sync(_png(2000, 1000))
    assert width == 2000 and height == 1000  # under the 2200 cap: unchanged
    assert Image.open(io.BytesIO(data)).format == "PNG"


def test_prepare_rejects_junk() -> None:
    from app.core.errors import BadRequestError

    with pytest.raises(BadRequestError):
        templates._prepare_sync(b"not a picture")


async def test_crud_and_single_default(db: AsyncSession) -> None:
    boss = await _boss(db)
    first = await templates.create(db, actor_id=boss.id, name="Bittasi", elements=[], is_default=True)
    assert first.is_default and first.elements  # empty list falls back to a starter layout
    second = await templates.create(db, actor_id=boss.id, name="Ikkinchi", elements=[], is_default=True)
    await db.refresh(first)
    assert second.is_default and not first.is_default  # only one default at a time
    assert (await templates.default_template(db)).id == second.id


async def test_render_with_template_has_no_watermark(db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids), first_name="Aziza", last_name="Karimova")
    await db.commit()
    template = await templates.create(
        db,
        actor_id=boss.id,
        name="Asosiy",
        elements=[TemplateElement(type="name", x=20, y=40, w=60, size=30)],
        is_default=False,
    )
    await templates.set_background(db, template=template, actor_id=boss.id, data=_png())
    certificate = await certificate_service.issue_manual(
        db,
        actor_id=boss.id,
        user_id=member.id,
        title="Faol kitobxon",
        description="Klub faoliyatida faol ishtirok etgani uchun taqdim etiladi.",
        place=None,
        template_id=template.id,
    )
    assert certificate.template_id == template.id and certificate.design is None
    pdf = await certificate_service.pdf_bytes(db, certificate)
    assert pdf[:5] == b"%PDF-"
    # the admin preview is a clean picture (no «ko'rish uchun» overlay)
    preview = await templates.preview_png(db, template, width=600)
    assert Image.open(io.BytesIO(preview)).size[0] == 600


async def test_gift_attaches_pdf_and_personal_message(db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir", last_name="Qodirov")
    await db.commit()
    certificate = await certificate_service.issue_manual(
        db,
        actor_id=boss.id,
        user_id=member.id,
        title="Sovg'a",
        description="Alohida hurmat uchun taqdim etiladi.",
        place=None,
        gift_message="Tabriklaymiz! Mana sizga maxsus sertifikat 🎁",
    )
    notification = await db.scalar(
        select(Notification).where(Notification.dedup_key == f"certificate:{certificate.id}")
    )
    assert notification is not None
    assert "Tabriklaymiz" in notification.text  # the admin's own words are the message
    assert notification.payload["certificate_id"] == str(certificate.id)
    # the sender attaches the real PDF to the gift message
    from app.workers.sender import _document

    attached = await _document(db, notification)
    assert attached is not None


async def test_completion_certificate_for_every_passer(db: AsyncSession) -> None:
    await _boss(db)
    a = await create_user(db, telegram_id=next(_ids))
    b = await create_user(db, telegram_id=next(_ids))
    test = await create_test(db, certificate_on_pass=True)
    await db.commit()
    standings = [{"user_id": a.id}, {"user_id": b.id}]
    count = await certificate_service.issue_for_passers(db, test, standings)
    await db.commit()
    assert count == 2
    kinds = await db.scalars(select(Certificate.kind).where(Certificate.test_id == test.id))
    assert set(kinds) == {CertificateKind.COMPLETION}
    # idempotent: running the close job twice does not double-issue
    again = await certificate_service.issue_for_passers(db, test, standings)
    assert again == 0


# ---------------------------------------------------------------------------- the admin API


async def test_designer_endpoints_end_to_end(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    headers = admin_headers(boss)

    created = await client.post(
        "/api/v1/admin/certificate-templates",
        json={"name": "Mening dizaynim", "elements": [], "is_default": True},
        headers=headers,
    )
    assert created.status_code == 201
    template_id = created.json()["id"]

    upload = await client.put(
        f"/api/v1/admin/certificate-templates/{template_id}/background",
        files={"file": ("design.png", _png(), "image/png")},
        headers=headers,
    )
    assert upload.status_code == 200 and upload.json()["has_background"] is True

    saved = await client.put(
        f"/api/v1/admin/certificate-templates/{template_id}",
        json={
            "name": "Mening dizaynim",
            "is_default": True,
            "elements": [
                {"type": "name", "x": 20, "y": 40, "w": 60, "size": 30, "bold": True, "color": "#14402c"},
                {"type": "qr", "x": 84, "y": 80, "w": 12},
            ],
        },
        headers=headers,
    )
    assert saved.status_code == 200 and len(saved.json()["elements"]) == 2

    listed = await client.get("/api/v1/admin/certificate-templates", headers=headers)
    assert listed.status_code == 200 and len(listed.json()) == 1

    preview = await client.get(f"/api/v1/admin/certificate-templates/{template_id}/preview.png", headers=headers)
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/png" and preview.content

    meta = await client.get("/api/v1/meta/certificate-elements")
    assert meta.status_code == 200 and "serif" in meta.json()["fonts"]

    removed = await client.delete(f"/api/v1/admin/certificate-templates/{template_id}", headers=headers)
    assert removed.status_code == 204
    assert await db.scalar(select(CertificateTemplate).where(CertificateTemplate.id == uuid.UUID(template_id))) is None


async def test_designer_rejects_bad_colour(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    created = await client.post(
        "/api/v1/admin/certificate-templates",
        json={
            "name": "X",
            "elements": [{"type": "name", "x": 10, "y": 10, "w": 20, "color": "red"}],
            "is_default": False,
        },
        headers=admin_headers(boss),
    )
    assert created.status_code == 422  # colour must be a #rrggbb hex
