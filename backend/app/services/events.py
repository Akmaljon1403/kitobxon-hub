"""Club events and members' registrations ("I intend to come").

Registration is separate from attendance: attendance is only created by the verified
check-in flow in ``app.services.attendance``.

An event may run in several shifts on the same day (``event_shifts``, e.g. 10:00 and 14:00 for two
groups). The event's own times then span all shifts; attendance opens by itself in every shift's
window, a member registers for the shift that suits them and still checks in once per event.
"""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import AttendanceRecord, AttendanceSession, Book, Event, EventRegistration, EventShift, User
from app.models.enums import AttendanceSessionStatus, AttendanceStatus, EventStatus, RegistrationStatus
from app.services import announcements
from app.services.audit import record_audit
from app.services.settings import get_setting

MEMBER_VISIBLE = (EventStatus.PUBLISHED, EventStatus.COMPLETED, EventStatus.CANCELLED)
COUNTED = (AttendanceStatus.VERIFIED, AttendanceStatus.SUSPICIOUS)  # PENDING waits for approval
MAX_SHIFTS = 6
OPENS_BEFORE = timedelta(minutes=10)
CLOSES_AFTER = timedelta(minutes=20)
TIMING_FIELDS = ("starts_at", "ends_at", "location", "shifts")
_EVENT_FIELDS = (
    "title",
    "description",
    "book_id",
    "location",
    "starts_at",
    "ends_at",
    "attendance_opens_at",
    "attendance_closes_at",
    "attendance_points",
    "capacity",
    "responsible_admin_id",
    "status",
)


def _snapshot(event: Event, shifts: list[EventShift] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in _EVENT_FIELDS:
        value = getattr(event, field)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, uuid.UUID):
            value = str(value)
        elif value is not None and not isinstance(value, int | str):
            value = str(value)
        result[field] = value
    if shifts is not None:
        result["shifts"] = [f"{shift.starts_at.isoformat()}/{shift.ends_at.isoformat()}" for shift in shifts]
    return result


def _validate_times(event: Event) -> None:
    if event.ends_at <= event.starts_at:
        raise BadRequestError("INVALID_DATES", "Tadbir tugash vaqti boshlanishidan keyin bo'lishi kerak.")
    if event.attendance_closes_at <= event.attendance_opens_at:
        raise BadRequestError(
            "INVALID_ATTENDANCE_WINDOW", "Davomat yopilish vaqti ochilish vaqtidan keyin bo'lishi kerak."
        )


async def effective_points(session: AsyncSession, event: Event) -> int:
    if event.attendance_points is not None:
        return event.attendance_points
    return await get_setting(session, "score.attendance_points")


async def shifts_of(session: AsyncSession, event_id: uuid.UUID) -> list[EventShift]:
    return list(
        await session.scalars(select(EventShift).where(EventShift.event_id == event_id).order_by(EventShift.position))
    )


async def shifts_by_event(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[EventShift]]:
    result: dict[uuid.UUID, list[EventShift]] = {event_id: [] for event_id in event_ids}
    if event_ids:
        for shift in await session.scalars(
            select(EventShift).where(EventShift.event_id.in_(event_ids)).order_by(EventShift.position)
        ):
            result[shift.event_id].append(shift)
    return result


