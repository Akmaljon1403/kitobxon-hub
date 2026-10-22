"""The winners' certificate choice for an event: a standard design in turn, a pinned standard
design, a saved template, or an uploaded image."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.permissions import Perm
from app.services import certificate_designs as designs
from app.services import certificate_templates, certificates
from app.services import events as event_service
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(7_200_000)
PERMS = (Perm.EVENT_VIEW, Perm.EVENT_CREATE, Perm.EVENT_EDIT, Perm.REWARD_MANAGE)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "bot_username", "kitobxon_test_bot")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _admin(db: AsyncSession, *roles: str) -> Any:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    for role in roles:
        await grant_role(db, admin, role)
    await grant_permissions(db, admin, *PERMS)
    return admin


def _iso(value: datetime) -> str:
    return value.isoformat()


def _event_body(book_id: str, **extra: Any) -> dict[str, Any]:
    day = datetime.now(UTC).replace(microsecond=0) + timedelta(days=3)
    body: dict[str, Any] = {
        "title": "Kitob suhbati",
        "status": "DRAFT",
        "starts_at": _iso(day),
        "ends_at": _iso(day + timedelta(hours=2)),
        "book_id": book_id,
    }
    body.update(extra)
    return body


async def test_certificate_choice_pins_design_then_template_then_auto(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    book = await create_book(db)
    await db.commit()
    headers = admin_headers(admin)
    event = (await client.post("/api/v1/admin/events", json=_event_body(str(book.id)), headers=headers)).json()
    base = f"/api/v1/admin/events/{event['id']}/certificate-choice"

    # pin a standard design
    pinned = await client.put(base, json={"design": "royal"}, headers=headers)
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["certificate_design"] == "royal"
    assert pinned.json()["certificate_template_id"] is None

    # an unknown design is refused
    assert (await client.put(base, json={"design": "no-such"}, headers=headers)).status_code == 400

    # choosing a saved template clears the pinned design
    template = await certificate_templates.create(
        db, actor_id=admin.id, name="Klub shabloni", elements=[], is_default=False
    )
    chosen = await client.put(base, json={"template_id": str(template.id)}, headers=headers)
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["certificate_template_id"] == str(template.id)
    assert chosen.json()["certificate_design"] is None

    # back to the standard rotation (neither)
    auto = await client.put(base, json={}, headers=headers)
    assert auto.status_code == 200
    assert auto.json()["certificate_design"] is None and auto.json()["certificate_template_id"] is None


async def test_pinned_design_is_used_when_issuing(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    book = await create_book(db)
    await db.commit()
    headers = admin_headers(admin)
    event = (await client.post("/api/v1/admin/events", json=_event_body(str(book.id)), headers=headers)).json()
    event_id = uuid.UUID(event["id"])
    await client.put(f"/api/v1/admin/events/{event_id}/certificate-choice", json={"design": "stars"}, headers=headers)

    design, background = await certificates._design_for(db, test_id=None, event_id=event_id, period=None)
    assert design == "stars" and background is None
    assert "stars" in designs.BY_CODE


async def test_uploading_a_background_drops_the_pinned_choice(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db, "SUPER_ADMIN")
    book = await create_book(db)
    await db.commit()
    headers = admin_headers(admin)
    event = (await client.post("/api/v1/admin/events", json=_event_body(str(book.id)), headers=headers)).json()
    event_id = uuid.UUID(event["id"])
    await client.put(f"/api/v1/admin/events/{event_id}/certificate-choice", json={"design": "ruby"}, headers=headers)

    # a tiny valid PNG uploaded as the event's own certificate background
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (1240, 877), "#ffffff").save(buffer, format="PNG")
    buffer.seek(0)
    files = {"file": ("design.png", buffer, "image/png")}
    up = await client.put(f"/api/v1/admin/events/{event_id}/certificate-background", files=files, headers=headers)
    assert up.status_code == 204, up.text

    event_row = await event_service.get_event(db, event_id)
    await db.refresh(event_row)
    assert event_row.certificate_background_key is not None
    assert event_row.certificate_design is None  # the uploaded image replaced the pinned design
