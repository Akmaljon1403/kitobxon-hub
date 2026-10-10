"""Official event reports: facts from the database, admin text, optional AI wording, approval, PDF.

The rule that keeps reports honest: every fact (dates, places, names, counts, percentages)
comes from ``facts_snapshot`` — loaded by SQL when the report is prepared — or from what the
admin typed. A draft (written by AI, by the built-in template or by hand) may only contain
numbers found there; ``number_issues`` lists any other number and approval is refused until
the admin fixes the text. The statistics tables in the PDF are always rendered from the
snapshot, never from the draft.
"""

from __future__ import annotations

import html
import io
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    Book,
    BookRead,
    Certificate,
    Event,
    EventFeedback,
    EventRegistration,
    Faculty,
    Report,
    ReportPhoto,
    Test,
    TestAttempt,
    User,
)
from app.models.enums import (
    AttemptStatus,
    AttendanceStatus,
    EventStatus,
    NotificationType,
    ReadingStatus,
    RegistrationStatus,
    ReportKind,
    ReportStatus,
    UserStatus,
)
from app.services.audit import record_audit
from app.services.settings import get_setting
from app.services.storage import get_storage
from app.utils.timezone import MONTHS_UZ, local_tz, to_local

EDITABLE_STATUSES = (ReportStatus.DRAFT, ReportStatus.AI_GENERATED, ReportStatus.REVIEW)
FINAL_STATUSES = (ReportStatus.APPROVED, ReportStatus.PDF_GENERATED, ReportStatus.ARCHIVED)
ADMIN_FIELDS = ("title", "objective", "activity_description", "results", "conclusion", "recommendations")
MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_PHOTO_PIXELS = 40_000_000
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
            .where(
                AttendanceRecord.event_id == event.id,
                AttendanceRecord.status.in_((AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)),
            )
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
        "feedback": await _feedback(session, [event.id]),
        "prepared_at": datetime.now(UTC).isoformat(),
    }


async def _feedback(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[str, Any]:
    count, average = (
        await session.execute(
            select(func.count(), func.avg(EventFeedback.rating)).where(EventFeedback.event_id.in_(event_ids))
        )
    ).one()
    return {"count": int(count or 0), "average": round(float(average), 1) if average is not None else None}


def _uz_day(value: date) -> str:
    return f"{value.year}-yil {value.day}-{MONTHS_UZ[value.month - 1]}"


def period_label(start: date, end: date) -> str:
    """ "2026-yil 1-oktabrdan 31-oktabrgacha" """
    if start.year == end.year:
        return f"{start.year}-yil {start.day}-{MONTHS_UZ[start.month - 1]}dan {end.day}-{MONTHS_UZ[end.month - 1]}gacha"
    return f"{_uz_day(start)}dan {_uz_day(end)}gacha"


async def build_period_facts(session: AsyncSession, start: date, end: date) -> dict[str, Any]:
    """Everything the club did between two dates (inclusive), loaded from the database."""
    from app.services.ranking import ranking

    since = datetime.combine(start, time.min, tzinfo=local_tz())
    until = datetime.combine(end + timedelta(days=1), time.min, tzinfo=local_tz())
    events = list(
        await session.scalars(
            select(Event)
            .where(
                Event.deleted_at.is_(None),
                Event.status.in_((EventStatus.PUBLISHED, EventStatus.COMPLETED)),
                Event.starts_at >= since,
                Event.starts_at < until,
            )
            .order_by(Event.starts_at)
        )
    )
    event_ids = [event.id for event in events]
    verified = (
        await session.execute(
            select(AttendanceRecord.event_id, AttendanceRecord.user_id, Faculty.name)
            .join(User, User.id == AttendanceRecord.user_id)
            .outerjoin(Faculty, Faculty.id == User.faculty_id)
            .where(AttendanceRecord.event_id.in_(event_ids), AttendanceRecord.status == AttendanceStatus.VERIFIED)
        )
    ).all()
    per_event: dict[uuid.UUID, int] = {}
    faculty_of: dict[uuid.UUID, str] = {}
    for row in verified:
        per_event[row.event_id] = per_event.get(row.event_id, 0) + 1
        faculty_of[row.user_id] = row.name or "Ko'rsatilmagan"
    by_faculty: dict[str, int] = {}
    for name in faculty_of.values():
        by_faculty[name] = by_faculty.get(name, 0) + 1

    tests = []
    for test in await session.scalars(
        select(Test)
        .where(Test.deleted_at.is_(None), Test.starts_at >= since, Test.starts_at < until)
        .order_by(Test.starts_at)
    ):
        participants, average = (
            await session.execute(
                select(func.count(func.distinct(TestAttempt.user_id)), func.avg(TestAttempt.score)).where(
                    TestAttempt.test_id == test.id,
                    TestAttempt.status.in_((AttemptStatus.SUBMITTED, AttemptStatus.EXPIRED)),
                )
            )
        ).one()
        if participants:
            tests.append(
                {
                    "title": test.title,
                    "participants": int(participants),
                    "average_score": round(float(average or 0), 1),
                    "max_score": test.max_score,
                }
            )

    async def count(query: Any) -> int:
        return int(await session.scalar(query) or 0)

    board = await ranking(session, period="all", scope="all", viewer=None, limit=5, between=(since, until))
    names = {  # an official report uses full names, whatever the public ranking shows
        row.id: f"{row.last_name} {row.first_name}"
        for row in await session.execute(
            select(User.id, User.first_name, User.last_name).where(User.id.in_([r.user_id for r in board.items]))
        )
    }
    return {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "period": {"label": period_label(start, end), "start": start.isoformat(), "end": end.isoformat()},
        "summary": {
            "events": len(events),
            "attendances": len(verified),
            "participants": len(faculty_of),
            "new_members": await count(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), User.registered_at >= since, User.registered_at < until)
            ),
            "active_members": await count(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
            ),
            "books_completed": await count(
                select(func.count())
                .select_from(BookRead)
                .where(
                    BookRead.status == ReadingStatus.COMPLETED,
                    BookRead.completed_at >= since,
                    BookRead.completed_at < until,
                )
            ),
            "certificates": await count(
                select(func.count())
                .select_from(Certificate)
                .where(Certificate.revoked_at.is_(None), Certificate.issued_at >= since, Certificate.issued_at < until)
            ),
        },
        "events": [
            {"title": event.title, "date": _uz_date(event.starts_at), "attended": per_event.get(event.id, 0)}
            for event in events
        ],
        "faculties": [{"name": name, "attended": n} for name, n in sorted(by_faculty.items())],
        "tests": tests,
        "top_members": [
            {"place": row.rank, "name": names.get(row.user_id, row.name), "faculty": row.faculty, "points": row.total}
            for row in board.items
        ],
        "feedback": await _feedback(session, event_ids) if event_ids else {"count": 0, "average": None},
        "prepared_at": datetime.now(UTC).isoformat(),
    }