def _clean_shifts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sorted shifts with default attendance windows; they must not overlap."""
    if len(items) > MAX_SHIFTS:
        raise BadRequestError("TOO_MANY_SHIFTS", f"Bir tadbirda {MAX_SHIFTS} tadan ko'p smena bo'lmaydi.")
    rows = []
    for item in sorted(items, key=lambda value: value["starts_at"]):
        starts_at, ends_at = item["starts_at"], item["ends_at"]
        if ends_at <= starts_at:
            raise BadRequestError("INVALID_DATES", "Smena tugash vaqti boshlanishidan keyin bo'lishi kerak.")
        opens = item.get("attendance_opens_at") or starts_at - OPENS_BEFORE
        closes = item.get("attendance_closes_at") or min(starts_at + CLOSES_AFTER, ends_at)
        if closes <= opens:
            raise BadRequestError(
                "INVALID_ATTENDANCE_WINDOW", "Davomat yopilish vaqti ochilish vaqtidan keyin bo'lishi kerak."
            )
        rows.append(
            {
                "starts_at": starts_at,
                "ends_at": ends_at,
                "attendance_opens_at": opens,
                "attendance_closes_at": closes,
                "capacity": item.get("capacity"),
            }
        )
    for before, after in itertools.pairwise(rows):
        if after["starts_at"] < before["ends_at"] or after["attendance_opens_at"] < before["attendance_closes_at"]:
            raise BadRequestError("SHIFTS_OVERLAP", "Smenalar vaqti (yoki davomat vaqti) ustma-ust tushmasin.")
    return rows


async def _apply_shifts(session: AsyncSession, event: Event, items: list[dict[str, Any]] | None) -> list[EventShift]:
    """Store the shifts (matched by position, so attendance already taken keeps its shift) and
    stretch the event's own times over them. One shift or none means a plain event."""
    existing = await shifts_of(session, event.id) if event.id else []
    if items is None:
        return existing
    rows = _clean_shifts(items) if items else []
    if len(rows) == 1:
        only = rows[0]
        event.starts_at, event.ends_at = only["starts_at"], only["ends_at"]
        event.attendance_opens_at = only["attendance_opens_at"]
        event.attendance_closes_at = only["attendance_closes_at"]
        rows = []
    by_position = {shift.position: shift for shift in existing}
    result = []
    for position, row in enumerate(rows, start=1):
        shift = by_position.pop(position, None)
        if shift is None:
            shift = EventShift(event_id=event.id, position=position, **row)
            session.add(shift)
        else:
            for field, value in row.items():
                setattr(shift, field, value)
        result.append(shift)
    for shift in by_position.values():
        await session.delete(shift)
    if rows:
        event.starts_at, event.ends_at = rows[0]["starts_at"], rows[-1]["ends_at"]
        event.attendance_opens_at = rows[0]["attendance_opens_at"]
        event.attendance_closes_at = rows[-1]["attendance_closes_at"]
    await session.flush()
    return result


async def get_event(session: AsyncSession, event_id: uuid.UUID) -> Event:
    event = await session.get(Event, event_id)
    if event is None or event.deleted_at is not None:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    return event


