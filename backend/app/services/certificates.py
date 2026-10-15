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
from app.models import AttendanceRecord, Certificate, CertificateTemplate, Event, Test, User
from app.models.enums import AttendanceStatus, CertificateKind, FeatureMode, NotificationType
from app.services import certificate_designs as designs
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


async def _design_for(
    session: AsyncSession, *, test_id: uuid.UUID | None, event_id: uuid.UUID | None, period: str | None
) -> tuple[str, str | None]:
    """(design, background_key): the club's own background for the event/test if one was uploaded;
    else the design already used for the same test or month, else the next one in turn."""
    test = await session.get(Test, test_id) if test_id else None
    event = await session.get(Event, event_id) if event_id else None
    background = (test.certificate_background_key if test else None) or (
        event.certificate_background_key if event else None
    )
    if background:
        return designs.CUSTOM, background
    batch = None
    if test_id is not None:
        batch = Certificate.test_id == test_id
    elif period is not None:
        batch = Certificate.period == period
    if batch is not None:
        same = await session.scalar(select(Certificate.design).where(batch, Certificate.design.is_not(None)).limit(1))
        if same:
            return same, None
    last = await session.scalar(
        select(Certificate.design)
        .where(Certificate.design.is_not(None), Certificate.design != designs.CUSTOM)
        .order_by(Certificate.created_at.desc())
        .limit(1)
    )
    return designs.next_after(last).code, None


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
    template_id: uuid.UUID | None = None,
    gift_message: str | None = None,
) -> Certificate | None:
    """Create a certificate and tell the member (it is seen and downloaded in the Mini App).
    With ``template_id`` an admin-built design is used; with ``gift_message`` the PDF is sent
    together with the admin's personal note. Returns None if it already exists."""
    if template_id is not None:
        design, background = None, None  # the template owns the whole page
    else:
        design, background = await _design_for(session, test_id=test_id, event_id=event_id, period=period)
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
            design=design,
            background_key=background,
            template_id=template_id,
        )
        .on_conflict_do_nothing(index_elements=[Certificate.dedup_key])
        .returning(Certificate.id)
    )
    if new_id is None:
        return None
    certificate = await session.get(Certificate, new_id)
    assert certificate is not None
    link = verify_url(certificate.verify_code)
    button = {"text": "🎓 Sertifikatni ko'rish", "app_route": f"certificates/{certificate.id}"}
    if gift_message:
        # A gift: the PDF itself is delivered together with the admin's personal message.
        text = gift_message.strip()
        payload = {"buttons": [button], "mood": "CELEBRATE", "certificate_id": str(certificate.id)}
    else:
        details = f"Tekshirish kodi: {display_code(certificate.verify_code)}"
        details += "\n\n📱 Sertifikatingizni ilovada ko'ring" + (
            f"; uning haqiqiyligini istalgan kishi shu havola orqali tekshiradi: {link}" if link else "."
        )
        text = await render(session, NotificationType.CERTIFICATE, title=title, details=details)
        payload = {"buttons": [button], "mood": "CELEBRATE"}
    if text:
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


async def _attended(session: AsyncSession, event_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        await session.scalars(
            select(AttendanceRecord.user_id).where(
                AttendanceRecord.event_id == event_id, AttendanceRecord.status == AttendanceStatus.VERIFIED
            )
        )
    )


def _test_template_id(test: Test, event: Event | None) -> uuid.UUID | None:
    """The admin-built design chosen for this test (its own, else the event's)."""
    return test.certificate_template_id or (event.certificate_template_id if event else None)