async def build_general_facts(session: AsyncSession) -> dict[str, Any]:
    return {
        "organization": await get_setting(session, "org.organization_name"),
        "club": await get_setting(session, "org.club_name"),
        "date": _uz_date(datetime.now(UTC)),
        "prepared_at": datetime.now(UTC).isoformat(),
    }


async def facts_for(session: AsyncSession, report: Report) -> dict[str, Any]:
    if report.kind == ReportKind.EVENT:
        event = await session.get(Event, report.event_id)
        assert event is not None
        return await build_facts(session, event)
    if report.kind == ReportKind.PERIOD:
        assert report.period_start is not None and report.period_end is not None
        return await build_period_facts(session, report.period_start, report.period_end)
    return await build_general_facts(session)


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


def _admin_sections(report: Report) -> list[str]:
    parts: list[str] = []
    if report.results:
        parts += ["## Natijalar", report.results.strip()]
    if report.conclusion:
        parts += ["## Xulosa", report.conclusion.strip()]
    if report.recommendations:
        parts += ["## Takliflar", report.recommendations.strip()]
    return parts


def _period_draft(report: Report) -> str:
    facts = report.facts_snapshot or {}
    summary = facts.get("summary", {})
    parts = [
        "## Kirish",
        f"Ushbu hisobotda {facts.get('club')}ning {facts.get('period', {}).get('label')} davrida amalga "
        "oshirgan ishlari jamlangan.",
    ]
    if report.objective:
        parts.append(report.objective.strip())
    parts.append("## Tadbirlar")
    if summary.get("events"):
        parts.append(
            f"Hisobot davrida {summary['events']} ta tadbir o'tkazildi. Ularda jami {summary.get('attendances', 0)}"
            f" marta qatnashuv qayd etildi, {summary.get('participants', 0)} nafar turli a'zo ishtirok etdi."
        )
        parts.append(
            "; ".join(f"«{row['title']}» ({row['date']}) — {row['attended']} nafar" for row in facts.get("events", []))
            + "."
        )
    else:
        parts.append("Hisobot davrida tadbirlar o'tkazilmadi.")
    if report.activity_description:
        parts.append(report.activity_description.strip())
    parts.append("## A'zolar va kitobxonlik")
    parts.append(
        f"Davr mobaynida {summary.get('new_members', 0)} nafar yangi a'zo qo'shildi; faol a'zolar soni"
        f" {summary.get('active_members', 0)} nafarni tashkil etadi. A'zolar {summary.get('books_completed', 0)} ta"
        " kitobni o'qib tugatdi."
    )
    for test in facts.get("tests") or []:
        parts.append(
            f"«{test['title']}» testida {test['participants']} nafar a'zo qatnashdi, o'rtacha natija"
            f" {test['average_score']} ball ({test['max_score']} balldan)."
        )
    top = facts.get("top_members") or []
    if top:
        parts.append("## Eng faol a'zolar")
        parts.append("; ".join(f"{row['place']}. {row['name']} — {row['points']} ball" for row in top) + ".")
    return "\n\n".join(parts + _admin_sections(report))


def _general_draft(report: Report) -> str:
    parts: list[str] = []
    if report.objective:
        parts += ["## Kirish", report.objective.strip()]
    if report.activity_description:
        parts += ["## Amalga oshirilgan ishlar", report.activity_description.strip()]
    return "\n\n".join(parts + _admin_sections(report)) or report.title


