"""Round P: one reading contest tied to an event (set inside the event window) and the winners'
certificate choice (a standard design in turn, a pinned standard design, or a saved template)."""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign
from app.models.enums import CampaignStatus
from app.security.permissions import Perm
from app.services import campaigns as campaign_service
from app.services import certificate_designs as designs
from app.services import certificate_templates, certificates
from app.services import events as event_service
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(7_200_000)
PERMS = (Perm.EVENT_VIEW, Perm.EVENT_CREATE, Perm.EVENT_EDIT, Perm.SEASON_MANAGE, Perm.REWARD_MANAGE)


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


# ---------------------------------------------------------------------------- P9: one event → one contest


async def test_event_create_with_contest_links_and_follows_dates(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    book = await create_book(db, title="O'tkan kunlar")
    await db.commit()
    headers = admin_headers(admin)
    body = _event_body(
        str(book.id),
        campaign={"name": "Tadbir tanlovi", "points_per_book": 15, "completion_bonus": 5, "book_ids": [str(book.id)]},
    )
    created = await client.post("/api/v1/admin/events", json=body, headers=headers)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["campaign"] is not None
    assert event["campaign"]["name"] == "Tadbir tanlovi"
    assert event["campaign"]["points_per_book"] == 15
    assert event["campaign"]["book_ids"] == [str(book.id)]

    # the contest exists, is tied to the event and its window follows the event
    campaign = await campaign_service.for_event(db, uuid.UUID(event["id"]))
    assert campaign is not None
    assert campaign.event_id == uuid.UUID(event["id"])
    assert campaign.starts_at == datetime.fromisoformat(event["starts_at"])
    assert campaign.ends_at == datetime.fromisoformat(event["ends_at"])
    assert campaign.status == CampaignStatus.DRAFT

    # it also shows up in the contest list, flagged with its event
    listed = await client.get("/api/v1/admin/campaigns", headers=headers)
    assert listed.status_code == 200
    rows = [row for row in listed.json() if row["id"] == str(campaign.id)]
    assert rows and rows[0]["event_id"] == event["id"]


async def test_event_edit_upserts_then_unlinks_the_contest(client: httpx.AsyncClient, db: AsyncSession) -> None:
    admin = await _admin(db)
    book1 = await create_book(db, title="Birinchi")
    book2 = await create_book(db, title="Ikkinchi")
    await db.commit()
    headers = admin_headers(admin)

    created = await client.post("/api/v1/admin/events", json=_event_body(str(book1.id)), headers=headers)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["campaign"] is None  # no contest yet

    # attach a contest while editing, with a different book set
    edit = dict(
        _event_body(str(book1.id)),
        campaign={
            "name": "Qo'shilgan tanlov",
            "points_per_book": 20,
            "completion_bonus": 0,
            "book_ids": [str(book2.id)],
        },
    )
    patched = await client.patch(f"/api/v1/admin/events/{event['id']}", json=edit, headers=headers)
    assert patched.status_code == 200, patched.text
    assert patched.json()["campaign"]["book_ids"] == [str(book2.id)]
    campaign_id = patched.json()["campaign"]["id"]

    # editing again with the same event keeps the one contest (one event → one contest)
    again = await client.patch(f"/api/v1/admin/events/{event['id']}", json=edit, headers=headers)
    assert again.status_code == 200
    assert again.json()["campaign"]["id"] == campaign_id
    count = await db.scalar(
        select(Campaign.id).where(Campaign.event_id == uuid.UUID(event["id"]), Campaign.deleted_at.is_(None))
    )
    assert count is not None

    # sending campaign: null unlinks it — the contest is kept, just freed from the event
    unlink = dict(_event_body(str(book1.id)), campaign=None)
    off = await client.patch(f"/api/v1/admin/events/{event['id']}", json=unlink, headers=headers)
    assert off.status_code == 200
    assert off.json()["campaign"] is None
    freed = await db.get(Campaign, uuid.UUID(campaign_id))
    assert freed is not None and freed.event_id is None  # kept, just unlinked


# ---------------------------------------------------------------------------- P4: the certificate choice


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
