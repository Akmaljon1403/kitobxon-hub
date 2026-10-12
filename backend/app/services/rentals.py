"""«🏢 Ijara»: the owner's panel for copies of Kitobxon Hub rented to other organisations.

Each organisation runs its own copy — its own server, database and bot — so organisations never mix.
This panel (only on the owner's server, only for super administrators) keeps the paperwork: the owner's
signing key (made here with one button; the private half is stored encrypted), the organisations, every
licence key given and every payment. A licence key is three lines for the copy's settings:

    LICENCE_REQUIRED=true
    LICENCE_PUBLIC_KEY=…   (the same for every copy)
    LICENCE_KEY=…          (this organisation's licence: name, until when, how many members)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import licence
from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import LicenceIssuer, RentalLicence, RentalOrganization, RentalPayment
from app.security.crypto import decrypt_secret, encrypt_secret
from app.services.audit import record_audit
from app.utils.timezone import local_tz

PURPOSE = "licence-issuer"
# The plans offered (docs/BOSHQARUV_QOLLANMA.md, «Boshqa tashkilotlarga ijaraga berish»).
PLANS: dict[str, dict[str, Any]] = {
    "SMALL": {"title": "Kichik (maktab, kollej)", "members": 300, "yearly": 3_000_000, "monthly": 300_000},
    "MEDIUM": {"title": "O'rta (institut)", "members": 1500, "yearly": 6_000_000, "monthly": 600_000},
    "LARGE": {"title": "Katta (universitet)", "members": None, "yearly": 12_000_000, "monthly": 1_200_000},
    "CUSTOM": {"title": "Kelishilgan", "members": None, "yearly": None, "monthly": None},
}
BILLING = {"YEARLY": "yillik", "MONTHLY": "oylik"}
SOON_DAYS = 30


def available() -> bool:
    """Only the owner's own server issues licences: a rented copy (LICENCE_REQUIRED) never shows the panel."""
    return not get_settings().licence_required


def _guard() -> None:
    if not available():
        raise ForbiddenError("RENTALS_OFF", "Ijara bo'limi faqat asosiy (egasining) serverida ishlaydi.")


def _today() -> date:
    return datetime.now(local_tz()).date()


# ---------------------------------------------------------------------------- the owner's key


async def issuer(session: AsyncSession) -> LicenceIssuer | None:
    return await session.get(LicenceIssuer, 1)


