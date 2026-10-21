"""The club's own certificate design for an event or a test: an uploaded picture, the text on top.

Who may upload, and until when:
* an administrator who edits events — while announcing the event, until it starts;
* the super administrator — until the event's test is over (the certificates are drawn then).
A test without an event follows the same rule with the test's own start and end.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import UTC, datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError
from app.models import CertificateTemplate, Event, Test
from app.models.enums import TestStatus
from app.services.audit import record_audit
from app.services.storage import get_storage

logger = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024
WIDTH, HEIGHT = 2480, 1754  # A4 landscape at 212 dpi: sharp in print, light enough


def prepare(data: bytes) -> bytes:
    """Check the picture and fit it to an A4 landscape page (JPEG, no metadata)."""
    if not data or len(data) > MAX_BYTES:
        raise BadRequestError("IMAGE_TOO_LARGE", "Rasm 10 MB dan oshmasin.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 60_000_000:
            raise BadRequestError("IMAGE_TOO_LARGE", "Rasm o'lchami juda katta.")
        image.verify()
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise BadRequestError("IMAGE_INVALID", "Rasm faylini tanlang (JPG yoki PNG).") from exc
    if image.height > image.width:
        image = image.rotate(90, expand=True)  # a portrait design is turned to landscape
    image = ImageOps.fit(image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


async def _event_deadline(session: AsyncSession, event: Event, super_admin: bool) -> tuple[bool, str]:
    now = datetime.now(UTC)
    if not super_admin:
        if event.starts_at <= now:
            return False, "Tadbir boshlangan — endi faqat bosh administrator dizaynni o'zgartira oladi."
        return True, ""
    tests = list(await session.scalars(select(Test).where(Test.event_id == event.id, Test.deleted_at.is_(None))))
    if tests and all(test.status == TestStatus.CLOSED for test in tests):
        return False, "Tadbir testi yakunlangan — sertifikatlar allaqachon berilgan."
    if not tests and event.ends_at <= now:
        return False, "Tadbir yakunlangan."
    return True, ""


async def _test_deadline(test: Test, super_admin: bool) -> tuple[bool, str]:
    now = datetime.now(UTC)
    if test.status == TestStatus.CLOSED:
        return False, "Test yakunlangan — sertifikatlar allaqachon berilgan."
    if not super_admin and test.starts_at <= now:
        return False, "Test boshlangan — endi faqat bosh administrator dizaynni o'zgartira oladi."
    return True, ""


async def set_background(
    session: AsyncSession, *, actor_id: uuid.UUID, super_admin: bool, target: Event | Test, data: bytes | None
) -> Event | Test:
    """Upload (``data``) or remove (``None``) the certificate background of an event or a test."""
    if isinstance(target, Event):
        allowed, reason = await _event_deadline(session, target, super_admin)
        kind = "event"
    else:
        allowed, reason = await _test_deadline(target, super_admin)
        kind = "test"
    if not allowed:
        raise ConflictError("BACKGROUND_LOCKED", reason)
    storage = get_storage()
    old = target.certificate_background_key
    key = None
    if data is not None:
        key = f"certificates/backgrounds/{kind}-{target.id}-{uuid.uuid4().hex[:8]}.jpg"
        await storage.put(key, prepare(data), "image/jpeg")
    target.certificate_background_key = key
    if key is not None and isinstance(target, Event):
        # An uploaded image is the one certificate choice: drop any pinned design / saved template.
        target.certificate_design = None
        target.certificate_template_id = None
    record_audit(
        session,
        actor_id=actor_id,
        action="CERTIFICATE_BACKGROUND_SET" if key else "CERTIFICATE_BACKGROUND_REMOVE",
        entity_type=kind,
        entity_id=target.id,
    )
    await session.commit()
    if old and old != key:
        try:
            await storage.delete(old)
        except Exception:  # an orphaned file is harmless
            logger.info("Old certificate background could not be removed")
    return target


async def set_choice(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    super_admin: bool,
    event: Event,
    design: str | None,
    template_id: uuid.UUID | None,
) -> Event:
    """Pick the winners' certificate look: a saved template, a standard design, or neither (next in
    turn). The four options (template / design / uploaded image / next in turn) are mutually exclusive,
    so choosing a template or design also drops any uploaded background image."""
    from app.services import certificate_designs as designs
    from app.services import certificate_templates

    allowed, reason = await _event_deadline(session, event, super_admin)
    if not allowed:
        raise ConflictError("BACKGROUND_LOCKED", reason)
    if template_id is not None:
        event.certificate_template_id = await certificate_templates.ensure_template_for(session, template_id)
        event.certificate_design = None
    elif design is not None:
        if design not in designs.BY_CODE:
            raise BadRequestError("DESIGN_NOT_FOUND", "Bunday dizayn yo'q.")
        event.certificate_design = design
        event.certificate_template_id = None
    else:  # back to the standard rotation
        event.certificate_design = None
        event.certificate_template_id = None
    storage = get_storage()
    old = event.certificate_background_key
    event.certificate_background_key = None
    record_audit(
        session,
        actor_id=actor_id,
        action="CERTIFICATE_CHOICE_SET",
        entity_type="event",
        entity_id=event.id,
        after={"design": event.certificate_design, "template_id": str(template_id) if template_id else None},
    )
    await session.commit()
    if old:
        try:
            await storage.delete(old)
        except Exception:  # an orphaned file is harmless
            logger.info("Old certificate background could not be removed")
    return event


async def preview(session: AsyncSession, target: Event | Test) -> bytes:
    """A sample winners' certificate as a picture — on the saved template, the uploaded background,
    the pinned standard design, or (when none is chosen) the next design in turn."""
    from app.models import Certificate
    from app.models.enums import CertificateKind
    from app.services import certificate_designs as designs
    from app.services import certificate_templates, certificates

    # A saved admin-built template owns the whole page: render it directly.
    template_id = target.certificate_template_id
    if template_id is not None:
        template = await session.get(CertificateTemplate, template_id)
        if template is not None and template.deleted_at is None:
            return await certificate_templates.preview_png(session, template)

    custom = target.certificate_background_key is not None
    pinned = getattr(target, "certificate_design", None)
    last = await session.scalar(
        select(Certificate.design)
        .where(Certificate.design.is_not(None), Certificate.design != designs.CUSTOM)
        .order_by(Certificate.created_at.desc())
        .limit(1)
    )
    if custom:
        design = designs.CUSTOM
    elif pinned in designs.BY_CODE:
        design = pinned
    else:
        design = designs.next_after(last).code
    sample = Certificate(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind=CertificateKind.TEST_PLACE,
        place=1,
        title="Namuna",
        description=f"«{target.title}» bilim testida 1-o'rinni egallagani uchun taqdim etiladi.",
        dedup_key="sample",
        verify_code="NAMUNA2026",
        issued_at=datetime.now(UTC),
        design=design,
        background_key=target.certificate_background_key,
    )
    return await certificates.sample_png(session, sample)