async def counts(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    """{event_id: (registered, verified attendance)}"""
    if not event_ids:
        return {}
    registered = dict(
        (
            await session.execute(
                select(EventRegistration.event_id, func.count())
                .where(
                    EventRegistration.event_id.in_(event_ids),
                    EventRegistration.status == RegistrationStatus.REGISTERED,
                )
                .group_by(EventRegistration.event_id)
            )
        ).all()
    )
    attended = dict(
        (
            await session.execute(
                select(AttendanceRecord.event_id, func.count())
                .where(
                    AttendanceRecord.event_id.in_(event_ids),
                    AttendanceRecord.status.in_(COUNTED),
                )
                .group_by(AttendanceRecord.event_id)
            )
        ).all()
    )
    return {event_id: (registered.get(event_id, 0), attended.get(event_id, 0)) for event_id in event_ids}


async def shift_registrations(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """{shift_id: registered members}"""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(EventRegistration.shift_id, func.count())
        .where(
            EventRegistration.event_id.in_(event_ids),
            EventRegistration.status == RegistrationStatus.REGISTERED,
            EventRegistration.shift_id.is_not(None),
        )
        .group_by(EventRegistration.shift_id)
    )
    return {shift_id: int(count) for shift_id, count in rows}


async def default_points(session: AsyncSession) -> int:
    return int(await get_setting(session, "score.attendance_points"))


async def book_titles(session: AsyncSession, book_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not book_ids:
        return {}
    return dict((await session.execute(select(Book.id, Book.title).where(Book.id.in_(book_ids)))).all())


# ---------------------------------------------------------------------------- admin


async def list_events_admin(
    session: AsyncSession, *, status: EventStatus | None, limit: int, offset: int
) -> tuple[list[Event], int]:
    conditions = [Event.deleted_at.is_(None)]
    if status:
        conditions.append(Event.status == status)
    total = await session.scalar(select(func.count()).select_from(Event).where(*conditions))
    rows = await session.scalars(
        select(Event).where(*conditions).order_by(Event.starts_at.desc()).limit(limit).offset(offset)
    )
    return list(rows), int(total or 0)


async def create_event(session: AsyncSession, *, actor_id: uuid.UUID, data: dict[str, Any]) -> Event:
    values = {key: value for key, value in data.items() if key in _EVENT_FIELDS}
    shift_items = data.get("shifts") or None
    if shift_items:
        first, last = min(item["starts_at"] for item in shift_items), max(item["ends_at"] for item in shift_items)
        values["starts_at"], values["ends_at"] = first, last
    values.setdefault("attendance_opens_at", None)
    values.setdefault("attendance_closes_at", None)
    if values["attendance_opens_at"] is None:
        values["attendance_opens_at"] = values["starts_at"] - OPENS_BEFORE
    if values["attendance_closes_at"] is None:
        values["attendance_closes_at"] = values["starts_at"] + CLOSES_AFTER
    if values.get("book_id"):
        await _ensure_book(session, values["book_id"])
    event = Event(**values, created_by=actor_id)
    session.add(event)
    await session.flush()
    shifts = await _apply_shifts(session, event, shift_items)
    _validate_times(event)
    record_audit(
        session,
        actor_id=actor_id,
        action="EVENT_CREATE",
        entity_type="event",
        entity_id=event.id,
        after=_snapshot(event, shifts),
    )
    await announcements.event_published(session, event)
    await session.commit()
    return event


async def _ensure_book(session: AsyncSession, book_id: uuid.UUID) -> None:
    book = await session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        raise BadRequestError("BOOK_NOT_FOUND", "Tanlangan kitob topilmadi.")


async def update_event(
    session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID, changes: dict[str, Any]
) -> Event:
    event = await get_event(session, event_id)
    before = _snapshot(event, await shifts_of(session, event.id))
    old_start, old_opens, old_closes = event.starts_at, event.attendance_opens_at, event.attendance_closes_at
    if changes.get("book_id"):
        await _ensure_book(session, changes["book_id"])
    for field, value in changes.items():
        if field in _EVENT_FIELDS:
            setattr(event, field, value)
    if event.starts_at != old_start and not changes.get("shifts"):
        # The event moved: its attendance window moves with it unless a new one was chosen.
        if changes.get("attendance_opens_at") in (None, old_opens):
            event.attendance_opens_at = event.starts_at - OPENS_BEFORE
        if changes.get("attendance_closes_at") in (None, old_closes):
            event.attendance_closes_at = min(event.starts_at + CLOSES_AFTER, event.ends_at)
    shifts = await _apply_shifts(session, event, changes.get("shifts"))
    _validate_times(event)
    after = _snapshot(event, shifts)
    if before != after:
        record_audit(
            session,
            actor_id=actor_id,
            action="EVENT_UPDATE",
            entity_type="event",
            entity_id=event.id,
            before=before,
            after=after,
        )
    if before["status"] != EventStatus.PUBLISHED and event.status == EventStatus.PUBLISHED:
        await announcements.event_published(session, event)
    elif (
        event.status == EventStatus.PUBLISHED
        and event.ends_at > datetime.now(UTC)
        and any(before.get(field) != after.get(field) for field in TIMING_FIELDS)
    ):
        await announcements.event_changed(session, event, shifts)
    if before["status"] == EventStatus.PUBLISHED and event.status == EventStatus.CANCELLED:
        await announcements.event_cancelled(session, event)
    await session.commit()
    return event


async def delete_event(session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID) -> None:
    event = await get_event(session, event_id)
    has_attendance = await session.scalar(
        select(func.count()).select_from(AttendanceRecord).where(AttendanceRecord.event_id == event.id)
    )
    if has_attendance:
        raise ConflictError(
            "EVENT_HAS_ATTENDANCE", "Davomat qayd etilgan tadbirni o'chirib bo'lmaydi. Uni «Bekor qilingan» qiling."
        )
    event.deleted_at = datetime.now(UTC)
    record_audit(
        session,
        actor_id=actor_id,
        action="EVENT_DELETE",
        entity_type="event",
        entity_id=event.id,
        before=_snapshot(event),
    )
    await session.commit()


async def list_registrations(session: AsyncSession, event_id: uuid.UUID) -> list[tuple[EventRegistration, User]]:
    await get_event(session, event_id)
    rows = await session.execute(
        select(EventRegistration, User)
        .join(User, User.id == EventRegistration.user_id)
        .where(EventRegistration.event_id == event_id, User.deleted_at.is_(None))
        .order_by(EventRegistration.registered_at)
    )
    return [(registration, user) for registration, user in rows]


# ---------------------------------------------------------------------------- members


async def list_member_events(
    session: AsyncSession, *, user_id: uuid.UUID, scope: str, limit: int, offset: int
) -> tuple[list[tuple[Event, EventRegistration | None, AttendanceRecord | None]], int]:
    now = datetime.now(UTC)
    conditions = [Event.deleted_at.is_(None), Event.status.in_(MEMBER_VISIBLE)]
    if scope == "upcoming":
        conditions.append(Event.ends_at >= now)
        order = (Event.starts_at.asc(),)
    else:
        conditions.append(or_(Event.ends_at < now, Event.status == EventStatus.COMPLETED))
        order = (Event.starts_at.desc(),)
    total = await session.scalar(select(func.count()).select_from(Event).where(*conditions))
    rows = await session.execute(
        select(Event, EventRegistration, AttendanceRecord)
        .outerjoin(
            EventRegistration,
            and_(EventRegistration.event_id == Event.id, EventRegistration.user_id == user_id),
        )
        .outerjoin(AttendanceRecord, and_(AttendanceRecord.event_id == Event.id, AttendanceRecord.user_id == user_id))
        .where(*conditions)
        .order_by(*order)
        .limit(limit)
        .offset(offset)
    )
    return [(event, registration, record) for event, registration, record in rows], int(total or 0)


async def get_member_event(
    session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID
) -> tuple[Event, EventRegistration | None, AttendanceRecord | None]:
    event = await get_event(session, event_id)
    if event.status not in MEMBER_VISIBLE:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    registration = await session.scalar(
        select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
    )
    record = await session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.event_id == event_id, AttendanceRecord.user_id == user_id)
    )
    return event, registration, record


