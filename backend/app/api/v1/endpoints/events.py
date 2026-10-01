"""Events and attendance check-in for members."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, CurrentUserDep, DbSession, get_current_user
from app.models import AttendanceRecord, Event, EventRegistration
from app.models.enums import AttendanceStatus, RegistrationStatus
from app.schemas.common import Page
from app.schemas.event import CheckInIn, CheckInOut, EventOut
from app.security.rate_limit import RateLimit, enforce
from app.services import attendance as attendance_service
from app.services import events as event_service

router = APIRouter(tags=["events"])
CHECK_IN_LIMIT = RateLimit("check-in", limit=10, window_seconds=60)


async def member_event_out(
    db, event: Event, registration: EventRegistration | None, record: AttendanceRecord | None
) -> EventOut:
    registered, attended = (await event_service.counts(db, [event.id]))[event.id]
    titles = await event_service.book_titles(db, {event.book_id} if event.book_id else set())
    return EventOut(
        id=event.id,
        title=event.title,
        description=event.description,
        book_id=event.book_id,
        book_title=titles.get(event.book_id) if event.book_id else None,
        location=event.location,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        attendance_opens_at=event.attendance_opens_at,
        attendance_closes_at=event.attendance_closes_at,
        attendance_points=await event_service.effective_points(db, event),
        capacity=event.capacity,
        status=event.status,
        registered_count=registered,
        attended_count=attended,
        is_registered=registration is not None and registration.status == RegistrationStatus.REGISTERED,
        my_attendance=record.status if record and record.status != AttendanceStatus.REVOKED else None,
    )


@router.get("/events", response_model=Page[EventOut], summary="Upcoming or past events")
async def list_events(
    current: CurrentUserDep,
    db: DbSession,
    scope: Literal["upcoming", "past"] = "upcoming",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventOut]:
    rows, total = await event_service.list_member_events(
        db, user_id=current.user.id, scope=scope, limit=limit, offset=offset
    )
    items = [await member_event_out(db, event, registration, record) for event, registration, record in rows]
    return Page[EventOut](items=items, total=total, limit=limit, offset=offset)


@router.get("/events/{event_id}", response_model=EventOut, summary="Event details")
async def get_event(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> EventOut:
    event, registration, record = await event_service.get_member_event(db, user_id=current.user.id, event_id=event_id)
    return await member_event_out(db, event, registration, record)


@router.post("/events/{event_id}/register", response_model=EventOut, summary="I intend to participate")
async def register(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> EventOut:
    await event_service.register(db, user_id=current.user.id, event_id=event_id)
    return await get_event(event_id, current, db)


@router.delete("/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel my registration")
async def cancel_registration(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await event_service.cancel_registration(db, user_id=current.user.id, event_id=event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _check_in_rate_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(CHECK_IN_LIMIT, str(current.user.id))
    return current


@router.post("/attendance/verify", response_model=CheckInOut, summary="Check in with the QR code or the short code")
async def verify_attendance(
    payload: CheckInIn, current: Annotated[CurrentUser, Depends(_check_in_rate_limit)], db: DbSession
) -> CheckInOut:
    result = await attendance_service.check_in(
        db, user=current.user, token=payload.token, code=payload.code, expected_event_id=payload.event_id
    )
    return CheckInOut(
        event_id=result.event.id,
        event_title=result.event.title,
        points=result.points,
        checked_in_at=result.record.checked_in_at,
    )