def template_draft(report: Report) -> str:
    """A formal draft built only from facts and admin text (used when AI is not configured)."""
    if report.kind == ReportKind.PERIOD:
        return _period_draft(report)
    if report.kind == ReportKind.GENERAL:
        return _general_draft(report)
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
    feedback = facts.get("feedback") or {}
    if feedback.get("count"):
        parts.append(
            f"Ishtirokchilar tadbirni o'rtacha {feedback['average']} ballga baholadi (5 ballik shkala,"
            f" {feedback['count']} ta baho)."
        )
    return "\n\n".join(parts + _admin_sections(report))


# ---------------------------------------------------------------------------- lifecycle


def _snapshot(report: Report) -> dict[str, Any]:
    return {"status": str(report.status), "version": report.version, "title": report.title}


def subject(report: Report, event_title: str | None) -> str:
    """What the report is about, for lists: the event, the period or "Umumiy"."""
    if report.kind == ReportKind.EVENT:
        return event_title or "—"
    if report.kind == ReportKind.PERIOD and report.period_start and report.period_end:
        return period_label(report.period_start, report.period_end)
    return "Umumiy hisobot"


async def list_reports(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[tuple[Report, str]], int]:
    total = await session.scalar(select(func.count()).select_from(Report))
    rows = await session.execute(
        select(Report, Event.title)
        .outerjoin(Event, Event.id == Report.event_id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [(report, subject(report, title)) for report, title in rows], int(total or 0)


MAX_PERIOD_DAYS = 400


async def create_report(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    kind: ReportKind = ReportKind.EVENT,
    event_id: uuid.UUID | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    title: str | None = None,
    version: int | None = None,
) -> Report:
    event = None
    if kind == ReportKind.EVENT:
        event = await session.get(Event, event_id) if event_id else None
        if event is None or event.deleted_at is not None:
            raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
        version = (
            int(
                await session.scalar(
                    select(func.coalesce(func.max(Report.version), 0)).where(Report.event_id == event.id)
                )
                or 0
            )
            + 1
        )
        title = title or f"«{event.title}» tadbiri bo'yicha hisobot"
    elif kind == ReportKind.PERIOD:
        if period_start is None or period_end is None or period_end < period_start:
            raise BadRequestError("INVALID_PERIOD", "Davr boshlanishi va tugashini to'g'ri kiriting.")
        if (period_end - period_start).days > MAX_PERIOD_DAYS:
            raise BadRequestError("INVALID_PERIOD", "Davr bir yildan oshmasin.")
        title = title or f"{period_label(period_start, period_end)} faoliyat hisoboti"
    elif not title:
        raise BadRequestError("TITLE_REQUIRED", "Hisobot mavzusini yozing.")
    report = Report(
        kind=kind,
        event_id=event.id if event else None,
        period_start=period_start if kind == ReportKind.PERIOD else None,
        period_end=period_end if kind == ReportKind.PERIOD else None,
        version=version or 1,
        status=ReportStatus.DRAFT,
        title=title,
        created_by=actor_id,
    )
    report.facts_snapshot = await facts_for(session, report)
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
    report.facts_snapshot = await facts_for(session, report)
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
    if report.kind == ReportKind.EVENT:
        from app.services import channel

        await channel.report_posted(session, report)
    await _tell_approved(session, report, actor_id)
    await session.commit()
    await store_pdf(session, report)
    return report


async def _tell_approved(session: AsyncSession, report: Report, actor_id: uuid.UUID) -> None:
    """The admin who approved gets a short confirmation in the bot (the report stays in the panel)."""
    from app.services.notifications import enqueue_notification

    await enqueue_notification(
        session,
        user_id=actor_id,
        type_=NotificationType.SYSTEM,
        text=f"✅ «{html.escape(report.title)}» hisoboti muvaffaqiyatli yaratildi va bazada saqlandi.",
        dedup_key=f"report_ready:{report.id}",
        payload={"buttons": [{"text": "📄 Hisobotlar", "admin_route": "reports"}]},
        priority=3,
    )


async def store_pdf(session: AsyncSession, report: Report) -> bytes:
    """Render the official PDF and keep it in storage (also used to rebuild a lost file)."""
    from app.services.report_pdf import render_report_pdf

    pdf = await render_report_pdf(session, report, draft=False)
    folder = report.event_id or str(report.kind).lower()
    key = report.pdf_object_key or f"reports/{folder}/{report.id}-v{report.version}.pdf"
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
    report = await create_report(
        session,
        actor_id=actor_id,
        kind=source.kind,
        event_id=source.event_id,
        period_start=source.period_start,
        period_end=source.period_end,
        title=source.title,
        version=source.version + 1,
    )
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
        # Opening reads only the header: refuse tiny files that would unpack into huge images.
        if image.width * image.height > MAX_PHOTO_PIXELS:
            raise BadRequestError("PHOTO_TOO_LARGE", "Rasm o'lchami juda katta (ko'pi bilan 40 megapiksel).")
        image.verify()
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
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
