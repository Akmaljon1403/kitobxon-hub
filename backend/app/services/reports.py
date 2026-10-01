"""Official event reports: facts from the database, admin text, optional AI wording, approval, PDF.

The rule that keeps reports honest: every fact (dates, places, names, counts, percentages)
comes from ``facts_snapshot`` — loaded by SQL when the report is prepared — or from what the
admin typed. A draft (written by AI, by the built-in template or by hand) may only contain
numbers found there; ``number_issues`` lists any other number and approval is refused until
the admin fixes the text. The statistics tables in the PDF are always rendered from the
snapshot, never from the draft.
"""

from __future__ import annotations

import io
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    Book,
    Event,
    EventRegistration,
    Faculty,
    Report,
    ReportPhoto,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import AttemptStatus, AttendanceStatus, RegistrationStatus, ReportStatus
from app.services.audit import record_audit
from app.services.settings import get_setting
from app.services.storage import get_storage
from app.utils.timezone import MONTHS_UZ, to_local

EDITABLE_STATUSES = (ReportStatus.DRAFT, ReportStatus.AI_GENERATED, ReportStatus.REVIEW)
FINAL_STATUSES = (ReportStatus.APPROVED, ReportStatus.PDF_GENERATED, ReportStatus.ARCHIVED)
ADMIN_FIELDS = ("title", "objective", "activity_description", "results", "conclusion", "recommendations")
MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 8 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _uz_date(value: datetime) -> str:
    local = to_local(value)
    return f"{local.year}-yil {local.day}-{MONTHS_UZ[local.month - 1]}"


