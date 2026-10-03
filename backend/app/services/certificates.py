"""Certificates for the best members, issued automatically and checkable by anyone.

* places 1-3 of a closed test (for a test tied to an event, only members whose attendance at
  that event was confirmed take part in the places);
* places 1-3 of the previous month's ranking (in the first days of a month);
* by hand from the Admin Panel ("Faol kitobxon", ...).

Each certificate is a PDF (A4 landscape) with a QR code leading to ``/v/<code>``, where anyone
can check that it is genuine and not revoked. The bot sends the PDF to the winner.
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

import segno
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.models import AttendanceRecord, Certificate, Event, Test, User
from app.models.enums import AttendanceStatus, CertificateKind, NotificationType
from app.services.audit import record_audit
from app.services.notifications import enqueue_notification, render
from app.services.settings import get_setting
from app.services.storage import get_storage
from app.utils.timezone import MONTHS_UZ, format_date, local_tz

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O, 1/I: easy to read aloud and type
# Months before this one are never certified retroactively (the feature started here).
MONTHLY_SINCE = "2026-10"
PLACES = (1, 2, 3)


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(10))


def display_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


def normalize_code(text: str) -> str:
    return "".join(char for char in text.upper() if char.isalnum())


def verify_url(code: str) -> str | None:
    base = get_settings().base_url
    return f"{base}/v/{code}" if base else None


def filename(certificate: Certificate) -> str:
    return f"sertifikat-{display_code(certificate.verify_code)}.pdf"


# ---------------------------------------------------------------------------- issuing


async def issue(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: CertificateKind,
    title: str,
    description: str,
    dedup_key: str,
    place: int | None = None,
    test_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
    period: str | None = None,
    issued_by: uuid.UUID | None = None,
) -> Certificate | None:
    """Create a certificate and queue it for the member. Returns None if it already exists."""
    new_id = await session.scalar(
        insert(Certificate)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            kind=kind,
            place=place,
            title=title,
            description=description,
            test_id=test_id,
            event_id=event_id,
            period=period,
            dedup_key=dedup_key,
            verify_code=new_code(),
            issued_by=issued_by,
        )
        .on_conflict_do_nothing(index_elements=[Certificate.dedup_key])
        .returning(Certificate.id)
    )
    if new_id is None:
        return None
    certificate = await session.get(Certificate, new_id)
    assert certificate is not None
    with_pdf = await _pdf_allowed(session, user_id)
    details = f"Tekshirish kodi: {display_code(certificate.verify_code)}"
    if with_pdf:
        details = "📎 PDF nusxasi shu xabarga ilova qilingan — yuklab olib, chop etishingiz mumkin.\n" + details
    else:
        link = verify_url(certificate.verify_code)
        details += "\n\n📄 PDF nusxasini yuklab olish va chop etish — 💎 Premium imkoniyati." + (
            f"\nSertifikatingiz onlayn tasdiqlangan — ushbu havolani istalgan kishiga ko'rsating: {link}"
            if link
            else ""
        )
    text = await render(session, NotificationType.CERTIFICATE, title=title, details=details)
    if text is not None:
        buttons: list[dict[str, Any]] = [{"text": "🎓 Sertifikatlarim", "app_route": "certificates"}]
        if not with_pdf:
            buttons.append({"text": "💎 Premium", "app_route": "premium"})
        payload: dict[str, Any] = {"buttons": buttons, "mood": "CELEBRATE"}
        if with_pdf:
            payload["certificate_id"] = str(certificate.id)
        await enqueue_notification(
            session,
            user_id=user_id,
            type_=NotificationType.CERTIFICATE,
            text=text,
            dedup_key=f"certificate:{certificate.id}",
            payload=payload,
            priority=2,
        )
    return certificate


async def _pdf_allowed(session: AsyncSession, user_id: uuid.UUID) -> bool:
    from app.services import features

    user = await session.get(User, user_id)
    return user is not None and await features.allowed(session, user, "certificate_pdf") == "on"


async def _attended(session: AsyncSession, event_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        await session.scalars(
            select(AttendanceRecord.user_id).where(
                AttendanceRecord.event_id == event_id, AttendanceRecord.status == AttendanceStatus.VERIFIED
            )
        )
    )


async def issue_for_test(session: AsyncSession, test: Test, standings: list[dict[str, Any]]) -> int:
    """Places 1-3 of a closed test. The caller commits."""
    if not await get_setting(session, "certificates.test_winners"):
        return 0
    winners = standings
    event = await session.get(Event, test.event_id) if test.event_id else None
    if event is not None:
        present = await _attended(session, event.id)
        winners = [row for row in standings if row["user_id"] in present]
    issued = 0
    for place, row in zip(PLACES, winners, strict=False):
        if event is not None:
            description = (
                f"«{event.title}» tadbiri doirasida o'tkazilgan «{test.title}» bilim testida "
                f"{place}-o'rinni egallagani uchun taqdim etiladi."
            )
        else:
            description = f"«{test.title}» bilim testida {place}-o'rinni egallagani uchun taqdim etiladi."
        created = await issue(
            session,
            user_id=row["user_id"],
            kind=CertificateKind.TEST_PLACE,
            place=place,
            title=f"«{test.title}» testi — {place}-o'rin",
            description=description,
            dedup_key=f"test:{test.id}:place:{place}",
            test_id=test.id,
            event_id=event.id if event else None,
        )
        issued += 1 if created else 0
    return issued


async def issue_monthly(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: in the first week of a month (from 10:00 on the 1st, so late corrections
    still count), places 1-3 of last month's ranking get a certificate."""
    from app.services.ranking import ranking

    local_now = (now or datetime.now(UTC)).astimezone(local_tz())
    if local_now.day > 7 or (local_now.day == 1 and local_now.hour < 10):
        return 0
    if not await get_setting(session, "certificates.monthly_top"):
        return 0
    this_month = datetime.combine(local_now.date().replace(day=1), time.min, tzinfo=local_tz())
    last_month = (this_month - timedelta(days=1)).replace(day=1)
    period = f"{last_month:%Y-%m}"
    if period < MONTHLY_SINCE:
        return 0
    board = await ranking(session, period="month", scope="all", viewer=None, limit=3, between=(last_month, this_month))
    month = f"{last_month.year}-yil {MONTHS_UZ[last_month.month - 1]}"
    issued = 0
    for row in board.items[:3]:
        created = await issue(
            session,
            user_id=row.user_id,
            kind=CertificateKind.MONTHLY_TOP,
            place=row.rank,
            title=f"{month.capitalize()} reytingi — {row.rank}-o'rin",
            description=(
                f"{month} oyida Kitobxonlar klubi reytingida {row.rank}-o'rinni egallagani va faol "
                "kitobxonligi uchun taqdim etiladi."
            ),
            dedup_key=f"month:{period}:place:{row.rank}",
            period=period,
        )
        issued += 1 if created else 0
    return issued


