"""Attendance check-in with rotating QR codes and short codes.

How the codes work (see docs/ARCHITECTURE.md §7.2):

* time is divided into slots of ``rotation_seconds``; for every slot the server derives a
  token ``HMAC(secret, session_id:slot)`` (128 bits) and a 6-character code from a second
  HMAC. Nobody can predict them without the server secret, they are specific to one
  attendance session (and therefore one event), and they expire ``token_ttl_seconds`` after
  the slot started;
* because tokens are derived (not random and kept in memory) every server instance shows
  and accepts the same codes; each issued token is still recorded in ``attendance_tokens``
  (hashes only) so check-ins can be traced to the exact token;
* one attendance record per member and event is guaranteed by ``UNIQUE(event_id, user_id)``;
  the record and its score transaction are written in the same database transaction.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceToken,
    Event,
    EventRegistration,
    EventShift,
    Faculty,
    User,
)
from app.models.enums import (
    AttendanceMethod,
    AttendanceSessionStatus,
    AttendanceStatus,
    EventStatus,
    RegistrationStatus,
    ScoreCategory,
)
from app.security.crypto import derive_key, keyed_hash
from app.services import achievements, announcements, books, referrals
from app.services.audit import record_audit
from app.services.events import effective_points, get_event, shifts_of
from app.services.scoring import award_points, reverse_latest_award
from app.services.settings import get_setting
from app.utils.spreadsheet import excel_writer
from app.utils.timezone import format_datetime

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 symbols, no 0/O/1/I confusion
CODE_LENGTH = 6
QR_PREFIX = "att_"


# ---------------------------------------------------------------------------- token derivation


def _digest(purpose: str, session_id: uuid.UUID, slot: int) -> bytes:
    return hmac.new(derive_key(purpose), f"{session_id}:{slot}".encode(), hashlib.sha256).digest()


def derive_token(session_id: uuid.UUID, slot: int) -> str:
    return base64.urlsafe_b64encode(_digest("attendance-token", session_id, slot)[:16]).decode().rstrip("=")


def derive_code(session_id: uuid.UUID, slot: int) -> str:
    digest = _digest("attendance-code", session_id, slot)
    return "".join(CODE_ALPHABET[byte % len(CODE_ALPHABET)] for byte in digest[:CODE_LENGTH])


def token_hash(raw: str) -> str:
    return keyed_hash("attendance-token-hash", raw)


def code_hash(code: str) -> str:
    return keyed_hash("attendance-code-hash", code.strip().upper())


def normalize_token(value: str) -> str:
    """Accepts a raw token, ``att_<token>`` or a full t.me deep link from the QR code."""
    value = value.strip()
    if "start=" in value:
        value = value.split("start=", 1)[1].split("&", 1)[0]
    if "startapp=" in value:
        value = value.split("startapp=", 1)[1].split("&", 1)[0]
    return value.removeprefix(QR_PREFIX)


@dataclass(frozen=True)
class DisplayToken:
    token: str
    code: str
    expires_at: datetime
    rotates_at: datetime
    session_closes_at: datetime


@dataclass(frozen=True)
class CheckInResult:
    event: Event
    record: AttendanceRecord
    points: int


# ---------------------------------------------------------------------------- sessions (admin)


async def get_open_session(session: AsyncSession, event_id: uuid.UUID) -> AttendanceSession | None:
    return await session.scalar(
        select(AttendanceSession).where(
            AttendanceSession.event_id == event_id, AttendanceSession.status == AttendanceSessionStatus.OPEN
        )
    )


async def open_events(session: AsyncSession, event_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Which of these events have attendance open right now."""
    if not event_ids:
        return set()
    return set(
        await session.scalars(
            select(AttendanceSession.event_id).where(
                AttendanceSession.event_id.in_(event_ids),
                AttendanceSession.status == AttendanceSessionStatus.OPEN,
                AttendanceSession.closes_at > datetime.now(UTC),
            )
        )
    )