async def get_report(session: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await session.get(Report, report_id)
    if report is None:
        raise NotFoundError("REPORT_NOT_FOUND", "Hisobot topilmadi.")
    return report


# ---------------------------------------------------------------------------- facts


async def build_facts(session: AsyncSession, event: Event) -> dict[str, Any]:
    """Everything factual the report may say, loaded from the database right now."""
    book = await session.get(Book, event.book_id) if event.book_id else None
    responsible_id = event.responsible_admin_id or event.created_by
    responsible = await session.get(User, responsible_id) if responsible_id else None

    registered_ids = set(
        await session.scalars(
            select(EventRegistration.user_id).where(
                EventRegistration.event_id == event.id, EventRegistration.status == RegistrationStatus.REGISTERED
            )
        )
    )
    attended_rows = (
        await session.execute(
            select(AttendanceRecord.user_id, AttendanceRecord.status, Faculty.name, User.course)
            .join(User, User.id == AttendanceRecord.user_id)
            .outerjoin(Faculty, Faculty.id == User.faculty_id)
            .where(AttendanceRecord.event_id == event.id, AttendanceRecord.status != AttendanceStatus.REVOKED)
        )
    ).all()
    verified = [row for row in attended_rows if row.status == AttendanceStatus.VERIFIED]
    attended_ids = {row.user_id for row in verified}
    by_faculty: dict[str, int] = {}
    by_course: dict[int, int] = {}
    for row in verified:
        by_faculty[row.name or "Ko'rsatilmagan"] = by_faculty.get(row.name or "Ko'rsatilmagan", 0) + 1
        if row.course:
            by_course[row.course] = by_course.get(row.course, 0) + 1
    attended_registered = len(attended_ids & registered_ids)

    tests = []
    test_conditions = [Test.event_id == event.id]
    if event.book_id:
        test_conditions.append(Test.book_id == event.book_id)
    for test in await session.scalars(
        select(Test).where(Test.deleted_at.is_(None), or_(*test_conditions)).order_by(Test.starts_at)
    ):
        stats = (
            await session.execute(
                select(
                    func.count(func.distinct(TestAttempt.user_id)),
                    func.avg(TestAttempt.score),
                    func.count(func.distinct(TestAttempt.user_id)).filter(
                        TestAttempt.score > 0, TestAttempt.score >= test.passing_score
                    ),
                ).where(
                    TestAttempt.test_id == test.id,
                    TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
                )
            )
        ).one()
        participants, average, passed = stats
        if participants:
            tests.append(
                {
                    "title": test.title,
                    "participants": int(participants),
                    "average_score": round(float(average or 0), 1),
                    "max_score": test.max_score,
                    "passed": int(passed or 0),
                }
            )

    starts = to_local(event.starts_at)
    ends = to_local(event.ends_at)
    return {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "event": {
            "title": event.title,
            "date": _uz_date(event.starts_at),
            "time": f"{starts:%H:%M}–{ends:%H:%M}",
            "location": event.location,
            "book_title": book.title if book else None,
            "book_author": book.author if book else None,
            "responsible": f"{responsible.first_name} {responsible.last_name}" if responsible else None,
        },
        "attendance": {
            "registered": len(registered_ids),
            "attended": len(attended_ids),
            "attended_registered": attended_registered,
            "walk_ins": len(attended_ids - registered_ids),
            "rate_percent": round(attended_registered / len(registered_ids) * 100, 1) if registered_ids else None,
            "suspicious": sum(1 for row in attended_rows if row.status == AttendanceStatus.SUSPICIOUS),
        },
        "faculties": [{"name": name, "attended": count} for name, count in sorted(by_faculty.items())],
        "courses": [{"course": course, "attended": count} for course, count in sorted(by_course.items())],
        "tests": tests,
        "prepared_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------- number check

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers_in(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            found |= _numbers_in(item)
    elif isinstance(value, list):
        for item in value:
            found |= _numbers_in(item)
    elif isinstance(value, bool) or value is None:
        pass
    elif isinstance(value, int | float):
        number = float(value)
        found.add(str(int(number)) if number.is_integer() else f"{number:g}")
        if not number.is_integer():
            found.add(f"{number:g}".replace(".", ","))
    elif isinstance(value, str):
        for match in _NUMBER.findall(value):
            found.add(_normalize(match))
    return found


def _normalize(number: str) -> str:
    value = float(number.replace(",", "."))
    return str(int(value)) if value.is_integer() else f"{value:g}"


def allowed_numbers(report: Report) -> set[str]:
    allowed = _numbers_in(report.facts_snapshot or {})
    for field in ADMIN_FIELDS:
        allowed |= _numbers_in(getattr(report, field))
    return allowed


def number_issues(report: Report) -> list[str]:
    """Numbers in the draft that are neither database facts nor typed by the admin."""
    if not report.body_text:
        return []
    allowed = allowed_numbers(report)
    unknown = []
    for match in _NUMBER.findall(report.body_text):
        normalized = _normalize(match)
        if normalized not in allowed and match not in unknown:
            unknown.append(match)
    return unknown


# ---------------------------------------------------------------------------- template draft


def template_draft(report: Report) -> str:
    """A formal draft built only from facts and admin text (used when AI is not configured)."""
    facts = report.facts_snapshot or {}
    event = facts.get("event", {})
    attendance = facts.get("attendance", {})
    parts: list[str] = ["## Kirish"]
    intro = f"{event.get('date')} kuni"
    if event.get("location"):
        intro += f" {event['location']}da"
    intro += f" {facts.get('club')} tomonidan «{event.get('title')}» tadbiri bo'lib o'tdi."
    if event.get("book_title"):
        intro += f" Tadbir {event.get('book_author')}ning «{event['book_title']}» asariga bag'ishlandi."
    parts.append(intro)
    if report.objective:
        parts.append(f"Tadbirning maqsadi: {report.objective.strip()}")
    parts.append("## Tadbirning borishi")
    parts.append(
        report.activity_description.strip() if report.activity_description else "Tadbir reja asosida o'tkazildi."
    )
    parts.append("## Ishtirok")
    sentence = f"Tadbirda jami {attendance.get('attended', 0)} nafar kitobxon ishtirok etdi."
    if attendance.get("registered"):
        sentence += (
            f" Oldindan {attendance['registered']} nafar a'zo ro'yxatdan o'tgan bo'lib,"
            f" ulardan {attendance.get('attended_registered', 0)} nafari qatnashdi"
            f" ({attendance.get('rate_percent')} foiz)."
        )
    parts.append(sentence)
    faculties = facts.get("faculties") or []
    if faculties:
        listed = ", ".join(f"{row['name']} — {row['attended']} nafar" for row in faculties)
        parts.append(f"Fakultetlar kesimida: {listed}.")
    for test in facts.get("tests") or []:
        parts.append(
            f"«{test['title']}» testida {test['participants']} nafar a'zo qatnashdi, o'rtacha natija"
            f" {test['average_score']} ball ({test['max_score']} balldan)."
        )
    if report.results:
        parts += ["## Natijalar", report.results.strip()]
    if report.conclusion:
        parts += ["## Xulosa", report.conclusion.strip()]
    if report.recommendations:
        parts += ["## Takliflar", report.recommendations.strip()]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------- lifecycle


def _snapshot(report: Report) -> dict[str, Any]:
    return {"status": str(report.status), "version": report.version, "title": report.title}


async def list_reports(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[tuple[Report, str]], int]:
    total = await session.scalar(select(func.count()).select_from(Report))
    rows = await session.execute(
        select(Report, Event.title)
        .join(Event, Event.id == Report.event_id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(report, title) for report, title in rows], int(total or 0)


async def create_report(session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID) -> Report:
    event = await session.get(Event, event_id)
    if event is None or event.deleted_at is not None:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    version = (
        int(
            await session.scalar(select(func.coalesce(func.max(Report.version), 0)).where(Report.event_id == event.id))
            or 0
        )
        + 1
    )
    report = Report(
        event_id=event.id,
        version=version,
        status=ReportStatus.DRAFT,
        title=f"«{event.title}» tadbiri bo'yicha hisobot",
        facts_snapshot=await build_facts(session, event),
        created_by=actor_id,
    )
    session.add(report)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="REPORT_CREATE",
        entity_type="report",
        entity_id=report.id,
        after=_snapshot(report),
    )
    await session.commit()
    return report


def _ensure_editable(report: Report) -> None:
    if report.status not in EDITABLE_STATUSES:
        raise ConflictError("REPORT_LOCKED", "Tasdiqlangan hisobotni o'zgartirib bo'lmaydi. Yangi versiya yarating.")


async def update_report(
    session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID, changes: dict[str, Any]
) -> Report:
    report = await get_report(session, report_id)
    _ensure_editable(report)
    for field in (*ADMIN_FIELDS, "body_text"):
        if field in changes:
            value = changes[field]
            setattr(report, field, value.strip() if isinstance(value, str) and value.strip() else (value or None))
    if "body_text" in changes:
        report.status = ReportStatus.REVIEW if report.body_text else ReportStatus.DRAFT
    record_audit(
        session,
        actor_id=actor_id,
        action="REPORT_UPDATE",
        entity_type="report",
        entity_id=report.id,
        after={"fields": sorted(changes)},
    )
    await session.commit()
    return report


async def refresh_facts(session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = await get_report(session, report_id)
    _ensure_editable(report)
    event = await session.get(Event, report.event_id)
    assert event is not None
    report.facts_snapshot = await build_facts(session, event)
    record_audit(session, actor_id=actor_id, action="REPORT_REFRESH_FACTS", entity_type="report", entity_id=report.id)
    await session.commit()
    return report


async def draft(session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID, use_ai: bool) -> Report:
    """Write the draft text with AI (if configured and requested) or with the built-in template."""
    from app.services import report_ai

    report = await get_report(session, report_id)
    _ensure_editable(report)
    if use_ai:
        result = await report_ai.draft_report(report)
        report.body_text = result.text
        report.ai_model = result.model
        report.ai_generated_at = datetime.now(UTC)
        report.status = ReportStatus.AI_GENERATED
        action = "REPORT_AI_DRAFT"
    else:
        report.body_text = template_draft(report)
        report.status = ReportStatus.REVIEW
        action = "REPORT_TEMPLATE_DRAFT"
    record_audit(
        session,
        actor_id=actor_id,
        action=action,
        entity_type="report",
        entity_id=report.id,
        after={"model": report.ai_model} if use_ai else None,
    )
    await session.commit()
    return report


async def approve(session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = await get_report(session, report_id)
    if report.status not in (ReportStatus.AI_GENERATED, ReportStatus.REVIEW):
        raise ConflictError("REPORT_NOT_READY", "Avval hisobot matnini tayyorlang.")
    if not report.body_text:
        raise BadRequestError("REPORT_EMPTY", "Hisobot matni bo'sh.")
    issues = number_issues(report)
    if issues:
        raise BadRequestError(
            "REPORT_UNVERIFIED_NUMBERS",
            "Matnda bazada yo'q raqamlar bor. Ularni tuzating yoki o'zingiz kiritgan maydonlarga yozing.",
            details={"numbers": issues},
        )
    report.status = ReportStatus.APPROVED
    report.approved_by = actor_id
    report.approved_at = datetime.now(UTC)
    record_audit(
        session,
        actor_id=actor_id,
        action="REPORT_APPROVE",
        entity_type="report",
        entity_id=report.id,
        after=_snapshot(report),
    )
    await session.commit()
    await store_pdf(session, report)
    return report


async def store_pdf(session: AsyncSession, report: Report) -> bytes:
    """Render the official PDF and keep it in storage (also used to rebuild a lost file)."""
    from app.services.report_pdf import render_report_pdf

    pdf = await render_report_pdf(session, report, draft=False)
    key = report.pdf_object_key or f"reports/{report.event_id}/{report.id}-v{report.version}.pdf"
    await get_storage().put(key, pdf, "application/pdf")
    report.pdf_object_key = key
    report.pdf_generated_at = datetime.now(UTC)
    if report.status == ReportStatus.APPROVED:
        report.status = ReportStatus.PDF_GENERATED
    record_audit(
        session, actor_id=None, action="REPORT_PDF", entity_type="report", entity_id=report.id, after={"key": key}
    )
    await session.commit()
    return pdf


async def pdf_bytes(session: AsyncSession, report: Report) -> bytes:
    if report.status not in FINAL_STATUSES:
        raise ConflictError("REPORT_NOT_APPROVED", "Rasmiy PDF hisobot tasdiqlangandan keyin tayyorlanadi.")
    storage = get_storage()
    if report.pdf_object_key and await storage.exists(report.pdf_object_key):
        return await storage.get(report.pdf_object_key)
    return await store_pdf(session, report)


async def archive(session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = await get_report(session, report_id)
    if report.status not in (ReportStatus.APPROVED, ReportStatus.PDF_GENERATED):
        raise ConflictError("REPORT_NOT_APPROVED", "Faqat tasdiqlangan hisobotni arxivlash mumkin.")
    report.status = ReportStatus.ARCHIVED
    report.archived_at = datetime.now(UTC)
    record_audit(session, actor_id=actor_id, action="REPORT_ARCHIVE", entity_type="report", entity_id=report.id)
    await session.commit()
    return report


async def new_version(session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    """Start a corrected version of an approved report (the approved one stays unchanged)."""
    source = await get_report(session, report_id)
    report = await create_report(session, actor_id=actor_id, event_id=source.event_id)
    for field in (*ADMIN_FIELDS, "body_text"):
        setattr(report, field, getattr(source, field))
    report.status = ReportStatus.REVIEW if report.body_text else ReportStatus.DRAFT
    await session.commit()
    return report


# ---------------------------------------------------------------------------- photos


def _process_photo(data: bytes) -> bytes:
    """Validate an image, drop its metadata (e.g. GPS) and shrink it for the PDF."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise BadRequestError("PHOTO_INVALID", "Fayl rasm emas yoki buzilgan.") from exc
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1600, 1600))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()


async def add_photo(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    report_id: uuid.UUID,
    data: bytes,
    content_type: str,
    caption: str | None,
) -> ReportPhoto:
    import asyncio

    report = await get_report(session, report_id)
    _ensure_editable(report)
    if content_type not in PHOTO_TYPES:
        raise BadRequestError("PHOTO_TYPE", "Faqat JPG, PNG yoki WEBP rasm yuklash mumkin.")
    if len(data) > MAX_PHOTO_BYTES:
        raise BadRequestError("PHOTO_TOO_LARGE", "Rasm hajmi 8 MB dan oshmasligi kerak.")
    count = await session.scalar(
        select(func.count()).select_from(ReportPhoto).where(ReportPhoto.report_id == report.id)
    )
    if (count or 0) >= MAX_PHOTOS:
        raise BadRequestError("PHOTO_LIMIT", f"Bitta hisobotga ko'pi bilan {MAX_PHOTOS} ta rasm qo'shiladi.")
    processed = await asyncio.to_thread(_process_photo, data)
    key = f"reports/{report.event_id}/photos/{uuid.uuid4()}.jpg"
    await get_storage().put(key, processed, "image/jpeg")
    photo = ReportPhoto(
        report_id=report.id,
        object_key=key,
        content_type="image/jpeg",
        size_bytes=len(processed),
        caption=caption.strip() if caption and caption.strip() else None,
        sort_order=int(count or 0),
        uploaded_by=actor_id,
    )
    session.add(photo)
    record_audit(session, actor_id=actor_id, action="REPORT_PHOTO_ADD", entity_type="report", entity_id=report.id)
    await session.commit()
    return photo


async def list_photos(session: AsyncSession, report_id: uuid.UUID) -> list[ReportPhoto]:
    return list(
        await session.scalars(
            select(ReportPhoto)
            .where(ReportPhoto.report_id == report_id)
            .order_by(ReportPhoto.sort_order, ReportPhoto.created_at)
        )
    )


async def get_photo(session: AsyncSession, report_id: uuid.UUID, photo_id: uuid.UUID) -> ReportPhoto:
    photo = await session.get(ReportPhoto, photo_id)
    if photo is None or photo.report_id != report_id:
        raise NotFoundError("PHOTO_NOT_FOUND", "Rasm topilmadi.")
    return photo


async def delete_photo(
    session: AsyncSession, *, actor_id: uuid.UUID, report_id: uuid.UUID, photo_id: uuid.UUID
) -> None:
    report = await get_report(session, report_id)
    _ensure_editable(report)
    photo = await get_photo(session, report_id, photo_id)
    await get_storage().delete(photo.object_key)
    await session.delete(photo)
    record_audit(session, actor_id=actor_id, action="REPORT_PHOTO_DELETE", entity_type="report", entity_id=report.id)
    await session.commit()