async def register(
    session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID, shift_id: uuid.UUID | None = None
) -> EventRegistration:
    """Register (or switch to another shift). An event with shifts needs the chosen shift."""
    # Lock the event row so the capacity check and the insert are atomic.
    event = await session.scalar(
        select(Event).where(Event.id == event_id, Event.deleted_at.is_(None)).with_for_update()
    )
    if event is None or event.status not in MEMBER_VISIBLE:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    if event.status != EventStatus.PUBLISHED or event.ends_at < datetime.now(UTC):
        raise BadRequestError("REGISTRATION_CLOSED", "Bu tadbirga ro'yxatdan o'tish yopilgan.")
    shifts = await shifts_of(session, event_id)
    shift = None
    if shifts:
        shift = next((item for item in shifts if item.id == shift_id), None)
        if shift is None:
            raise BadRequestError("SHIFT_REQUIRED", "Qaysi smenada qatnashishingizni tanlang.")
        if shift.ends_at < datetime.now(UTC):
            raise BadRequestError("REGISTRATION_CLOSED", "Bu smena tugagan.")
    registration = await session.scalar(
        select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
    )
    if (
        registration is not None
        and registration.status == RegistrationStatus.REGISTERED
        and registration.shift_id == (shift.id if shift else registration.shift_id)
    ):
        await session.commit()  # releases the row lock; nothing changed
        return registration
    if shift is not None and shift.capacity is not None:
        taken = await session.scalar(
            select(func.count())
            .select_from(EventRegistration)
            .where(
                EventRegistration.shift_id == shift.id,
                EventRegistration.status == RegistrationStatus.REGISTERED,
                EventRegistration.user_id != user_id,
            )
        )
        if taken >= shift.capacity:
            raise ConflictError("SHIFT_FULL", f"{shift.position}-smenada bo'sh joy qolmadi. Boshqa smenani tanlang.")
    already = registration is not None and registration.status == RegistrationStatus.REGISTERED
    if event.capacity is not None and not already:
        taken = await session.scalar(
            select(func.count())
            .select_from(EventRegistration)
            .where(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED)
        )
        if taken >= event.capacity:
            raise ConflictError("EVENT_FULL", "Afsuski, tadbirda bo'sh joy qolmadi.")
    now = datetime.now(UTC)
    if registration is None:
        registration = EventRegistration(
            event_id=event_id, user_id=user_id, registered_at=now, shift_id=shift.id if shift else None
        )
        session.add(registration)
    else:
        if not already:
            registration.registered_at = now
        registration.status = RegistrationStatus.REGISTERED
        registration.cancelled_at = None
        registration.shift_id = shift.id if shift else registration.shift_id
    await session.commit()
    return registration


async def cancel_registration(session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID) -> None:
    event = await get_event(session, event_id)
    if event.starts_at <= datetime.now(UTC):
        raise BadRequestError("EVENT_STARTED", "Tadbir boshlangan, ro'yxatdan chiqib bo'lmaydi.")
    registration = await session.scalar(
        select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
    )
    if registration is not None and registration.status == RegistrationStatus.REGISTERED:
        registration.status = RegistrationStatus.CANCELLED
        registration.cancelled_at = datetime.now(UTC)
        await session.commit()


