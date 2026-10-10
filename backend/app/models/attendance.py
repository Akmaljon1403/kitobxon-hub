"""Attendance: sessions opened by admins, rotating tokens (QR + short code) and verified records.

Design (see docs/ARCHITECTURE.md §7.2):
* tokens are server-generated 128-bit random values; only an HMAC of the token and of the
  short code is stored, so a database leak does not reveal valid codes;
* a token is shared by everyone in the room during its short lifetime, but
  ``UNIQUE(event_id, user_id)`` on records guarantees one check-in per member per event,
  even when two requests arrive at the same moment.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import AttendanceMethod, AttendanceSessionStatus, AttendanceStatus


class AttendanceSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("closes_at > opened_at", name="window_order"),
        CheckConstraint("token_ttl_seconds BETWEEN 10 AND 600", name="token_ttl_range"),
        CheckConstraint("rotation_seconds BETWEEN 5 AND token_ttl_seconds", name="rotation_range"),
        # Only one open session per event.
        Index(
            "uq_attendance_sessions_open_event",
            "event_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    opened_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    opened_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closes_at: Mapped[datetime] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[AttendanceSessionStatus] = mapped_column(
        enum_column(AttendanceSessionStatus),
        default=AttendanceSessionStatus.OPEN,
        server_default=AttendanceSessionStatus.OPEN.value,
    )
    # The shift this session belongs to (events with several shifts open once per shift).
    shift_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event_shifts.id", ondelete="SET NULL"))
    token_ttl_seconds: Mapped[int] = mapped_column(Integer, default=60, server_default=text("60"))
    rotation_seconds: Mapped[int] = mapped_column(Integer, default=30, server_default=text("30"))


class AttendanceToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "attendance_tokens"
    __table_args__ = (
        Index("ix_attendance_tokens_code_hash", "code_hash"),
        Index("ix_attendance_tokens_session_id", "session_id"),
        Index("ix_attendance_tokens_expires_at", "expires_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attendance_sessions.id", ondelete="CASCADE"))
    # Denormalised so "token belongs to this event" is a direct comparison.
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column()


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id"),
        Index("ix_attendance_records_user_id", "user_id"),
        Index("ix_attendance_records_event_id_status", "event_id", "status"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendance_sessions.id", ondelete="SET NULL"))
    token_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("attendance_tokens.id", ondelete="SET NULL"))
    method: Mapped[AttendanceMethod] = mapped_column(enum_column(AttendanceMethod))
    status: Mapped[AttendanceStatus] = mapped_column(
        enum_column(AttendanceStatus), default=AttendanceStatus.VERIFIED, server_default=AttendanceStatus.VERIFIED.value
    )
    checked_in_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # An administrator added the member by hand (status PENDING until the super admin approves).
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Set when an admin confirmed or created the record manually.
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column()
    suspicious_reason: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
