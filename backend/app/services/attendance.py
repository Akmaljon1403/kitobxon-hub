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
import csv
import hashlib
import hmac
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    AttendanceToken,
    Event,
    EventRegistration,
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
from app.services.audit import record_audit
from app.services.events import effective_points, get_event
from app.services.scoring import award_points, reverse_latest_award
from app.services.settings import get_setting
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


def _is_live(attendance_session: AttendanceSession | None, now: datetime) -> bool:
    return (
        attendance_session is not None
        and attendance_session.status == AttendanceSessionStatus.OPEN
        and attendance_session.closes_at > now
    )


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

    if minutes:
        closes_at = now + timedelta(minutes=minutes)
    elif event.attendance_closes_at > now + timedelta(minutes=1):
        closes_at = event.attendance_closes_at
    else:
        closes_at = now + timedelta(minutes=15)
    ttl = await get_setting(session, "attendance.token_ttl_seconds")
    rotation = min(await get_setting(session, "attendance.rotation_seconds"), ttl)
    attendance_session = AttendanceSession(
        event_id=event.id,
        opened_by=actor_id,
        opened_at=now,
        closes_at=closes_at,
        token_ttl_seconds=ttl,
        rotation_seconds=rotation,
    )
    session.add(attendance_session)
    await session.flush()
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_SESSION_OPEN",
        entity_type="event",
        entity_id=event.id,
        after={"closes_at": closes_at.isoformat()},
    )
    await session.commit()
    return attendance_session


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
        select(AttendanceRecord.id).where(AttendanceRecord.event_id == event.id, AttendanceRecord.user_id == user.id)
    )
    if existing is not None:
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


async def manual_check_in(
    session: AsyncSession, *, actor_id: uuid.UUID, event_id: uuid.UUID, user_id: uuid.UUID, note: str
) -> AttendanceRecord:
    event = await get_event(session, event_id)
    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    existing = await session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.event_id == event_id, AttendanceRecord.user_id == user_id)
    )
    if existing is not None:
        if existing.status == AttendanceStatus.REVOKED:
            return await set_record_status(
                session, actor_id=actor_id, record_id=existing.id, status=AttendanceStatus.VERIFIED, reason=note
            )
        raise ConflictError("ALREADY_CHECKED_IN", "Bu a'zo tadbirda allaqachon qayd etilgan.")
    now = datetime.now(UTC)
    record = AttendanceRecord(
        event_id=event.id,
        user_id=user_id,
        method=AttendanceMethod.MANUAL,
        status=AttendanceStatus.VERIFIED,
        checked_in_at=now,
        verified_by=actor_id,
        verified_at=now,
        note=note,
    )
    session.add(record)
    await session.flush()
    points = await effective_points(session, event)
    await award_points(
        session,
        user_id=user_id,
        amount=points,
        category=ScoreCategory.ATTENDANCE,
        idempotency_key=f"attendance:{event.id}:{user_id}",
        source_type="EVENT",
        source_id=event.id,
        created_by=actor_id,
        reason=note,
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="ATTENDANCE_MANUAL_ADD",
        entity_type="attendance",
        entity_id=record.id,
        after={"event_id": str(event.id), "user_id": str(user_id), "points": points},
        reason=note,
    )
    await session.commit()
    return record


async def set_record_status(
    session: AsyncSession, *, actor_id: uuid.UUID, record_id: uuid.UUID, status: AttendanceStatus, reason: str
) -> AttendanceRecord:
    record = await session.scalar(select(AttendanceRecord).where(AttendanceRecord.id == record_id).with_for_update())
    if record is None:
        raise NotFoundError("ATTENDANCE_NOT_FOUND", "Davomat yozuvi topilmadi.")
    previous = record.status
    if previous == status:
        return record
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
    await session.commit()
    return record


_METHOD_LABELS = {AttendanceMethod.QR: "QR kod", AttendanceMethod.CODE: "Kod", AttendanceMethod.MANUAL: "Admin"}
_STATUS_LABELS = {
    AttendanceStatus.VERIFIED: "Tasdiqlangan",
    AttendanceStatus.SUSPICIOUS: "Shubhali",
    AttendanceStatus.REVOKED: "Bekor qilingan",
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
    writer = csv.writer(buffer, delimiter=";")
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