async def pending_counts(session: AsyncSession, event_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Members added by hand that wait for the super admin, per event."""
    if not event_ids:
        return {}
    rows = await session.execute(
        select(AttendanceRecord.event_id, func.count())
        .where(AttendanceRecord.event_id.in_(event_ids), AttendanceRecord.status == AttendanceStatus.PENDING)
        .group_by(AttendanceRecord.event_id)
    )
    return {event_id: int(count) for event_id, count in rows}


async def requester_names(session: AsyncSession, records: list[AttendanceRecord]) -> dict[uuid.UUID, str]:
    ids = {record.requested_by for record in records if record.requested_by}
    if not ids:
        return {}
    rows = await session.execute(select(User.id, User.first_name, User.last_name).where(User.id.in_(ids)))
    return {user_id: f"{last} {first}" for user_id, first, last in rows}


def _is_live(attendance_session: AttendanceSession | None, now: datetime) -> bool:
    return (
        attendance_session is not None
        and attendance_session.status == AttendanceSessionStatus.OPEN
        and attendance_session.closes_at > now
    )


async def _create_session(
    session: AsyncSession,
    *,
    event: Event,
    actor_id: uuid.UUID | None,
    closes_at: datetime,
    now: datetime,
    shift: EventShift | None = None,
) -> AttendanceSession:
    ttl = await get_setting(session, "attendance.token_ttl_seconds")
    rotation = min(await get_setting(session, "attendance.rotation_seconds"), ttl)
    attendance_session = AttendanceSession(
        event_id=event.id,
        opened_by=actor_id,
        opened_at=now,
        closes_at=closes_at,
        token_ttl_seconds=ttl,
        rotation_seconds=rotation,
        shift_id=shift.id if shift else None,
    )
    session.add(attendance_session)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_SESSION_OPEN" if actor_id else "ATTENDANCE_SESSION_AUTO_OPEN",
        entity_type="event",
        entity_id=event.id,
        after={"closes_at": closes_at.isoformat(), "shift": shift.position if shift else None},
    )
    await announcements.attendance_opened(session, event, shift)
    return attendance_session


def _current_shift(shifts: list[EventShift], now: datetime) -> EventShift | None:
    """The shift whose attendance window is open now, else the next one, else the last one."""
    for shift in shifts:
        if shift.attendance_opens_at <= now < shift.attendance_closes_at:
            return shift
    upcoming = [shift for shift in shifts if shift.attendance_opens_at > now]
    return upcoming[0] if upcoming else (shifts[-1] if shifts else None)


async def open_session(
    session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID, minutes: int | None
) -> AttendanceSession:
    event = await get_event(session, event_id)
    if event.status != EventStatus.PUBLISHED:
        raise BadRequestError("EVENT_NOT_AVAILABLE", "Davomatni faqat e'lon qilingan tadbirda ochish mumkin.")
    now = datetime.now(UTC)
    existing = await get_open_session(session, event_id)
    if existing is not None:
        existing.status = AttendanceSessionStatus.CLOSED
        existing.closed_at = now
        await session.flush()

    shift = _current_shift(await shifts_of(session, event.id), now)
    window_closes = shift.attendance_closes_at if shift else event.attendance_closes_at
    if minutes:
        closes_at = now + timedelta(minutes=minutes)
    elif window_closes > now + timedelta(minutes=1):
        closes_at = window_closes
    else:
        closes_at = now + timedelta(minutes=15)
    attendance_session = await _create_session(
        session, event=event, actor_id=actor_id, closes_at=closes_at, now=now, shift=shift
    )
    await session.commit()
    return attendance_session


def _due_events(now: datetime, event_id: uuid.UUID | None = None) -> Select[tuple[Event]]:
    """Published events inside their (overall) attendance window."""
    conditions = [
        Event.status == EventStatus.PUBLISHED,
        Event.deleted_at.is_(None),
        Event.attendance_opens_at <= now,
        Event.attendance_closes_at > now,
    ]
    if event_id is not None:
        conditions.append(Event.id == event_id)
    return select(Event).where(*conditions)


async def _due_window(session: AsyncSession, event: Event, now: datetime) -> tuple[EventShift | None, datetime] | None:
    """(shift, closes_at) when attendance should open by itself now, else None.

    Once per window: an administrator who closed attendance early is not overruled, but a window
    that moved (the event got a new time) or the next shift opens again."""
    shifts = await shifts_of(session, event.id)
    if shifts:
        shift = next((item for item in shifts if item.attendance_opens_at <= now < item.attendance_closes_at), None)
        if shift is None:
            return None
        opened = await session.scalar(
            select(AttendanceSession.id)
            .where(
                AttendanceSession.event_id == event.id,
                AttendanceSession.shift_id == shift.id,
                AttendanceSession.opened_at >= shift.attendance_opens_at - timedelta(hours=2),
            )
            .limit(1)
        )
        return None if opened else (shift, shift.attendance_closes_at)
    opened = await session.scalar(
        select(AttendanceSession.id)
        .where(
            AttendanceSession.event_id == event.id,
            AttendanceSession.opened_at >= event.attendance_opens_at - timedelta(hours=2),
        )
        .limit(1)
    )
    return None if opened else (None, event.attendance_closes_at)


async def open_scheduled_sessions(
    session: AsyncSession, *, event_id: uuid.UUID | None = None, now: datetime | None = None
) -> int:
    """Open attendance automatically at the event's scheduled time (once per event).

    Called by the scheduler and, so nobody has to wait for it, whenever the attendance screen
    or a member's check-in page is opened. An administrator who closed attendance early is not
    overruled: an event that already had a session is never reopened automatically.
    """
    now = now or datetime.now(UTC)
    # Tidy up first: sessions whose time is over are marked closed (a new shift may open next).
    await session.execute(
        update(AttendanceSession)
        .where(AttendanceSession.status == AttendanceSessionStatus.OPEN, AttendanceSession.closes_at <= now)
        .values(status=AttendanceSessionStatus.CLOSED, closed_at=AttendanceSession.closes_at)
    )
    opened = 0
    for event in list(await session.scalars(_due_events(now, event_id))):
        # Serialise parallel callers per event; the re-check sees a session created meanwhile.
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"attendance-open:{event.id}"))))
        due = await _due_window(session, event, now)
        if due is None:
            continue
        shift, closes_at = due
        still_open = await get_open_session(session, event.id)
        if still_open is not None:  # the previous shift's session gives way to this one
            still_open.status = AttendanceSessionStatus.CLOSED
            still_open.closed_at = now
            await session.flush()
        await _create_session(session, event=event, actor_id=None, closes_at=closes_at, now=now, shift=shift)
        opened += 1
    await session.commit()
    return opened


async def live_events_for_member(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """Events where a member can check in right now (attendance is open)."""
    await open_scheduled_sessions(session)
    now = datetime.now(UTC)
    rows = await session.execute(
        select(Event, AttendanceSession.closes_at, AttendanceRecord.id)
        .join(AttendanceSession, AttendanceSession.event_id == Event.id)
        .outerjoin(AttendanceRecord, and_(AttendanceRecord.event_id == Event.id, AttendanceRecord.user_id == user_id))
        .where(
            AttendanceSession.status == AttendanceSessionStatus.OPEN,
            AttendanceSession.closes_at > now,
            Event.deleted_at.is_(None),
            Event.status == EventStatus.PUBLISHED,
        )
        .order_by(Event.starts_at)
    )
    return [
        {
            "event_id": event.id,
            "title": event.title,
            "location": event.location,
            "starts_at": event.starts_at,
            "closes_at": closes_at,
            "checked_in": record_id is not None,
        }
        for event, closes_at, record_id in rows
    ]


async def close_session(session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID) -> None:
    attendance_session = await get_open_session(session, event_id)
    if attendance_session is None:
        return
    attendance_session.status = AttendanceSessionStatus.CLOSED
    attendance_session.closed_at = datetime.now(UTC)
    record_audit(session, actor_id=actor_id, action="ATTENDANCE_SESSION_CLOSE", entity_type="event", entity_id=event_id)
    await session.commit()


async def current_display_token(session: AsyncSession, event_id: uuid.UUID) -> DisplayToken:
    """The QR token and code to show on the screen right now (creates the token row if needed)."""
    attendance_session = await get_open_session(session, event_id)
    now = datetime.now(UTC)
    if not _is_live(attendance_session, now):
        raise BadRequestError("ATTENDANCE_CLOSED", "Davomat ochiq emas.")
    assert attendance_session is not None
    rotation = attendance_session.rotation_seconds
    slot = int(now.timestamp()) // rotation
    slot_start = datetime.fromtimestamp(slot * rotation, UTC)
    expires_at = min(slot_start + timedelta(seconds=attendance_session.token_ttl_seconds), attendance_session.closes_at)
    raw = derive_token(attendance_session.id, slot)
    code = derive_code(attendance_session.id, slot)
    await session.execute(
        insert(AttendanceToken)
        .values(
            session_id=attendance_session.id,
            event_id=event_id,
            token_hash=token_hash(raw),
            code_hash=code_hash(code),
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(index_elements=[AttendanceToken.token_hash])
    )
    await session.commit()
    return DisplayToken(
        token=raw,
        code=code,
        expires_at=expires_at,
        rotates_at=slot_start + timedelta(seconds=rotation),
        session_closes_at=attendance_session.closes_at,
    )


# ---------------------------------------------------------------------------- check-in (members)


async def check_in(
    session: AsyncSession,
    *,
    user: User,
    token: str | None = None,
    code: str | None = None,
    expected_event_id: uuid.UUID | None = None,
) -> CheckInResult:
    now = datetime.now(UTC)
    if token:
        row = await session.scalar(
            select(AttendanceToken).where(AttendanceToken.token_hash == token_hash(normalize_token(token)))
        )
        method = AttendanceMethod.QR
    elif code:
        candidates = list(
            await session.scalars(
                select(AttendanceToken)
                .where(AttendanceToken.code_hash == code_hash(code))
                .order_by(AttendanceToken.created_at.desc())
                .limit(2)
            )
        )
        live = [candidate for candidate in candidates if candidate.expires_at > now]
        row = live[0] if len(live) == 1 else (candidates[0] if candidates and not live else None)
        method = AttendanceMethod.CODE
    else:
        raise BadRequestError("ATTENDANCE_TOKEN_REQUIRED", "QR kodni skanerlang yoki kodni kiriting.")

    if row is None:
        raise BadRequestError("ATTENDANCE_TOKEN_INVALID", "QR kod yoki kod noto'g'ri. Ekrandagi kodni tekshiring.")
    if expected_event_id is not None and row.event_id != expected_event_id:
        raise BadRequestError("ATTENDANCE_WRONG_EVENT", "Bu QR kod boshqa tadbirga tegishli.")
    if row.expires_at <= now:
        raise BadRequestError("ATTENDANCE_EXPIRED", "Kod muddati tugagan. Ekrandagi yangi QR kodni skanerlang.")

    attendance_session = await session.get(AttendanceSession, row.session_id)
    if not _is_live(attendance_session, now):
        raise BadRequestError("ATTENDANCE_CLOSED", "Bu tadbirda davomat yopilgan.")
    event = await session.get(Event, row.event_id)
    if event is None or event.deleted_at is not None or event.status != EventStatus.PUBLISHED:
        raise BadRequestError("EVENT_NOT_AVAILABLE", "Bu tadbir hozir faol emas.")

    if await get_setting(session, "attendance.require_registration"):
        registered = await session.scalar(
            select(EventRegistration.id).where(
                EventRegistration.event_id == event.id,
                EventRegistration.user_id == user.id,
                EventRegistration.status == RegistrationStatus.REGISTERED,
            )
        )
        if registered is None:
            raise BadRequestError("REGISTRATION_REQUIRED", "Davomat uchun avval tadbirga ro'yxatdan o'ting.")

    existing = await session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.event_id == event.id, AttendanceRecord.user_id == user.id)
    )
    if existing is not None and existing.status == AttendanceStatus.PENDING:
        # An admin asked to add the member by hand, but the member scanned the code: no approval needed.
        await session.delete(existing)
        await session.flush()
    elif existing is not None:
        raise ConflictError("ALREADY_CHECKED_IN", "Siz bu tadbirda allaqachon qayd etilgansiz.")

    record = AttendanceRecord(
        event_id=event.id,
        user_id=user.id,
        session_id=row.session_id,
        token_id=row.id,
        method=method,
        status=AttendanceStatus.VERIFIED,
        checked_in_at=now,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError as exc:  # a parallel request of the same member won the race
        await session.rollback()
        raise ConflictError("ALREADY_CHECKED_IN", "Siz bu tadbirda allaqachon qayd etilgansiz.") from exc

    points = await effective_points(session, event)
    await award_points(
        session,
        user_id=user.id,
        amount=points,
        category=ScoreCategory.ATTENDANCE,
        idempotency_key=f"attendance:{event.id}:{user.id}",
        source_type="EVENT",
        source_id=event.id,
    )
    await books.read_at_event(session, event.book_id, user.id)
    await achievements.evaluate(session, user.id)
    await referrals.on_first_attendance(session, user.id)
    await session.commit()
    return CheckInResult(event=event, record=record, points=points)


# ---------------------------------------------------------------------------- admin corrections


async def list_records(session: AsyncSession, event_id: uuid.UUID) -> list[tuple[AttendanceRecord, User, str | None]]:
    await get_event(session, event_id)
    rows = await session.execute(
        select(AttendanceRecord, User, Faculty.name)
        .join(User, User.id == AttendanceRecord.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(AttendanceRecord.event_id == event_id)
        .order_by(AttendanceRecord.checked_in_at.desc())
    )
    return [(record, user, faculty) for record, user, faculty in rows]


async def _is_super_admin(session: AsyncSession, user_id: uuid.UUID) -> bool:
    from app.services.rbac import get_role_codes

    return "SUPER_ADMIN" in await get_role_codes(session, user_id)


async def _credit(
    session: AsyncSession, record: AttendanceRecord, event: Event, *, actor_id: uuid.UUID, note: str | None
) -> int:
    """Points, achievements and a friend's invitation reward for a verified manual record."""
    points = await effective_points(session, event)
    await award_points(
        session,
        user_id=record.user_id,
        amount=points,
        category=ScoreCategory.ATTENDANCE,
        idempotency_key=f"attendance:{event.id}:{record.user_id}",
        source_type="EVENT",
        source_id=event.id,
        created_by=actor_id,
        reason=note,
    )
    await books.read_at_event(session, event.book_id, record.user_id)
    await achievements.evaluate(session, record.user_id)
    await referrals.on_first_attendance(session, record.user_id)
    return points


async def manual_check_in(
    session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID, user_id: uuid.UUID, note: str
) -> AttendanceRecord:
    """An administrator adds a member by hand (exceptional cases: a dead phone, a lost code...).

    Added by the super administrator, it counts at once. Added by another administrator, it waits
    (PENDING) until a super administrator approves it in the bot or the panel."""
    event = await get_event(session, event_id)
    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    direct = await _is_super_admin(session, actor_id)
    existing = await session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.event_id == event_id, AttendanceRecord.user_id == user_id)
    )
    if existing is not None:
        if existing.status == AttendanceStatus.REVOKED and direct:
            return await set_record_status(
                session, actor_id=actor_id, record_id=existing.id, status=AttendanceStatus.VERIFIED, reason=note
            )
        if existing.status == AttendanceStatus.PENDING:
            raise ConflictError("ATTENDANCE_PENDING", "Bu a'zo uchun so'rov allaqachon tasdiq kutmoqda.")
        if existing.status != AttendanceStatus.REVOKED:
            raise ConflictError("ALREADY_CHECKED_IN", "Bu a'zo tadbirda allaqachon qayd etilgan.")
        await session.delete(existing)  # a revoked record is replaced by the new request
        await session.flush()
    now = datetime.now(UTC)
    record = AttendanceRecord(
        event_id=event.id,
        user_id=user_id,
        method=AttendanceMethod.MANUAL,
        status=AttendanceStatus.VERIFIED if direct else AttendanceStatus.PENDING,
        checked_in_at=now,
        requested_by=actor_id,
        verified_by=actor_id if direct else None,
        verified_at=now if direct else None,
        note=note,
    )
    session.add(record)
    await session.flush()
    points = await _credit(session, record, event, actor_id=actor_id, note=note) if direct else 0
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_MANUAL_ADD" if direct else "ATTENDANCE_MANUAL_REQUEST",
        entity_type="attendance",
        entity_id=record.id,
        after={"event_id": str(event.id), "user_id": str(user_id), "points": points, "pending": not direct},
        reason=note,
    )
    if not direct:
        await _ask_super_admins(session, record, event, member, actor_id)
    await session.commit()
    return record