async def issue_manual(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    description: str,
    place: int | None,
) -> Certificate:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    certificate = await issue(
        session,
        user_id=user_id,
        kind=CertificateKind.MANUAL,
        place=place,
        title=title,
        description=description,
        dedup_key=f"manual:{uuid.uuid4()}",
        issued_by=actor_id,
    )
    assert certificate is not None
    record_audit(
        session,
        actor_id=actor_id,
        action="CERTIFICATE_ISSUE",
        entity_type="certificate",
        entity_id=certificate.id,
        after={"user_id": str(user_id), "title": title, "place": place},
    )
    await session.commit()
    return certificate


async def revoke(session: AsyncSession, *, actor_id: uuid.UUID, certificate_id: uuid.UUID, reason: str) -> Certificate:
    certificate = await get(session, certificate_id)
    if certificate.revoked_at is not None:
        raise ConflictError("CERTIFICATE_REVOKED", "Sertifikat allaqachon bekor qilingan.")
    certificate.revoked_at = datetime.now(UTC)
    certificate.revoke_reason = reason
    record_audit(
        session,
        actor_id=actor_id,
        action="CERTIFICATE_REVOKE",
        entity_type="certificate",
        entity_id=certificate.id,
        after={"reason": reason},
    )
    await session.commit()
    return certificate


