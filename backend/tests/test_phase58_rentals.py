"""Round K5: «🏢 Ijara» — the owner's panel for copies rented to other organisations: the signing key made
in the panel, organisations, licence keys a rented copy accepts, payments, reminders — and never on a
rented copy itself."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import licence
from app.core.config import get_settings
from app.models import LicenceIssuer
from app.services import admin_digest, rentals
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(3_200_000)
URL = "/api/v1/admin/rentals"


async def _boss(db: AsyncSession):
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmaljon")
    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await grant_role(db, plain, "ADMIN")
    return boss, plain


async def test_rent_a_copy_from_the_panel(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss, plain = await _boss(db)
    headers = admin_headers(boss)
    assert (await client.get(URL, headers=admin_headers(plain))).status_code == 403

    first = (await client.get(URL, headers=headers)).json()
    assert first["public_key"] is None and first["items"] == []
    assert {plan["code"] for plan in first["plans"]} == {"SMALL", "MEDIUM", "LARGE", "CUSTOM"}

    # an organisation cannot get a key before the owner's key exists
    created = await client.post(
        f"{URL}/organizations",
        json={"name": "Namuna tibbiyot kolleji", "plan": "SMALL", "max_members": 300, "price_uzs": 3_000_000},
        headers=headers,
    )
    assert created.status_code == 201
    org = created.json()
    assert org["state"] == "NO_LICENCE"
    no_key = await client.post(
        f"{URL}/organizations/{org['id']}/licences", json={"expires_on": "2027-12-31"}, headers=headers
    )
    assert no_key.status_code == 409

    key = await client.post(f"{URL}/key", json={}, headers=headers)
    public_key = key.json()["public_key"]
    stored = await db.get(LicenceIssuer, 1)
    assert "PRIVATE KEY" not in stored.private_key_enc  # kept encrypted
    assert (await client.post(f"{URL}/key", json={}, headers=headers)).status_code == 409

    until = date.today() + timedelta(days=365)
    issued = await client.post(
        f"{URL}/organizations/{org['id']}/licences",
        json={"expires_on": until.isoformat(), "max_members": 300},
        headers=headers,
    )
    assert issued.status_code == 200, issued.text
    env = issued.json()["env"]
    lines = dict(line.split("=", 1) for line in env.splitlines())
    assert lines["LICENCE_REQUIRED"] == "true" and lines["LICENCE_PUBLIC_KEY"] == public_key
    # a rented copy accepts exactly this key
    parsed = licence.parse(lines["LICENCE_KEY"], lines["LICENCE_PUBLIC_KEY"])
    assert (parsed.organization, parsed.expires, parsed.max_members) == ("Namuna tibbiyot kolleji", until, 300)

    past = await client.post(
        f"{URL}/organizations/{org['id']}/licences", json={"expires_on": "2020-01-01"}, headers=headers
    )
    assert past.status_code == 400

    paid = await client.post(
        f"{URL}/organizations/{org['id']}/payments",
        json={"amount_uzs": 3_000_000, "paid_on": date.today().isoformat(), "note": "2026–2027"},
        headers=headers,
    )
    assert paid.status_code == 201
    details = (await client.get(f"{URL}/organizations/{org['id']}", headers=headers)).json()
    assert details["state"] == "ACTIVE" and details["paid_total"] == 3_000_000
    assert details["licences"][0]["env"] == env and details["payments"][0]["note"] == "2026–2027"
    overview = (await client.get(URL, headers=headers)).json()
    assert overview["totals"]["active"] == 1 and overview["totals"]["paid_this_year"] == 3_000_000

    removed = await client.delete(f"{URL}/payments/{details['payments'][0]['id']}", headers=headers)
    assert removed.status_code == 204

    # a licence ending soon shows up in the owner's morning message
    soon = date.today() + timedelta(days=5)
    await client.post(
        f"{URL}/organizations/{org['id']}/licences", json={"expires_on": soon.isoformat()}, headers=headers
    )
    assert await rentals.expiring_soon(db) == [("Namuna tibbiyot kolleji", 5)]
    from datetime import UTC, datetime

    text = await admin_digest.text(db, datetime.now(UTC))
    assert "«Namuna tibbiyot kolleji» litsenziyasi: 5 kun qoldi" in text

    # archived organisations are not reminded about
    archived = await client.put(
        f"{URL}/organizations/{org['id']}",
        json={"name": "Namuna tibbiyot kolleji", "plan": "SMALL", "archived": True},
        headers=headers,
    )
    assert archived.json()["state"] == "ARCHIVED"
    assert await rentals.expiring_soon(db) == []


async def test_an_existing_key_can_be_brought_in(client: httpx.AsyncClient, db: AsyncSession, tmp_path) -> None:
    from app import licence_tool

    boss, _ = await _boss(db)
    path = tmp_path / "owner-key.pem"
    assert licence_tool.main(["keygen", str(path)]) == 0
    bad = await client.post(f"{URL}/key", json={"private_pem": "not a key"}, headers=admin_headers(boss))
    assert bad.status_code == 400
    good = await client.post(f"{URL}/key", json={"private_pem": path.read_text()}, headers=admin_headers(boss))
    assert good.status_code == 200
    stored = await db.scalar(select(LicenceIssuer))
    assert stored.public_key == good.json()["public_key"]


async def test_a_rented_copy_has_no_rentals_panel(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    boss, _ = await _boss(db)
    monkeypatch.setattr(get_settings(), "licence_required", True)
    response = await client.get(URL, headers=admin_headers(boss))
    assert response.status_code == 403 and "egasining" in response.json()["error"]["message"]
    assert await rentals.expiring_soon(db) == []