async def _ask_super_admins(
    session: AsyncSession, record: AttendanceRecord, event: Event, member: User, actor_id: uuid.UUID
) -> None:
    from html import escape

    from app.models.enums import NotificationType
    from app.services.notifications import enqueue_for_members
    from app.services.rbac import super_admins

    actor = await session.get(User, actor_id)
    who = f"{actor.last_name} {actor.first_name}" if actor else "Admin"
    text = (
        f"🙋 <b>Davomatga qo'lda qo'shish so'rovi</b>\n\n"
        f"Tadbir: «{escape(event.title)}»\n"
        f"A'zo: {escape(member.last_name)} {escape(member.first_name)}"
        + (f" ({escape(member.group_name)}-guruh)" if member.group_name else "")
        + f"\nKim qo'shdi: {escape(who)}\nSabab: {escape(record.note or '—')}\n\nTasdiqlaysizmi?"
    )
    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=text,
        dedup_prefix=f"attendance_request:{record.id}",
        members=super_admins(),
        sync=f"attendance:{record.id}",
        payload={
            "base": text,
            "buttons": [
                {
                    "row": [
                        {"text": "✅ Tasdiqlash", "callback": f"att:ok:{record.id.hex}"},
                        {"text": "❌ Rad etish", "callback": f"att:no:{record.id.hex}"},
                    ]
                },
                {"text": "📋 Davomat sahifasi", "admin_route": f"events/{event.id}/attendance"},
            ],
        },
        priority=2,
    )


