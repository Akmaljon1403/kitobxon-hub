"""Admin-built certificate designs: an uploaded page (PNG/JPG/PDF) with elements placed on it.

The admin uploads their own design and, in a visual editor, drops the pieces they need (name, QR,
seal, signature, date, …), each with its own position, size, font and colour. The design is drawn
exactly as uploaded — the text sits where the admin put it, so no readability overlay is painted on
top. Rendering reuses the club's PDF pipeline (WeasyPrint): an absolutely-positioned HTML page whose
sheet matches the design's own aspect ratio, so the picture is never stretched or letter-boxed.
"""

from __future__ import annotations

import asyncio
import io
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import segno
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Certificate, CertificateTemplate, User
from app.schemas.certificate import TemplateElement
from app.services.audit import record_audit
from app.services.settings import get_setting
from app.services.storage import get_storage
from app.utils.timezone import format_date

logger = logging.getLogger(__name__)

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 60_000_000
TARGET_PX = 2200  # the prepared design's longer side: crisp in print, light enough to store
LONG_MM = 297.0  # the page's longer side (A4), so a printed certificate is a familiar size

FONT_STACKS: dict[str, str] = {
    "serif": '"Liberation Serif", "Times New Roman", "DejaVu Serif", serif',
    "sans": '"Liberation Sans", "DejaVu Sans", Arial, sans-serif',
    "mono": '"DejaVu Sans Mono", monospace',
}

# (type, label, is_image) — shown in the editor's palette.
ELEMENT_TYPES: tuple[tuple[str, str, bool], ...] = (
    ("name", "Ism familiya", False),
    ("cert_title", "Sertifikat nomi", False),
    ("description", "Asosiy matn", False),
    ("place", "O'rin (1/2/3)", False),
    ("date", "Sana", False),
    ("member_number", "A'zo raqami", False),
    ("organization", "Tashkilot nomi", False),
    ("club", "Klub nomi", False),
    ("signer", "Imzolovchi", False),
    ("code", "Tekshirish kodi", False),
    ("qr", "QR kod", True),
    ("seal", "Muhr", True),
    ("logo", "Logotip", True),
    ("text", "Erkin matn", False),
)
IMAGE_TYPES = frozenset(code for code, _, is_image in ELEMENT_TYPES if is_image)


def default_elements() -> list[dict[str, Any]]:
    """A sensible starting layout the admin then drags into place on their design."""
    return [
        {"type": "name", "x": 15, "y": 42, "w": 70, "size": 30, "font": "serif", "color": "#14402c", "bold": True},
        {"type": "description", "x": 18, "y": 56, "w": 64, "size": 14, "font": "serif", "color": "#1c2b24"},
        {"type": "date", "x": 10, "y": 84, "w": 30, "size": 11, "font": "serif", "align": "left"},
        {"type": "signer", "x": 60, "y": 84, "w": 32, "size": 11, "font": "serif", "align": "right"},
        {"type": "qr", "x": 84, "y": 78, "w": 12},
        {"type": "code", "x": 80, "y": 91, "w": 18, "size": 9, "font": "mono"},
    ]


# ---------------------------------------------------------------------------- the uploaded design


