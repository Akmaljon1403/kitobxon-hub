"""Seasons (competition periods) and reading campaigns."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import CampaignStatus, SeasonStatus


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


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A reading campaign such as "1 hafta — 1 kitob" with its own scoring rules."""

    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="dates_order"),
        CheckConstraint("points_per_book >= 0 AND completion_bonus >= 0", name="points_non_negative"),
        Index("ix_campaigns_season_id", "season_id"),
        # At most one (live) contest may be tied to a given event: one tadbir → one tanlov.
        Index(
            "uq_campaigns_event_id",
            "event_id",
            unique=True,
            postgresql_where=text("event_id IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    # A reading contest may be attached to one event (created inside the event window); NULL means stand-alone.
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[CampaignStatus] = mapped_column(
        enum_column(CampaignStatus), default=CampaignStatus.DRAFT, server_default=CampaignStatus.DRAFT.value
    )
    # Scoring rules: points for each verified completed campaign book, bonus for completing all of them.
    points_per_book: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    completion_bonus: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class CampaignBook(Base):
    __tablename__ = "campaign_books"
    __table_args__ = (Index("ix_campaign_books_book_id", "book_id"),)

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True)
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class CampaignParticipant(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One member's taking part in one reading contest. Keyed by (campaign, member), so two contests
    running at the same time — even on the same book — never mix: each has its own participants."""

    __tablename__ = "campaign_participants"
    __table_args__ = (
        UniqueConstraint("campaign_id", "user_id", name="uq_campaign_participant"),
        Index("ix_campaign_participants_campaign_id", "campaign_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # The member said they finished the contest's book(s); an admin then confirms it.
    completed_at: Mapped[datetime | None] = mapped_column()
    verified_at: Mapped[datetime | None] = mapped_column()
    verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Points (points_per_book + completion_bonus) given once, when an admin confirms.
    points_awarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