async def _settle_request(
    session: AsyncSession, record: AttendanceRecord, event: Any, actor_id: uuid.UUID, what: str
) -> None:
    """Every super admin's copy of the request shows the decision."""
    from app.services import copies

    status = f"{what} — {await copies.admin_name(session, actor_id)}, {copies.stamp()}"
    buttons = [{"text": "📋 Davomat sahifasi", "admin_route": f"events/{event.id}/attendance"}]
    await copies.settle(session, f"attendance:{record.id}", status, buttons=buttons)


async def decide_request(
    session: AsyncSession, *, actor_id: uuid.UUID, record_id: uuid.UUID, approve: bool, reason: str | None = None
) -> AttendanceRecord | None:
    """The super administrator approves (points are given) or rejects (the request is removed)."""
    if not await _is_super_admin(session, actor_id):
        raise ForbiddenError("SUPER_ADMIN_ONLY", "Qo'lda qo'shilgan davomatni faqat bosh administrator tasdiqlaydi.")
    record = await session.scalar(select(AttendanceRecord).where(AttendanceRecord.id == record_id).with_for_update())
    if record is None or record.status != AttendanceStatus.PENDING:
        raise ConflictError("REQUEST_DECIDED", "Bu so'rov allaqachon hal qilingan.")
    event = await get_event(session, record.event_id)
    if approve:
        record.status = AttendanceStatus.VERIFIED
        record.verified_by = actor_id
        record.verified_at = datetime.now(UTC)
        await session.flush()
        points = await _credit(session, record, event, actor_id=actor_id, note=record.note)
        record_audit(
            session,
            actor_id=actor_id,
            action="ATTENDANCE_MANUAL_APPROVE",
            entity_type="attendance",
            entity_id=record.id,
            after={"points": points},
        )
        await _settle_request(session, record, event, actor_id, "✅ <b>Tasdiqlandi</b>")
        await session.commit()
        return record
    await _settle_request(session, record, event, actor_id, "❌ <b>Rad etildi</b>")
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_MANUAL_REJECT",
        entity_type="attendance",
        entity_id=record.id,
        before={"event_id": str(record.event_id), "user_id": str(record.user_id)},
        reason=reason,
    )
    await session.delete(record)  # the member can still check in properly
    await session.commit()
    return None


