"""Seasons (competition periods)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import SeasonStatus


class Season(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A competition period, e.g. "Kitobxon Hub — 2026 Kuz". Closing a season never deletes data."""

    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint("ends_on >= starts_on", name="dates_order"),
        # At most one season is "current" at any time.
        Index("uq_seasons_is_current", "is_current", unique=True, postgresql_where=text("is_current")),
    )

    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    starts_on: Mapped[date] = mapped_column()
    ends_on: Mapped[date] = mapped_column()
    status: Mapped[SeasonStatus] = mapped_column(
        enum_column(SeasonStatus), default=SeasonStatus.PLANNED, server_default=SeasonStatus.PLANNED.value
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