async def issue_for_test(session: AsyncSession, test: Test, standings: list[dict[str, Any]]) -> int:
    """Places 1-3 of a closed test, plus a completion certificate for every passer when the test asks
    for it (``certificate_on_pass``). The caller commits."""
    if not await get_setting(session, "certificates.test_winners"):
        return 0
    event = await session.get(Event, test.event_id) if test.event_id else None
    template_id = _test_template_id(test, event)
    if template_id is None:
        from app.services import certificate_templates

        default = await certificate_templates.default_template(session)
        template_id = default.id if default else None
    winners = standings
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
            template_id=template_id,
        )
        issued += 1 if created else 0
    issued += await issue_for_passers(session, test, standings, event=event, template_id=template_id)
    return issued


async def issue_for_passers(
    session: AsyncSession,
    test: Test,
    standings: list[dict[str, Any]],
    *,
    event: Event | None = None,
    template_id: uuid.UUID | None = None,
) -> int:
    """A completion certificate for everybody who passed the test (``certificate_on_pass``). ``standings``
    already contains only members whose score reached ``passing_score`` (an event's test: attendees only)."""
    if not test.certificate_on_pass:
        return 0
    passers = standings
    if event is not None:
        present = await _attended(session, event.id)
        passers = [row for row in standings if row["user_id"] in present]
    title = f"«{test.title}» — ishtirok sertifikati"
    issued = 0
    for row in passers:
        created = await issue(
            session,
            user_id=row["user_id"],
            kind=CertificateKind.COMPLETION,
            place=None,
            title=title,
            description=f"«{test.title}» bilim testini muvaffaqiyatli topshirgani uchun taqdim etiladi.",
            dedup_key=f"testpass:{test.id}:{row['user_id']}",
            test_id=test.id,
            event_id=event.id if event else None,
            template_id=template_id,
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
    from app.services import certificate_templates

    default = await certificate_templates.default_template(session)
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
            template_id=default.id if default else None,
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
    template_id: uuid.UUID | None = None,
    gift_message: str | None = None,
) -> Certificate:
    """By hand from the panel: a plain certificate, or a gift with a chosen design and a personal note."""
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    if template_id is not None:
        from app.services import certificate_templates

        template_id = await certificate_templates.ensure_template_for(session, template_id)
    certificate = await issue(
        session,
        user_id=user_id,
        kind=CertificateKind.MANUAL,
        place=place,
        title=title,
        description=description,
        dedup_key=f"manual:{uuid.uuid4()}",
        issued_by=actor_id,
        template_id=template_id,
        gift_message=gift_message,
    )
    assert certificate is not None
    record_audit(
        session,
        actor_id=actor_id,
        action="CERTIFICATE_ISSUE",
        entity_type="certificate",
        entity_id=certificate.id,
        after={"user_id": str(user_id), "title": title, "place": place, "gift": bool(gift_message)},
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


async def _template_values(session: AsyncSession, certificate: Certificate, design: str | None) -> dict[str, Any]:
    from app.services.passport import member_number

    user = await session.get(User, certificate.user_id)
    assert user is not None
    url = verify_url(certificate.verify_code)
    code = design or certificate.design
    custom = code == designs.CUSTOM and certificate.background_key is not None
    background = None
    if custom:
        try:
            background = designs.image_uri(await get_storage().get(certificate.background_key or ""))
        except AppError:
            custom = False  # the uploaded picture is gone: a standard design instead
    chosen = designs.get(None if custom else code)
    palette = designs.CUSTOM_PALETTE if custom else chosen.palette
    return {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "name": f"{user.last_name} {user.first_name}",
        "place": certificate.place,
        "description": certificate.description,
        "issued_on": format_date(certificate.issued_at),
        "number": member_number(user),
        **await _signer_values(session),
        "code": display_code(certificate.verify_code),
        "qr": segno.make(url, error="m").svg_data_uri(dark="#14402c", border=0) if url else None,
        "revoked": certificate.revoked_at is not None,
        "design": designs.CUSTOM if custom else chosen.code,
        "custom": custom,
        "background": background or chosen.background_uri(),
        "p": palette,
        **await _brand_values(session, palette.paper),
    }


async def _signer_values(session: AsyncSession) -> dict[str, Any]:
    """«Klub rahbari» and the leader's name — the owner's when the setting is empty (see services/signing)."""
    from app.services import signing

    signer = await signing.signer(session)
    return {"signer_title": signer.title, "signer_name": signer.name}


async def _brand_values(session: AsyncSession, paper: str) -> dict[str, Any]:
    """The club's seal over the signature and its mark above the title (see services/brand.py)."""
    from app.services import brand

    return {
        "seal": brand.seal(bool(await get_setting(session, "certificates.seal")), paper),
        "logo": brand.logo_mark(paper) if await get_setting(session, "certificates.logo") else None,
    }


async def render_pdf(session: AsyncSession, certificate: Certificate, design: str | None = None) -> bytes:
    from weasyprint import HTML  # heavy import, only when a PDF is needed

    from app.services.report_pdf import TEMPLATES, _environment

    # An admin-built design takes over the whole page (no fixed layout, no readability overlay).
    if certificate.template_id is not None:
        template = await session.get(CertificateTemplate, certificate.template_id)
        if template is not None and template.deleted_at is None:
            from app.services import certificate_templates

            return await certificate_templates.render_pdf(session, template, certificate=certificate)

    values = await _template_values(session, certificate, design)
    html = _environment().get_template("certificate.html").render(**values)
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())