def _prepare_sync(data: bytes) -> tuple[bytes, int, int]:
    """Turn an uploaded PNG/JPG/PDF into one opaque PNG; return (bytes, width, height). CPU-bound."""
    if not data or len(data) > MAX_BYTES:
        raise BadRequestError("DESIGN_TOO_LARGE", "Fayl 15 MB dan oshmasin.")
    if data[:5] == b"%PDF-":
        image = _pdf_first_page(data)
    else:
        try:
            probe = Image.open(io.BytesIO(data))
            if probe.width * probe.height > MAX_PIXELS:
                raise BadRequestError("DESIGN_TOO_LARGE", "Rasm o'lchami juda katta.")
            probe.verify()
            image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        except BadRequestError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise BadRequestError("DESIGN_INVALID", "PNG, JPG yoki PDF faylini tanlang.") from exc
    if image.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", image.size, "#ffffff")  # flatten onto white: a certificate page is opaque
        flat.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
        image = flat
    else:
        image = image.convert("RGB")
    if max(image.size) > TARGET_PX:
        image.thumbnail((TARGET_PX, TARGET_PX), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue(), image.width, image.height


def _pdf_first_page(data: bytes) -> Image.Image:
    import pypdfium2

    try:
        document = pypdfium2.PdfDocument(data)
    except Exception as exc:  # a broken or encrypted PDF
        raise BadRequestError("DESIGN_INVALID", "PDF faylni o'qib bo'lmadi.") from exc
    try:
        page = document[0]
        scale = min(4.0, TARGET_PX / max(1.0, page.get_width()))
        return page.render(scale=scale).to_pil()
    finally:
        document.close()


async def set_background(
    session: AsyncSession, *, template: CertificateTemplate, actor_id: uuid.UUID, data: bytes
) -> None:
    """Replace the template's design picture."""
    prepared, width, height = await asyncio.to_thread(_prepare_sync, data)
    storage = get_storage()
    old = template.background_key
    key = f"certificates/templates/{template.id}-{uuid.uuid4().hex[:8]}.png"
    await storage.put(key, prepared, "image/png")
    template.background_key = key
    template.bg_width = width
    template.bg_height = height
    record_audit(
        session,
        actor_id=actor_id,
        action="CERT_TEMPLATE_BACKGROUND",
        entity_type="certificate_template",
        entity_id=template.id,
    )
    await session.commit()
    if old and old != key:
        try:
            await storage.delete(old)
        except Exception:  # an orphaned file is harmless
            logger.info("Old certificate-template background could not be removed")


async def background_bytes(template: CertificateTemplate) -> bytes:
    if not template.background_key:
        raise NotFoundError("DESIGN_NO_BACKGROUND", "Bu shablonda rasm yo'q.")
    try:
        return await get_storage().get(template.background_key)
    except Exception as exc:
        raise NotFoundError("DESIGN_NO_BACKGROUND", "Rasm topilmadi.") from exc


# ---------------------------------------------------------------------------- CRUD


async def create(
    session: AsyncSession, *, actor_id: uuid.UUID, name: str, elements: list[TemplateElement], is_default: bool
) -> CertificateTemplate:
    template = CertificateTemplate(
        name=name.strip(),
        elements=[element.model_dump() for element in elements] or default_elements(),
        created_by=actor_id,
    )
    session.add(template)
    await session.flush()
    if is_default:
        await _make_default(session, template)
    record_audit(
        session,
        actor_id=actor_id,
        action="CERT_TEMPLATE_CREATE",
        entity_type="certificate_template",
        entity_id=template.id,
        after={"name": template.name},
    )
    await session.commit()
    await session.refresh(template)
    return template


async def update(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    template: CertificateTemplate,
    name: str,
    elements: list[TemplateElement],
    is_default: bool,
) -> CertificateTemplate:
    template.name = name.strip()
    template.elements = [element.model_dump() for element in elements]
    if is_default and not template.is_default:
        await _make_default(session, template)
    elif not is_default and template.is_default:
        template.is_default = False
    record_audit(
        session,
        actor_id=actor_id,
        action="CERT_TEMPLATE_UPDATE",
        entity_type="certificate_template",
        entity_id=template.id,
    )
    await session.commit()
    await session.refresh(template)
    return template


async def _make_default(session: AsyncSession, template: CertificateTemplate) -> None:
    """Only one template is the default; clear the others first (the partial unique index enforces it)."""
    await session.execute(
        sql_update(CertificateTemplate)
        .where(CertificateTemplate.is_default.is_(True), CertificateTemplate.id != template.id)
        .values(is_default=False)
    )
    await session.flush()
    template.is_default = True


async def get(session: AsyncSession, template_id: uuid.UUID) -> CertificateTemplate:
    template = await session.get(CertificateTemplate, template_id)
    if template is None or template.deleted_at is not None:
        raise NotFoundError("CERT_TEMPLATE_NOT_FOUND", "Shablon topilmadi.")
    return template


async def list_templates(session: AsyncSession) -> list[CertificateTemplate]:
    return list(
        await session.scalars(
            select(CertificateTemplate)
            .where(CertificateTemplate.deleted_at.is_(None))
            .order_by(CertificateTemplate.is_default.desc(), CertificateTemplate.updated_at.desc())
        )
    )


async def default_template(session: AsyncSession) -> CertificateTemplate | None:
    return await session.scalar(
        select(CertificateTemplate).where(
            CertificateTemplate.is_default.is_(True), CertificateTemplate.deleted_at.is_(None)
        )
    )


async def delete(session: AsyncSession, *, actor_id: uuid.UUID, template: CertificateTemplate) -> None:
    used = await session.scalar(
        select(func.count()).select_from(Certificate).where(Certificate.template_id == template.id)
    )
    if used:
        # Keep the picture so already-issued certificates still draw; just hide the template from the list.
        template.deleted_at = datetime.now(UTC)
        template.is_default = False
        record_audit(
            session,
            actor_id=actor_id,
            action="CERT_TEMPLATE_HIDE",
            entity_type="certificate_template",
            entity_id=template.id,
        )
        await session.commit()
        return
    key = template.background_key
    record_audit(
        session,
        actor_id=actor_id,
        action="CERT_TEMPLATE_DELETE",
        entity_type="certificate_template",
        entity_id=template.id,
    )
    await session.delete(template)
    await session.commit()
    if key:
        try:
            await get_storage().delete(key)
        except Exception:
            logger.info("Certificate-template background could not be removed")


# ---------------------------------------------------------------------------- rendering


def page_mm(template: CertificateTemplate) -> tuple[float, float]:
    """The page size in millimetres, keeping the design's own aspect ratio."""
    width, height = max(1, template.bg_width), max(1, template.bg_height)
    if width >= height:
        return LONG_MM, round(LONG_MM * height / width, 2)
    return round(LONG_MM * width / height, 2), LONG_MM


async def _values(session: AsyncSession, certificate: Certificate | None) -> dict[str, Any]:
    from app.services import brand, certificates
    from app.services.passport import member_number

    signer = await _signer(session)
    org = await get_setting(session, "org.organization_name")
    club = await get_setting(session, "org.club_name")
    if certificate is not None:
        user = await session.get(User, certificate.user_id)
        assert user is not None
        name = f"{user.last_name} {user.first_name}"
        number = member_number(user)
        code = certificates.display_code(certificate.verify_code)
        url = certificates.verify_url(certificate.verify_code)
        description = certificate.description
        title = certificate.title
        place = certificate.place
        issued_on = format_date(certificate.issued_at)
        revoked = certificate.revoked_at is not None
    else:  # a made-up certificate for the admin's preview
        name = "Karimova Aziza"
        number = "KH-000042"
        code = "NAMUNA-2026"
        url = "https://example.org/v/NAMUNA2026"
        description = "«O'tkan kunlar» bilim testida 1-o'rinni egallagani uchun taqdim etiladi."
        title = "«O'tkan kunlar» testi — 1-o'rin"
        place = 1
        issued_on = format_date(datetime.now(UTC))
        revoked = False
    qr = segno.make(url, error="m").svg_data_uri(dark="#14402c", border=0) if url else None
    return {
        "text": {
            "name": name,
            "cert_title": title,
            "description": description,
            "place": f"{place}-o'rin" if place else "",
            "date": issued_on,
            "member_number": f"A'zo № {number}",
            "organization": org or "",
            "club": club or "",
            "signer": signer,
            "code": code,
        },
        "qr": qr,
        "seal": {variant: brand.seal(True, _paper(variant)) for variant in ("auto", "light", "dark")},
        "logo": {variant: brand.logo_mark(_paper(variant)) for variant in ("auto", "light", "dark")},
        "revoked": revoked,
    }


def _paper(variant: str) -> str:
    """The notional paper colour behind a seal/logo: «dark» design → a light mark is chosen."""
    return "#111111" if variant == "dark" else "#ffffff"


async def _signer(session: AsyncSession) -> str:
    from app.services import signing

    signer = await signing.signer(session)
    return signer.title + (f" — {signer.name}" if signer.name else "")


def _prepare_elements(template: CertificateTemplate, values: dict[str, Any]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for raw in template.elements or []:
        try:
            element = TemplateElement.model_validate(raw)
        except Exception:  # noqa: S112 — a stray element from an older save: skip it, don't fail the PDF
            continue
        if element.type in IMAGE_TYPES:
            src = values["qr"] if element.type == "qr" else values[element.type].get(element.variant)
            if not src:
                continue
            prepared.append({"image": True, "x": element.x, "y": element.y, "w": element.w, "src": src})
        else:
            value = element.content if element.type == "text" else values["text"].get(element.type, "")
            if not value:
                continue
            prepared.append(
                {
                    "image": False,
                    "x": element.x,
                    "y": element.y,
                    "w": element.w,
                    "value": value,
                    "font": FONT_STACKS.get(element.font, FONT_STACKS["serif"]),
                    "size": element.size,
                    "color": element.color,
                    "align": element.align,
                    "weight": "bold" if element.bold else "normal",
                    "style": "italic" if element.italic else "normal",
                }
            )
    return prepared


async def render_pdf(
    session: AsyncSession, template: CertificateTemplate, *, certificate: Certificate | None = None
) -> bytes:
    from weasyprint import HTML

    from app.services.report_pdf import TEMPLATES, _environment

    values = await _values(session, certificate)
    width_mm, height_mm = page_mm(template)
    background = None
    if template.background_key:
        try:
            from app.services import certificate_designs as designs

            background = designs.image_uri(await get_storage().get(template.background_key), "image/png")
        except Exception:
            background = None  # the picture is gone: draw a plain page so the text still comes out
    html = (
        _environment()
        .get_template("certificate_custom.html")
        .render(
            width_mm=width_mm,
            height_mm=height_mm,
            background=background,
            elements=_prepare_elements(template, values),
            revoked=values["revoked"],
        )
    )
    return await asyncio.to_thread(lambda: HTML(string=html, base_url=str(TEMPLATES)).write_pdf())


async def preview_png(
    session: AsyncSession, template: CertificateTemplate, *, width: int = 1400, certificate: Certificate | None = None
) -> bytes:
    """A picture of the design (no «ko'rish uchun» overlay — what the admin builds is what prints)."""
    from app.services.certificates import _to_png

    pdf = await render_pdf(session, template, certificate=certificate)
    return await asyncio.to_thread(_to_png, pdf, width=width, watermark=False)


async def ensure_template_for(session: AsyncSession, template_id: uuid.UUID | None) -> uuid.UUID | None:
    """Validate a chosen template id (for a test, event or manual issue); None when absent or gone."""
    if template_id is None:
        return None
    template = await session.get(CertificateTemplate, template_id)
    if template is None or template.deleted_at is not None:
        raise NotFoundError("CERT_TEMPLATE_NOT_FOUND", "Tanlangan shablon topilmadi.")
    return template.id


def guard_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ConflictError("CERT_TEMPLATE_NAME", "Shablon nomini kiriting.")
    return cleaned