async def create_key(session: AsyncSession, *, actor_id: uuid.UUID, private_pem: str | None = None) -> LicenceIssuer:
    """Make the owner's signing key (or take one made earlier with ``python -m app.licence_tool keygen``)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    _guard()
    if await issuer(session) is not None:
        raise ConflictError("KEY_EXISTS", "Kalit allaqachon yaratilgan — uni almashtirib bo'lmaydi.")
    if private_pem:
        try:
            private = serialization.load_pem_private_key(private_pem.strip().encode(), password=None)
        except (ValueError, TypeError) as exc:
            raise BadRequestError("KEY_INVALID", "Bu maxfiy kalit emas (PEM ko'rinishida bo'lishi kerak).") from exc
        if not isinstance(private, Ed25519PrivateKey):
            raise BadRequestError("KEY_INVALID", "Ed25519 kaliti kerak (licence_tool keygen bilan yaratilgan).")
    else:
        private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    row = LicenceIssuer(
        id=1, private_key_enc=encrypt_secret(PURPOSE, pem), public_key=licence.b64encode(public), created_by=actor_id
    )
    session.add(row)
    record_audit(
        session,
        actor_id=actor_id,
        action="LICENCE_KEY_CREATE",
        entity_type="licence_issuer",
        entity_id="1",
        after={"imported": bool(private_pem)},
    )
    await session.commit()
    return row


# ---------------------------------------------------------------------------- organisations


def _org_dict(
    org: RentalOrganization, current: RentalLicence | None, paid: int, last_paid: date | None
) -> dict[str, Any]:
    days_left = (current.expires_on - _today()).days if current else None
    if org.archived_at is not None:
        state = "ARCHIVED"
    elif current is None:
        state = "NO_LICENCE"
    elif days_left is not None and days_left < 0:
        state = "EXPIRED"
    elif days_left is not None and days_left <= SOON_DAYS:
        state = "SOON"
    else:
        state = "ACTIVE"
    return {
        "id": org.id,
        "name": org.name,
        "contact_person": org.contact_person,
        "phone": org.phone,
        "telegram": org.telegram,
        "plan": org.plan,
        "plan_title": PLANS.get(org.plan, PLANS["CUSTOM"])["title"],
        "max_members": org.max_members,
        "price_uzs": org.price_uzs,
        "billing": org.billing,
        "server_url": org.server_url,
        "bot_username": org.bot_username,
        "notes": org.notes,
        "archived": org.archived_at is not None,
        "expires_on": current.expires_on if current else None,
        "days_left": days_left,
        "state": state,
        "paid_total": paid,
        "last_paid_on": last_paid,
        "created_at": org.created_at,
    }


async def _current_licences(session: AsyncSession) -> dict[uuid.UUID, RentalLicence]:
    rows = await session.scalars(select(RentalLicence).order_by(RentalLicence.issued_at))
    return {row.organization_id: row for row in rows}  # the latest one wins


async def overview(session: AsyncSession) -> dict[str, Any]:
    _guard()
    key = await issuer(session)
    current = await _current_licences(session)
    payments = {
        org_id: (int(total or 0), last)
        for org_id, total, last in (
            await session.execute(
                select(
                    RentalPayment.organization_id, func.sum(RentalPayment.amount_uzs), func.max(RentalPayment.paid_on)
                ).group_by(RentalPayment.organization_id)
            )
        ).all()
    }
    orgs = list(await session.scalars(select(RentalOrganization).order_by(RentalOrganization.name)))
    items = [_org_dict(org, current.get(org.id), *payments.get(org.id, (0, None))) for org in orgs]
    year_start = _today().replace(month=1, day=1)
    this_year = await session.scalar(
        select(func.coalesce(func.sum(RentalPayment.amount_uzs), 0)).where(RentalPayment.paid_on >= year_start)
    )
    return {
        "public_key": key.public_key if key else None,
        "plans": [{"code": code, **plan} for code, plan in PLANS.items()],
        "items": items,
        "totals": {
            "active": sum(1 for item in items if item["state"] in ("ACTIVE", "SOON")),
            "soon": sum(1 for item in items if item["state"] == "SOON"),
            "expired": sum(1 for item in items if item["state"] == "EXPIRED"),
            "paid_this_year": int(this_year or 0),
        },
    }


FIELDS = (
    "name",
    "contact_person",
    "phone",
    "telegram",
    "plan",
    "max_members",
    "price_uzs",
    "billing",
    "server_url",
    "bot_username",
    "notes",
)


async def save(
    session: AsyncSession, *, actor_id: uuid.UUID, organization_id: uuid.UUID | None, data: dict[str, Any]
) -> RentalOrganization:
    _guard()
    if data.get("plan") not in PLANS:
        raise BadRequestError("PLAN_UNKNOWN", "Tarifni tanlang.")
    if data.get("billing") not in BILLING:
        raise BadRequestError("BILLING_UNKNOWN", "To'lov davrini tanlang.")
    if organization_id is None:
        org = RentalOrganization()
        session.add(org)
    else:
        org = await _get(session, organization_id)
    before = {field: getattr(org, field, None) for field in FIELDS}
    for field in FIELDS:
        value = data.get(field)
        if isinstance(value, str):
            value = value.strip() or None  # an empty box means «not given»
        setattr(org, field, value)
    if not org.name:
        raise BadRequestError("NAME_REQUIRED", "Tashkilot nomini yozing.")
    if "archived" in data:
        org.archived_at = datetime.now(local_tz()) if data["archived"] else None
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="RENTAL_ORG_SAVE",
        entity_type="rental_organization",
        entity_id=org.id,
        before={key: str(value) for key, value in before.items() if value is not None} if organization_id else None,
        after={field: str(getattr(org, field)) for field in FIELDS if getattr(org, field) is not None},
    )
    await session.commit()
    await session.refresh(org)
    return org


async def _get(session: AsyncSession, organization_id: uuid.UUID) -> RentalOrganization:
    org = await session.get(RentalOrganization, organization_id)
    if org is None:
        raise NotFoundError("ORG_NOT_FOUND", "Tashkilot topilmadi.")
    return org


def env_block(public_key: str, key: str) -> str:
    return f"LICENCE_REQUIRED=true\nLICENCE_PUBLIC_KEY={public_key}\nLICENCE_KEY={key}"


async def details(session: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    _guard()
    org = await _get(session, organization_id)
    key = await issuer(session)
    licences = list(
        await session.scalars(
            select(RentalLicence)
            .where(RentalLicence.organization_id == org.id)
            .order_by(RentalLicence.issued_at.desc())
        )
    )
    payments = list(
        await session.scalars(
            select(RentalPayment)
            .where(RentalPayment.organization_id == org.id)
            .order_by(RentalPayment.paid_on.desc(), RentalPayment.created_at.desc())
        )
    )
    paid = sum(payment.amount_uzs for payment in payments)
    base = _org_dict(org, licences[0] if licences else None, paid, payments[0].paid_on if payments else None)
    return {
        **base,
        "licences": [
            {
                "id": row.id,
                "expires_on": row.expires_on,
                "max_members": row.max_members,
                "issued_at": row.issued_at,
                "env": env_block(key.public_key, row.key) if key else None,
            }
            for row in licences
        ],
        "payments": [
            {"id": row.id, "amount_uzs": row.amount_uzs, "paid_on": row.paid_on, "note": row.note} for row in payments
        ],
    }


async def issue(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    expires_on: date,
    max_members: int | None,
) -> dict[str, Any]:
    """A signed licence for the organisation's copy: shown as the three lines for its settings."""
    _guard()
    org = await _get(session, organization_id)
    key = await issuer(session)
    if key is None:
        raise ConflictError("NO_KEY", "Avval «🔑 Kalit yaratish» tugmasini bosing.")
    if expires_on <= _today():
        raise BadRequestError("DATE_IN_PAST", "Tugash sanasi bugundan keyin bo'lsin.")
    if expires_on > _today() + timedelta(days=366 * 5):
        raise BadRequestError("DATE_TOO_FAR", "Ko'pi bilan 5 yilga.")
    if max_members is not None and max_members < 1:
        raise BadRequestError("MEMBERS_INVALID", "A'zolar chegarasi musbat bo'lsin (yoki bo'sh — cheklovsiz).")
    private_pem = decrypt_secret(PURPOSE, key.private_key_enc).encode()
    signed = licence.sign(private_pem, organization=org.name, until=expires_on, members=max_members)
    row = RentalLicence(
        organization_id=org.id, key=signed, expires_on=expires_on, max_members=max_members, issued_by=actor_id
    )
    session.add(row)
    org.max_members = max_members
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="RENTAL_LICENCE_ISSUE",
        entity_type="rental_organization",
        entity_id=org.id,
        after={"expires_on": expires_on.isoformat(), "max_members": max_members},
    )
    await session.commit()
    return {"id": row.id, "expires_on": expires_on, "env": env_block(key.public_key, signed)}


