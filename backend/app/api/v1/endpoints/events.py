"""Events and attendance check-in for members."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUser, CurrentUserDep, DbSession, get_current_user
from app.models import AttendanceRecord, Event, EventRegistration
from app.models.enums import RegistrationStatus
from app.schemas.common import Page
from app.schemas.event import CheckInIn, CheckInOut, EventOut, LiveAttendanceOut, RegisterIn, ShiftOut
from app.schemas.premium import FeedbackIn, FeedbackOut
from app.security.rate_limit import RateLimit, enforce
from app.services import attendance as attendance_service
from app.services import events as event_service
from app.services import feedback as feedback_service

router = APIRouter(tags=["events"])
CHECK_IN_LIMIT = RateLimit("check-in", limit=10, window_seconds=60)


async def member_events_out(
    db, rows: list[tuple[Event, EventRegistration | None, AttendanceRecord | None]]
) -> list[EventOut]:
    """The events as a member sees them (a few queries for the whole list)."""
    ids = [event.id for event, _, _ in rows]
    counts = await event_service.counts(db, ids)
    titles = await event_service.book_titles(db, {event.book_id for event, _, _ in rows if event.book_id})
    shifts = await event_service.shifts_by_event(db, ids)
    shift_counts = await event_service.shift_registrations(db, ids)
    default_points = await event_service.default_points(db)
    items = []
    for event, registration, record in rows:
        registered, attended = counts[event.id]
        is_registered = registration is not None and registration.status == RegistrationStatus.REGISTERED
        my_answer = (
            "coming"
            if is_registered
            else "declined"
            if registration is not None and registration.status == RegistrationStatus.DECLINED
            else None
        )
        items.append(
            EventOut(
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
                attendance_points=event.attendance_points if event.attendance_points is not None else default_points,
                capacity=event.capacity,
                status=event.status,
                registered_count=registered,
                attended_count=attended,
                shifts=[
                    ShiftOut.model_validate(shift, from_attributes=True).model_copy(
                        update={"registered_count": shift_counts.get(shift.id, 0)}
                    )
                    for shift in shifts[event.id]
                ],
                is_registered=is_registered,
                my_answer=my_answer,
                my_shift_id=registration.shift_id if is_registered and registration else None,
                my_attendance=record.status if record and record.status in event_service.COUNTED else None,
            )
        )
    return items


async def member_event_out(
    db, event: Event, registration: EventRegistration | None, record: AttendanceRecord | None
) -> EventOut:
    return (await member_events_out(db, [(event, registration, record)]))[0]


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
    return Page[EventOut](items=await member_events_out(db, rows), total=total, limit=limit, offset=offset)


@router.get("/events/{event_id}", response_model=EventOut, summary="Event details")
async def get_event(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> EventOut:
    event, registration, record = await event_service.get_member_event(db, user_id=current.user.id, event_id=event_id)
    return await member_event_out(db, event, registration, record)


@router.post(
    "/events/{event_id}/register",
    response_model=EventOut,
    summary="I intend to participate (choose the shift when the event has several)",
)
async def register(
    event_id: uuid.UUID, current: CurrentUserDep, db: DbSession, payload: RegisterIn | None = None
) -> EventOut:
    await event_service.register(
        db, user_id=current.user.id, event_id=event_id, shift_id=payload.shift_id if payload else None
    )
    return await get_event(event_id, current, db)


@router.delete("/events/{event_id}/register", status_code=status.HTTP_204_NO_CONTENT, summary="Cancel my registration")
async def cancel_registration(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> Response:
    await event_service.cancel_registration(db, user_id=current.user.id, event_id=event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/events/{event_id}/decline",
    response_model=EventOut,
    summary="«Bu safar bora olmayman» — a recorded answer that can be changed back",
)
async def decline(
    event_id: uuid.UUID, current: CurrentUserDep, db: DbSession, payload: RegisterIn | None = None
) -> EventOut:
    await event_service.decline(
        db, user_id=current.user.id, event_id=event_id, shift_id=payload.shift_id if payload else None
    )
    return await get_event(event_id, current, db)


async def _check_in_rate_limit(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    await enforce(CHECK_IN_LIMIT, str(current.user.id))
    return current


@router.get("/attendance/open", response_model=list[LiveAttendanceOut], summary="Events where I can check in right now")
async def open_attendance(current: CurrentUserDep, db: DbSession) -> list[LiveAttendanceOut]:
    return [LiveAttendanceOut(**row) for row in await attendance_service.live_events_for_member(db, current.user.id)]


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


@router.get("/events/{event_id}/feedback", response_model=FeedbackOut | None, summary="My rating of an event")
async def my_feedback(event_id: uuid.UUID, current: CurrentUserDep, db: DbSession) -> FeedbackOut | None:
    feedback = await feedback_service.my_feedback(db, user_id=current.user.id, event_id=event_id)
    return (
        FeedbackOut(rating=feedback.rating, comment=feedback.comment, updated_at=feedback.updated_at)
        if feedback
        else None
    )


@router.put("/events/{event_id}/feedback", response_model=FeedbackOut, summary="Rate an event I attended (1-5)")
async def rate_event(event_id: uuid.UUID, payload: FeedbackIn, current: CurrentUserDep, db: DbSession) -> FeedbackOut:
    feedback = await feedback_service.rate(
        db, user=current.user, event_id=event_id, rating=payload.rating, comment=payload.comment or ""
    )
    return FeedbackOut(rating=feedback.rating, comment=feedback.comment, updated_at=feedback.updated_at)
