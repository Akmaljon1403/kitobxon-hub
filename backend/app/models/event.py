"""Club events (discussions, meetings) and members' intention to participate.

Registration ("I intend to come") is deliberately separate from attendance
("I was verified as present"), see ``attendance.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import EventStatus, RegistrationStatus


class Event(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="dates_order"),
        CheckConstraint("attendance_closes_at > attendance_opens_at", name="attendance_window_order"),
        CheckConstraint("attendance_points IS NULL OR attendance_points >= 0", name="points_non_negative"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity_positive"),
        Index("ix_events_status_starts_at", "status", "starts_at"),
        Index("ix_events_book_id", "book_id"),
        Index("ix_events_season_id", "season_id"),
    )

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    location: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    attendance_opens_at: Mapped[datetime] = mapped_column()
    attendance_closes_at: Mapped[datetime] = mapped_column()
    # NULL means "use the default from system settings".
    attendance_points: Mapped[int | None] = mapped_column(Integer)
    capacity: Mapped[int | None] = mapped_column(Integer)
    responsible_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[EventStatus] = mapped_column(
        enum_column(EventStatus), default=EventStatus.DRAFT, server_default=EventStatus.DRAFT.value
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # The club's own certificate design for this event (an image; the text is written on top).
    certificate_background_key: Mapped[str | None] = mapped_column(String(512))


class EventShift(UUIDPrimaryKeyMixin, Base):
    """One of several sessions of the same event on the same day (e.g. morning and afternoon).

    Attendance opens by itself in every shift's window; a member still checks in once per event
    (one record, one score), and registers for the shift that suits them."""

    __tablename__ = "event_shifts"
    __table_args__ = (
        UniqueConstraint("event_id", "position"),
        Index("ix_event_shifts_event_id", "event_id"),
        CheckConstraint("ends_at > starts_at", name="dates_order"),
        CheckConstraint("attendance_closes_at > attendance_opens_at", name="attendance_window_order"),
        CheckConstraint("position BETWEEN 1 AND 6", name="position_range"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity_positive"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    attendance_opens_at: Mapped[datetime] = mapped_column()
    attendance_closes_at: Mapped[datetime] = mapped_column()
    capacity: Mapped[int | None] = mapped_column(Integer)


class EventRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id"),
        Index("ix_event_registrations_user_id", "user_id"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[RegistrationStatus] = mapped_column(
        enum_column(RegistrationStatus),
        default=RegistrationStatus.REGISTERED,
        server_default=RegistrationStatus.REGISTERED.value,
    )
    registered_at: Mapped[datetime] = mapped_column(server_default=func.now())
    cancelled_at: Mapped[datetime | None] = mapped_column()
    # The chosen shift when the event has several (NULL: the event has one session).
    shift_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("event_shifts.id", ondelete="SET NULL"))


class EventFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A member's rating (1-5) and optional comment after an event they attended."""

    __tablename__ = "event_feedback"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