async def set_record_status(
    session: AsyncSession, *, actor_id: uuid.UUID, record_id: uuid.UUID, status: AttendanceStatus, reason: str
) -> AttendanceRecord:
    record = await session.scalar(select(AttendanceRecord).where(AttendanceRecord.id == record_id).with_for_update())
    if record is None:
        raise NotFoundError("ATTENDANCE_NOT_FOUND", "Davomat yozuvi topilmadi.")
    previous = record.status
    if previous == status:
        return record
    if AttendanceStatus.PENDING in (previous, status):
        raise ConflictError(
            "ATTENDANCE_PENDING", "Tasdiq kutayotgan yozuvni «Tasdiqlash» yoki «Rad etish» bilan hal qiling."
        )
    event = await get_event(session, record.event_id)

    if status == AttendanceStatus.REVOKED:
        await reverse_latest_award(
            session,
            user_id=record.user_id,
            category=ScoreCategory.ATTENDANCE,
            source_type="EVENT",
            source_id=event.id,
            created_by=actor_id,
            reason=reason,
        )
    elif previous == AttendanceStatus.REVOKED:
        points = await effective_points(session, event)
        await award_points(
            session,
            user_id=record.user_id,
            amount=points,
            category=ScoreCategory.ATTENDANCE,
            idempotency_key=f"attendance:{event.id}:{record.user_id}:restored:{uuid.uuid4()}",
            source_type="EVENT",
            source_id=event.id,
            created_by=actor_id,
            reason=reason,
        )

    record.status = status
    record.suspicious_reason = reason if status == AttendanceStatus.SUSPICIOUS else record.suspicious_reason
    record.verified_by = actor_id
    record.verified_at = datetime.now(UTC)
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_CORRECTION",
        entity_type="attendance",
        entity_id=record.id,
        before={"status": previous.value},
        after={"status": status.value},
        reason=reason,
    )
    if status == AttendanceStatus.VERIFIED:
        await session.flush()
        await books.read_at_event(session, event.book_id, record.user_id)
        await achievements.evaluate(session, record.user_id)
    await session.commit()
    return record