async def decline(
    session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID, shift_id: uuid.UUID | None = None
) -> EventRegistration:
    """«✖️ Bu safar bora olmayman» — a recorded answer. The member may switch back to
    «Qatnashaman» any time before the event ends; only the last answer counts. Declining
    never takes a seat, so there is no capacity check."""
    event = await session.scalar(
        select(Event).where(Event.id == event_id, Event.deleted_at.is_(None)).with_for_update()
    )
    if event is None or event.status not in MEMBER_VISIBLE:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    if event.status != EventStatus.PUBLISHED or event.ends_at < datetime.now(UTC):
        raise BadRequestError("REGISTRATION_CLOSED", "Bu tadbirga javob berish yopilgan.")
    now = datetime.now(UTC)
    registration = await session.scalar(
        select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
    )
    if registration is None:
        registration = EventRegistration(
            event_id=event_id, user_id=user_id, registered_at=now, status=RegistrationStatus.DECLINED, shift_id=shift_id
        )
        session.add(registration)
    else:
        registration.status = RegistrationStatus.DECLINED
        registration.cancelled_at = now
        if shift_id is not None:
            registration.shift_id = shift_id
    await session.commit()
    return registration


# ---------------------------------------------------------------------------- the end of an event


async def _finish(session: AsyncSession, event: Event, now: datetime) -> None:
    """Mark the event held, close its attendance and remind the super admins about the report."""
    event.status = EventStatus.COMPLETED
    await session.execute(
        update(AttendanceSession)
        .where(AttendanceSession.event_id == event.id, AttendanceSession.status == AttendanceSessionStatus.OPEN)
        .values(status=AttendanceSessionStatus.CLOSED, closed_at=now)
    )
    await announcements.event_finished(session, event)


async def finish_event(session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID) -> Event:
    """Stop a running event now (super admin): attendance closes and the members are told."""
    event = await get_event(session, event_id)
    now = datetime.now(UTC)
    if event.status != EventStatus.PUBLISHED:
        raise ConflictError("EVENT_NOT_RUNNING", "Faqat e'lon qilingan tadbirni yakunlash mumkin.")
    if event.starts_at > now:
        raise ConflictError("EVENT_NOT_STARTED", "Tadbir hali boshlanmagan — uni «Bekor qilingan» qiling.")
    before = _snapshot(event)
    if event.ends_at > now:
        event.ends_at = now
        for shift in await shifts_of(session, event.id):
            if shift.starts_at >= now:
                await session.delete(shift)  # a shift that never started is dropped
            elif shift.ends_at > now:
                shift.ends_at = now
                shift.attendance_closes_at = min(shift.attendance_closes_at, max(now, shift.attendance_opens_at))
    if event.attendance_closes_at > now:
        event.attendance_closes_at = max(now, event.attendance_opens_at + timedelta(seconds=1))
    await _finish(session, event, now)
    await announcements.event_stopped(session, event)
    record_audit(
        session,
        actor_id=actor_id,
        action="EVENT_FINISH",
        entity_type="event",
        entity_id=event.id,
        before=before,
        after=_snapshot(event),
    )
    await session.commit()
    return event


async def complete_finished(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: an event whose time is over becomes «o'tkazildi» (COMPLETED)."""
    now = now or datetime.now(UTC)
    events = list(
        await session.scalars(
            select(Event)
            .where(Event.deleted_at.is_(None), Event.status == EventStatus.PUBLISHED, Event.ends_at <= now)
            .with_for_update(skip_locked=True)
        )
    )
    for event in events:
        await _finish(session, event, now)
    return len(events)


async def top_rated(session: AsyncSession, *, limit: int = 10, min_ratings: int = 3) -> list[dict[str, Any]]:
    """The best events by the members' ⭐ ratings (at least ``min_ratings`` ratings)."""
    from app.models import EventFeedback

    rows = (
        await session.execute(
            select(
                Event.id,
                Event.title,
                Event.starts_at,
                func.avg(EventFeedback.rating).label("average"),
                func.count(EventFeedback.id).label("ratings"),
            )
            .join(EventFeedback, EventFeedback.event_id == Event.id)
            .where(Event.deleted_at.is_(None))
            .group_by(Event.id)
            .having(func.count(EventFeedback.id) >= min_ratings)
            .order_by(
                func.avg(EventFeedback.rating).desc(), func.count(EventFeedback.id).desc(), Event.starts_at.desc()
            )
            .limit(limit)
        )
    ).all()
    return [
        {
            "event_id": event_id,
            "title": title,
            "starts_at": starts_at,
            "average": round(float(average), 2),
            "ratings": int(ratings),
        }
        for event_id, title, starts_at, average, ratings in rows
    ]


async def feedback_averages(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[float, int]]:
    from app.models import EventFeedback

    if not event_ids:
        return {}
    rows = await session.execute(
        select(EventFeedback.event_id, func.avg(EventFeedback.rating), func.count())
        .where(EventFeedback.event_id.in_(event_ids))
        .group_by(EventFeedback.event_id)
    )
    return {event_id: (round(float(average), 1), int(count)) for event_id, average, count in rows}
