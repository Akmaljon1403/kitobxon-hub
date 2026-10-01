"""Members (club users), faculties and per-user notification preferences."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import UserStatus


class Faculty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Admin-managed list so that faculty rankings use consistent names."""

    __tablename__ = "faculties"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    short_name: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("course IS NULL OR (course BETWEEN 1 AND 8)", name="course_range"),
        # One Telegram phone number belongs to exactly one Telegram account.
        Index("uq_users_phone", "phone", unique=True, postgresql_where=text("phone IS NOT NULL")),
        Index("ix_users_status", "status"),
        Index("ix_users_faculty_id", "faculty_id"),
        Index("ix_users_group_name", "group_name"),
    )

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(20))
    faculty_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("faculties.id", ondelete="RESTRICT"))
    course: Mapped[int | None] = mapped_column(SmallInteger)
    group_name: Mapped[str | None] = mapped_column(String(32))
    photo_url: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str] = mapped_column(String(8), default="uz", server_default=text("'uz'"))
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus), default=UserStatus.PENDING, server_default=UserStatus.PENDING.value
    )
    registered_at: Mapped[datetime | None] = mapped_column()
    last_seen_at: Mapped[datetime | None] = mapped_column()
    # Incremented to invalidate every access token issued to this user (logout everywhere, block).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    faculty: Mapped[Faculty | None] = relationship(lazy="raise")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class UserNotificationSettings(Base):
    """Opt-outs for non-critical reminders. Critical system messages ignore these flags."""

    __tablename__ = "user_notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event_reminders: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    test_reminders: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    reading_reminders: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    quote_of_day: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    ranking_updates: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    achievement_alerts: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