_METHOD_LABELS = {AttendanceMethod.QR: "QR kod", AttendanceMethod.CODE: "Kod", AttendanceMethod.MANUAL: "Admin"}
_STATUS_LABELS = {
    AttendanceStatus.VERIFIED: "Tasdiqlangan",
    AttendanceStatus.SUSPICIOUS: "Shubhali",
    AttendanceStatus.REVOKED: "Bekor qilingan",
    AttendanceStatus.PENDING: "Tasdiq kutilmoqda",
}


async def export_csv(session: AsyncSession, event_id: uuid.UUID) -> tuple[str, str]:
    """(file name, CSV text with BOM so that Excel opens Uzbek letters correctly)."""
    event = await get_event(session, event_id)
    records = await list_records(session, event_id)
    registered = set(
        await session.scalars(
            select(EventRegistration.user_id).where(
                EventRegistration.event_id == event_id, EventRegistration.status == RegistrationStatus.REGISTERED
            )
        )
    )
    buffer = io.StringIO()
    writer = excel_writer(buffer)
    writer.writerow(["№", "Familiya", "Ism", "Fakultet", "Kurs", "Guruh", "Usul", "Holat", "Vaqt", "Ro'yxatdan o'tgan"])
    for index, (record, user, faculty) in enumerate(reversed(records), start=1):
        writer.writerow(
            [
                index,
                user.last_name,
                user.first_name,
                faculty or "",
                user.course or "",
                user.group_name or "",
                _METHOD_LABELS[record.method],
                _STATUS_LABELS[record.status],
                format_datetime(record.checked_in_at),
                "ha" if user.id in registered else "yo'q",
            ]
        )
    safe_title = "".join(ch if ch.isalnum() else "_" for ch in event.title)[:40] or "tadbir"
    return f"davomat_{safe_title}.csv", "﻿" + buffer.getvalue()
