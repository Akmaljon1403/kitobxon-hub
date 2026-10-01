"""Club events and members' registrations ("I intend to come").

Registration is separate from attendance: attendance is only created by the verified
check-in flow in ``app.services.attendance``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import AttendanceRecord, Book, Event, EventRegistration, User
from app.models.enums import AttendanceStatus, EventStatus, RegistrationStatus
from app.services.audit import record_audit
from app.services.settings import get_setting

MEMBER_VISIBLE = (EventStatus.PUBLISHED, EventStatus.COMPLETED, EventStatus.CANCELLED)
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


def _snapshot(event: Event) -> dict[str, Any]:
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
                    AttendanceRecord.status != AttendanceStatus.REVOKED,
                )
                .group_by(AttendanceRecord.event_id)
            )
        ).all()
    )
    return {event_id: (registered.get(event_id, 0), attended.get(event_id, 0)) for event_id in event_ids}


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
    values.setdefault("attendance_opens_at", None)
    values.setdefault("attendance_closes_at", None)
    if values["attendance_opens_at"] is None:
        values["attendance_opens_at"] = values["starts_at"] - timedelta(minutes=10)
    if values["attendance_closes_at"] is None:
        values["attendance_closes_at"] = values["starts_at"] + timedelta(minutes=20)
    if values.get("book_id"):
        await _ensure_book(session, values["book_id"])
    event = Event(**values, created_by=actor_id)
    _validate_times(event)
    session.add(event)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="EVENT_CREATE",
        entity_type="event",
        entity_id=event.id,
        after=_snapshot(event),
    )
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
    before = _snapshot(event)
    if changes.get("book_id"):
        await _ensure_book(session, changes["book_id"])
    for field, value in changes.items():
        if field in _EVENT_FIELDS:
            setattr(event, field, value)
    _validate_times(event)
    after = _snapshot(event)
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


async def register(session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID) -> EventRegistration:
    # Lock the event row so the capacity check and the insert are atomic.
    event = await session.scalar(
        select(Event).where(Event.id == event_id, Event.deleted_at.is_(None)).with_for_update()
    )
    if event is None or event.status not in MEMBER_VISIBLE:
        raise NotFoundError("EVENT_NOT_FOUND", "Tadbir topilmadi.")
    if event.status != EventStatus.PUBLISHED or event.ends_at < datetime.now(UTC):
        raise BadRequestError("REGISTRATION_CLOSED", "Bu tadbirga ro'yxatdan o'tish yopilgan.")
    registration = await session.scalar(
        select(EventRegistration).where(EventRegistration.event_id == event_id, EventRegistration.user_id == user_id)
    )
    if registration is not None and registration.status == RegistrationStatus.REGISTERED:
        await session.commit()  # releases the row lock; nothing changed
        return registration
    if event.capacity is not None:
        taken = await session.scalar(
            select(func.count())
            .select_from(EventRegistration)
            .where(EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED)
        )
        if taken >= event.capacity:
            raise ConflictError("EVENT_FULL", "Afsuski, tadbirda bo'sh joy qolmadi.")
    now = datetime.now(UTC)
    if registration is None:
        registration = EventRegistration(event_id=event_id, user_id=user_id, registered_at=now)
        session.add(registration)
    else:
        registration.status = RegistrationStatus.REGISTERED
        registration.registered_at = now
        registration.cancelled_at = None
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