# ---------------------------------------------------------------------------- reading


async def get(session: AsyncSession, certificate_id: uuid.UUID) -> Certificate:
    certificate = await session.get(Certificate, certificate_id)
    if certificate is None:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", "Sertifikat topilmadi.")
    return certificate


async def get_own(session: AsyncSession, *, user_id: uuid.UUID, certificate_id: uuid.UUID) -> Certificate:
    certificate = await session.get(Certificate, certificate_id)
    if certificate is None or certificate.user_id != user_id or certificate.revoked_at is not None:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", "Sertifikat topilmadi.")
    return certificate


async def by_code(session: AsyncSession, code: str) -> Certificate | None:
    normalized = normalize_code(code)
    if len(normalized) != 10:
        return None
    return await session.scalar(select(Certificate).where(Certificate.verify_code == normalized))


async def member_certificates(session: AsyncSession, user_id: uuid.UUID) -> list[Certificate]:
    return list(
        await session.scalars(
            select(Certificate)
            .where(Certificate.user_id == user_id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
        )
    )


async def count_for_member(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Certificate)
            .where(Certificate.user_id == user_id, Certificate.revoked_at.is_(None))
        )
        or 0
    )


async def list_admin(
    session: AsyncSession, *, q: str | None, kind: CertificateKind | None, limit: int, offset: int
) -> tuple[list[tuple[Certificate, User]], int]:
    query = select(Certificate, User).join(User, User.id == Certificate.user_id)
    if kind is not None:
        query = query.where(Certificate.kind == kind)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                Certificate.title.ilike(pattern),
                Certificate.verify_code == normalize_code(q),
            )
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await session.execute(query.order_by(Certificate.issued_at.desc()).limit(limit).offset(offset))).all()
    return [(row[0], row[1]) for row in rows], int(total or 0)


# ---------------------------------------------------------------------------- the PDF


async def render_pdf(session: AsyncSession, certificate: Certificate) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is needed

    from app.services.passport import member_number
    from app.services.report_pdf import TEMPLATES, _environment

    user = await session.get(User, certificate.user_id)
    assert user is not None
    url = verify_url(certificate.verify_code)
    html = (
        _environment()
        .get_template("certificate.html")
        .render(
            organization=await get_setting(session, "org.organization_name"),
            club=await get_setting(session, "org.club_name"),
            name=f"{user.last_name} {user.first_name}",
            place=certificate.place,
            description=certificate.description,
            issued_on=format_date(certificate.issued_at),
            number=member_number(user),
            signer_title=await get_setting(session, "certificates.signer_title"),
            signer_name=await get_setting(session, "certificates.signer_name"),
            code=display_code(certificate.verify_code),
            qr=segno.make(url, error="m").svg_data_uri(dark="#14402c", border=0) if url else None,
            revoked=certificate.revoked_at is not None,
        )
    )
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())


async def pdf_bytes(session: AsyncSession, certificate: Certificate) -> bytes:
    """The stored PDF, drawn (and stored) the first time. A revoked one is drawn with a stamp."""
    if certificate.revoked_at is not None:
        return await render_pdf(session, certificate)
    storage = get_storage()
    if certificate.file_key:
        try:
            return await storage.get(certificate.file_key)
        except AppError:
            pass  # lost file (e.g. a rebuilt free server): draw it again
    data = await render_pdf(session, certificate)
    key = f"certificates/{certificate.id}.pdf"
    await storage.put(key, data, "application/pdf")
    certificate.file_key = key
    return data