def _to_png(pdf: bytes, *, width: int, watermark: bool) -> bytes:
    """The first page as a PNG (for previews in the app); ``watermark`` marks it «ko'rish uchun»."""
    import io

    import pypdfium2
    from PIL import Image, ImageDraw, ImageFont

    document = pypdfium2.PdfDocument(pdf)
    try:
        page = document[0]
        scale = width / page.get_width()
        image = page.render(scale=scale).to_pil().convert("RGB")
    finally:
        document.close()
    if watermark:
        layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", max(18, image.width // 24))
        except OSError:
            font = ImageFont.load_default()
        text = "KO'RISH UCHUN NUSXA"
        box = draw.textbbox((0, 0), text, font=font)
        tile = Image.new("RGBA", (box[2] + 40, box[3] + 30), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((20, 10), text, font=font, fill=(150, 150, 150, 70))
        tile = tile.rotate(18, expand=True)
        for y in range(-tile.height, image.height, tile.height + image.height // 6):
            for x in range(-tile.width // 2, image.width, tile.width + 30):
                layer.alpha_composite(tile, (x, y))
        image = Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


async def preview_png(session: AsyncSession, certificate: Certificate, design: str | None = None) -> bytes:
    """What the member sees in the app (free): a picture with a «ko'rish uchun» mark."""
    pdf = await render_pdf(session, certificate, design)
    return await asyncio.to_thread(_to_png, pdf, width=1200, watermark=True)


async def sample_png(session: AsyncSession, sample: Certificate, *, width: int = 1000) -> bytes:
    """A made-up certificate (for design pictures and the admins' preview of a background)."""
    from weasyprint import HTML

    from app.services.report_pdf import TEMPLATES, _environment

    custom = sample.design == designs.CUSTOM and sample.background_key is not None
    background = None
    if custom:
        try:
            background = designs.image_uri(await get_storage().get(sample.background_key or ""))
        except AppError:
            custom = False
    chosen = designs.get(None if custom else sample.design)
    values = {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "name": "Karimova Aziza",
        "place": sample.place,
        "description": sample.description,
        "issued_on": format_date(sample.issued_at),
        "number": "KH-000042",
        **await _signer_values(session),
        "code": display_code(sample.verify_code),
        "qr": segno.make("https://example.org/v/NAMUNA2026", error="m").svg_data_uri(dark="#14402c", border=0),
        "revoked": False,
        "design": designs.CUSTOM if custom else chosen.code,
        "custom": custom,
        "background": background or chosen.background_uri(),
        "p": designs.CUSTOM_PALETTE if custom else chosen.palette,
    }
    values |= await _brand_values(session, values["p"].paper)
    html = _environment().get_template("certificate.html").render(**values)
    pdf = await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())
    return await asyncio.to_thread(_to_png, pdf, width=width, watermark=False)


async def design_thumbnail(session: AsyncSession, code: str) -> bytes:
    """A small sample of a design (cached in storage)."""
    storage = get_storage()
    key = f"certificates/designs/{code}-v1.png"
    try:
        return await storage.get(key)
    except AppError:
        pass
    sample = Certificate(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind=CertificateKind.MANUAL,
        place=1,
        title="Namuna",
        description="«O'tkan kunlar» bilim testida 1-o'rinni egallagani uchun taqdim etiladi.",
        dedup_key="sample",
        verify_code="NAMUNA2026",
        issued_at=datetime.now(UTC),
        design=code,
    )
    image = await sample_png(session, sample, width=420)
    await storage.put(key, image, "image/png")
    return image


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
    suffix = f"tpl-{certificate.template_id}" if certificate.template_id else (certificate.design or "classic")
    key = f"certificates/{certificate.id}-{suffix}.pdf"
    await storage.put(key, data, "application/pdf")
    certificate.file_key = key
    return data


# ---------------------------------------------------------------------------- the member's copy


async def access(session: AsyncSession, user: User, certificate: Certificate) -> dict[str, Any]:
    """What the member may do with their certificate: download (Premium: always; otherwise a few free
    downloads) and change its design (Premium, a few times)."""
    from app.services import features
    from app.services.premium import is_premium

    mode = await features.mode(session, "certificate_pdf")
    premium = await is_premium(session, user.id)
    free = int(await get_setting(session, "certificates.free_downloads"))
    changes = int(await get_setting(session, "certificates.design_changes"))
    if mode == FeatureMode.OFF:
        can_download, left = False, 0
    elif mode == FeatureMode.ALL or premium:
        can_download, left = True, None
    else:
        left = max(free - certificate.downloads, 0)
        can_download = left > 0
    return {
        "can_download": can_download,
        "downloads_left": left,
        "premium": premium,
        "can_change_design": premium and certificate.design_changes < changes,
        "design_changes_left": max(changes - certificate.design_changes, 0) if premium else 0,
    }


async def take_download(session: AsyncSession, user: User, certificate: Certificate) -> None:
    """Count a download (or refuse it): the PDF itself is fetched or sent right after."""
    rights = await access(session, user, certificate)
    if not rights["can_download"]:
        from app.services.features import PremiumRequiredError, get_feature

        raise PremiumRequiredError(get_feature("certificate_pdf"))
    if rights["downloads_left"] is not None:
        certificate.downloads += 1
    await session.commit()


async def change_design(session: AsyncSession, user: User, certificate: Certificate, design: str) -> Certificate:
    if design not in designs.BY_CODE and not (design == designs.CUSTOM and certificate.background_key):
        raise NotFoundError("DESIGN_NOT_FOUND", "Bunday dizayn yo'q.")
    if design == certificate.design:
        return certificate
    rights = await access(session, user, certificate)
    if not rights["premium"]:
        from app.services.features import PremiumRequiredError, get_feature

        raise PremiumRequiredError(get_feature("certificate_pdf"))
    if not rights["can_change_design"]:
        raise ConflictError("DESIGN_LIMIT", "Bu sertifikat dizaynini almashtirish imkoniyati tugadi.")
    certificate.design = design
    certificate.design_changes += 1
    certificate.file_key = None  # drawn again in the new design (same number and check code)
    await session.commit()
    return certificate


def design_list(certificate: Certificate | None = None) -> list[dict[str, str]]:
    items = [{"code": design.code, "title": design.title} for design in designs.DESIGNS]
    if certificate is not None and certificate.background_key:
        items.insert(0, {"code": designs.CUSTOM, "title": "Klub dizayni"})
    return items