async def add_payment(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    amount_uzs: int,
    paid_on: date,
    note: str | None,
) -> RentalPayment:
    _guard()
    org = await _get(session, organization_id)
    if amount_uzs <= 0:
        raise BadRequestError("AMOUNT_INVALID", "Summani yozing.")
    row = RentalPayment(
        organization_id=org.id,
        amount_uzs=amount_uzs,
        paid_on=paid_on,
        note=(note or "").strip()[:255] or None,
        recorded_by=actor_id,
    )
    session.add(row)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="RENTAL_PAYMENT",
        entity_type="rental_organization",
        entity_id=org.id,
        after={"amount_uzs": amount_uzs, "paid_on": paid_on.isoformat()},
    )
    await session.commit()
    return row


async def delete_payment(session: AsyncSession, *, actor_id: uuid.UUID, payment_id: uuid.UUID) -> None:
    _guard()
    row = await session.get(RentalPayment, payment_id)
    if row is None:
        raise NotFoundError("PAYMENT_NOT_FOUND", "To'lov topilmadi.")
    record_audit(
        session,
        actor_id=actor_id,
        action="RENTAL_PAYMENT_DELETE",
        entity_type="rental_organization",
        entity_id=row.organization_id,
        before={"amount_uzs": row.amount_uzs, "paid_on": row.paid_on.isoformat()},
    )
    await session.delete(row)
    await session.commit()


async def expiring_soon(session: AsyncSession, days: int = SOON_DAYS) -> list[tuple[str, int]]:
    """(organisation, days left) whose latest licence ends within ``days`` (for the morning digest)."""
    if not available():
        return []
    current = await _current_licences(session)
    if not current:
        return []
    orgs = {
        org.id: org
        for org in await session.scalars(
            select(RentalOrganization).where(
                RentalOrganization.id.in_(list(current)), RentalOrganization.archived_at.is_(None)
            )
        )
    }
    today = _today()
    result = []
    for org_id, row in current.items():
        left = (row.expires_on - today).days
        if org_id in orgs and left <= days:
            result.append((orgs[org_id].name, left))
    return sorted(result, key=lambda pair: pair[1])
