"""Admin Panel: events, registrations and attendance (live screen, corrections, export)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.bot.setup import resolve_bot_username
from app.core.errors import ForbiddenError
from app.models import Event
from app.models.enums import EventStatus
from app.schemas.common import Page
from app.schemas.event import (
    AttendanceOverviewOut,
    AttendanceRecordOut,
    AttendanceSessionIn,
    AttendanceTokenOut,
    CertificateChoiceIn,
    EventAdminOut,
    EventCreateIn,
    EventUpdateIn,
    ManualCheckInIn,
    RecordStatusIn,
    RegistrationOut,
    RejectIn,
    RsvpSummaryOut,
    ShiftOut,
    TopEventOut,
)
from app.schemas.premium import FeedbackSummaryOut
from app.security.permissions import Perm
from app.services import attendance as attendance_service
from app.services import certificate_backgrounds
from app.services import events as event_service
from app.services import feedback as feedback_service

router = APIRouter(prefix="/admin", tags=["admin: events and attendance"])
EventViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.EVENT_VIEW))]
EventCreator = Annotated[CurrentUser, Depends(require_permissions(Perm.EVENT_CREATE))]
EventEditor = Annotated[CurrentUser, Depends(require_permissions(Perm.EVENT_EDIT))]
EventDeleter = Annotated[CurrentUser, Depends(require_permissions(Perm.EVENT_DELETE))]
AttendanceViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.ATTENDANCE_VIEW))]
AttendanceManager = Annotated[CurrentUser, Depends(require_permissions(Perm.ATTENDANCE_VIEW, Perm.ATTENDANCE_MANAGE))]


async def _events_out(db, events: list[Event]) -> list[EventAdminOut]:
    """Everything the panel shows about the events, loaded in a few queries (not per event)."""
    ids = [event.id for event in events]
    counts = await event_service.counts(db, ids)
    titles = await event_service.book_titles(db, {event.book_id for event in events if event.book_id})
    shifts = await event_service.shifts_by_event(db, ids)
    shift_counts = await event_service.shift_registrations(db, ids)
    ratings = await event_service.feedback_averages(db, ids)
    live = await attendance_service.open_events(db, ids)
    pending = await attendance_service.pending_counts(db, ids)
    default_points = await event_service.default_points(db)
    result = []
    for event in events:
        registered, attended = counts[event.id]
        rating, rated = ratings.get(event.id, (None, 0))
        result.append(
            EventAdminOut(
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
                attendance_points_override=event.attendance_points,
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
                rating=rating,
                ratings_count=rated,
                responsible_admin_id=event.responsible_admin_id,
                attendance_open=event.id in live,
                created_at=event.created_at,
                pending_requests=pending.get(event.id, 0),
                certificate_background=event.certificate_background_key is not None,
                certificate_design=event.certificate_design,
                certificate_template_id=event.certificate_template_id,
            )
        )
    return result


async def _event_out(db, event: Event) -> EventAdminOut:
    return (await _events_out(db, [event]))[0]


@router.get("/events", response_model=Page[EventAdminOut], summary="All events")
async def list_events(
    _: EventViewer,
    db: DbSession,
    status_filter: Annotated[EventStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventAdminOut]:
    events, total = await event_service.list_events_admin(db, status=status_filter, limit=limit, offset=offset)
    return Page[EventAdminOut](items=await _events_out(db, events), total=total, limit=limit, offset=offset)


@router.get("/events/top-rated", response_model=list[TopEventOut], summary="The best events by members' ratings")
async def top_rated(
    _: EventViewer, db: DbSession, min_ratings: Annotated[int, Query(ge=1, le=50)] = 3
) -> list[TopEventOut]:
    return [TopEventOut(**row) for row in await event_service.top_rated(db, min_ratings=min_ratings)]


@router.post("/events", response_model=EventAdminOut, status_code=status.HTTP_201_CREATED, summary="Create an event")
async def create_event(payload: EventCreateIn, current: EventCreator, db: DbSession) -> EventAdminOut:
    event = await event_service.create_event(db, actor_id=current.user.id, data=payload.model_dump())
    return await _event_out(db, event)


@router.get("/events/{event_id}", response_model=EventAdminOut, summary="Event details")
async def get_event(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> EventAdminOut:
    return await _event_out(db, await event_service.get_event(db, event_id))


@router.patch("/events/{event_id}", response_model=EventAdminOut, summary="Edit, publish, complete or cancel")
async def update_event(
    event_id: uuid.UUID, payload: EventUpdateIn, current: EventEditor, db: DbSession
) -> EventAdminOut:
    event = await event_service.update_event(
        db, actor_id=current.user.id, event_id=event_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _event_out(db, event)


@router.post(
    "/events/{event_id}/finish",
    response_model=EventAdminOut,
    summary="Stop a running event now (super admin): attendance closes, members are told",
)
async def finish_event(event_id: uuid.UUID, current: EventEditor, db: DbSession) -> EventAdminOut:
    if "SUPER_ADMIN" not in current.roles:
        raise ForbiddenError("SUPER_ADMIN_ONLY", "Tadbirni muddatidan oldin faqat bosh administrator yakunlaydi.")
    return await _event_out(db, await event_service.finish_event(db, actor_id=current.user.id, event_id=event_id))


@router.delete(
    "/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an event without attendance"
)
async def delete_event(event_id: uuid.UUID, current: EventDeleter, db: DbSession) -> Response:
    await event_service.delete_event(db, actor_id=current.user.id, event_id=event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/{event_id}/registrations", response_model=list[RegistrationOut], summary="Members' RSVP answers")
async def registrations(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> list[RegistrationOut]:
    positions = {shift.id: shift.position for shift in await event_service.shifts_of(db, event_id)}
    return [
        RegistrationOut(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            faculty_name=faculty,
            course=user.course,
            group_name=user.group_name,
            status=registration.status.value,
            registered_at=registration.registered_at,
            shift=positions.get(registration.shift_id) if registration.shift_id else None,
        )
        for registration, user, faculty in await event_service.list_registrations(db, event_id)
    ]


@router.get(
    "/events/{event_id}/rsvp-summary",
    response_model=RsvpSummaryOut,
    summary="RSVP counts: coming / not coming / no answer",
)
async def rsvp_summary(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> RsvpSummaryOut:
    return RsvpSummaryOut(**await event_service.rsvp_summary(db, event_id))


@router.get("/events/{event_id}/registrations.csv", summary="Download RSVP answers as CSV (Excel)")
async def export_registrations(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> Response:
    filename, content = await event_service.export_registrations_csv(db, event_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ---------------------------------------------------------------------------- attendance


@router.get("/events/{event_id}/attendance", response_model=AttendanceOverviewOut, summary="Live attendance list")
async def attendance_overview(event_id: uuid.UUID, current: AttendanceViewer, db: DbSession) -> AttendanceOverviewOut:
    # Attendance opens by itself at the scheduled time; opening the screen makes it immediate.
    await attendance_service.open_scheduled_sessions(db, event_id=event_id)
    records = await attendance_service.list_records(db, event_id)
    open_session = await attendance_service.get_open_session(db, event_id)
    is_open = open_session is not None and open_session.closes_at > datetime.now(UTC)
    registered, attended = (await event_service.counts(db, [event_id]))[event_id]
    names = await attendance_service.requester_names(db, [record for record, _, _ in records])
    positions = {shift.id: shift.position for shift in await event_service.shifts_of(db, event_id)}
    return AttendanceOverviewOut(
        event_id=event_id,
        is_open=is_open,
        closes_at=open_session.closes_at if is_open and open_session else None,
        shift=positions.get(open_session.shift_id) if is_open and open_session and open_session.shift_id else None,
        can_approve="SUPER_ADMIN" in current.roles,
        registered_count=registered,
        attended_count=attended,
        records=[
            AttendanceRecordOut(
                id=record.id,
                user_id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                faculty_name=faculty,
                course=user.course,
                group_name=user.group_name,
                method=record.method,
                status=record.status,
                checked_in_at=record.checked_in_at,
                suspicious_reason=record.suspicious_reason,
                note=record.note,
                requested_by_name=names.get(record.requested_by) if record.requested_by else None,
            )
            for record, user, faculty in records
        ],
    )


@router.post("/events/{event_id}/attendance/open", status_code=status.HTTP_204_NO_CONTENT, summary="Open check-in")
async def open_attendance(
    event_id: uuid.UUID, payload: AttendanceSessionIn, current: AttendanceManager, db: DbSession
) -> Response:
    await attendance_service.open_session(db, actor_id=current.user.id, event_id=event_id, minutes=payload.minutes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events/{event_id}/attendance/close", status_code=status.HTTP_204_NO_CONTENT, summary="Close check-in")
async def close_attendance(event_id: uuid.UUID, current: AttendanceManager, db: DbSession) -> Response:
    await attendance_service.close_session(db, actor_id=current.user.id, event_id=event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/events/{event_id}/attendance/token",
    response_model=AttendanceTokenOut,
    summary="Current rotating QR token and short code for the projector screen",
)
async def attendance_token(event_id: uuid.UUID, _: AttendanceManager, db: DbSession) -> AttendanceTokenOut:
    await attendance_service.open_scheduled_sessions(db, event_id=event_id)
    display = await attendance_service.current_display_token(db, event_id)
    username = await resolve_bot_username()
    start = f"{attendance_service.QR_PREFIX}{display.token}"
    payload = f"https://t.me/{username}?start={quote(start)}" if username else start
    return AttendanceTokenOut(
        qr_payload=payload,
        token=display.token,
        code=display.code,
        expires_at=display.expires_at,
        rotates_at=display.rotates_at,
        session_closes_at=display.session_closes_at,
    )


@router.post(
    "/events/{event_id}/attendance/manual", status_code=status.HTTP_204_NO_CONTENT, summary="Add a member manually"
)
async def manual_attendance(
    event_id: uuid.UUID, payload: ManualCheckInIn, current: AttendanceManager, db: DbSession
) -> Response:
    await attendance_service.manual_check_in(
        db, actor_id=current.user.id, event_id=event_id, user_id=payload.user_id, note=payload.note
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/attendance/{record_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Approve a member added by hand (super admin): the points are given",
)
async def approve_attendance(record_id: uuid.UUID, current: AttendanceViewer, db: DbSession) -> Response:
    await attendance_service.decide_request(db, actor_id=current.user.id, record_id=record_id, approve=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/attendance/{record_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject a member added by hand (super admin): the request is removed",
)
async def reject_attendance(
    record_id: uuid.UUID, payload: RejectIn, current: AttendanceViewer, db: DbSession
) -> Response:
    await attendance_service.decide_request(
        db, actor_id=current.user.id, record_id=record_id, approve=False, reason=payload.reason
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/attendance/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Mark suspicious / revoke / restore"
)
async def correct_attendance(
    record_id: uuid.UUID, payload: RecordStatusIn, current: AttendanceManager, db: DbSession
) -> Response:
    await attendance_service.set_record_status(
        db, actor_id=current.user.id, record_id=record_id, status=payload.status, reason=payload.reason
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/{event_id}/attendance.csv", summary="Download attendance as CSV (Excel)")
async def export_attendance(event_id: uuid.UUID, _: AttendanceViewer, db: DbSession) -> Response:
    filename, content = await attendance_service.export_csv(db, event_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/events/{event_id}/feedback", response_model=FeedbackSummaryOut, summary="Members' ratings and comments")
async def event_feedback(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> FeedbackSummaryOut:
    return FeedbackSummaryOut(**await feedback_service.summary(db, event_id))


# ---------------------------------------------------------------------------- the event's own certificate design


@router.put(
    "/events/{event_id}/certificate-background",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Upload the event's certificate design (admins until the start, the super admin until the test ends)",
)
async def set_certificate_background(
    event_id: uuid.UUID, current: EventEditor, db: DbSession, file: Annotated[UploadFile, File()]
) -> Response:
    event = await event_service.get_event(db, event_id)
    data = await file.read(certificate_backgrounds.MAX_BYTES + 1)
    await certificate_backgrounds.set_background(
        db, actor_id=current.user.id, super_admin="SUPER_ADMIN" in current.roles, target=event, data=data
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/events/{event_id}/certificate-background",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Back to the standard designs (taken in turn)",
)
async def remove_certificate_background(event_id: uuid.UUID, current: EventEditor, db: DbSession) -> Response:
    event = await event_service.get_event(db, event_id)
    await certificate_backgrounds.set_background(
        db, actor_id=current.user.id, super_admin="SUPER_ADMIN" in current.roles, target=event, data=None
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/certificate-next-design",
    summary="Which standard design the next certificate would use (so the admin sees the rotation point)",
)
async def certificate_next_design(_: EventViewer, db: DbSession) -> dict[str, str]:
    from sqlalchemy import select

    from app.models import Certificate
    from app.services import certificate_designs as designs

    last = await db.scalar(
        select(Certificate.design)
        .where(Certificate.design.is_not(None), Certificate.design != designs.CUSTOM)
        .order_by(Certificate.created_at.desc())
        .limit(1)
    )
    nxt = designs.next_after(last)
    return {"code": nxt.code, "title": nxt.title}


@router.put(
    "/events/{event_id}/certificate-choice",
    response_model=EventAdminOut,
    summary="Pick a ready design (standard or saved template) for the winners, or back to next-in-turn",
)
async def set_certificate_choice(
    event_id: uuid.UUID, payload: CertificateChoiceIn, current: EventEditor, db: DbSession
) -> EventAdminOut:
    event = await event_service.get_event(db, event_id)
    await certificate_backgrounds.set_choice(
        db,
        actor_id=current.user.id,
        super_admin="SUPER_ADMIN" in current.roles,
        event=event,
        design=payload.design,
        template_id=payload.template_id,
    )
    return await _event_out(db, event)


@router.get(
    "/events/{event_id}/certificate-preview.png",
    summary="How the winners' certificate of this event will look (a sample)",
    response_class=Response,
)
async def certificate_preview(event_id: uuid.UUID, _: EventViewer, db: DbSession) -> Response:
    event = await event_service.get_event(db, event_id)
    return Response(content=await certificate_backgrounds.preview(db, event), media_type="image/png")
