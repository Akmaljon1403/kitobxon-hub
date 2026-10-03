"""Official reports (of an event, of a period, or on any topic) and their photos.

``facts_snapshot`` holds the statistics loaded from the database when the report was
prepared (counts, percentages, names of responsible people). The AI draft may only use
those facts; every number in it is cross-checked before approval.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import ReportKind, ReportStatus


class Report(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("event_id", "version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("kind <> 'EVENT' OR event_id IS NOT NULL", name="event_required"),
        CheckConstraint(
            "kind <> 'PERIOD' OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_end >= period_start)",
            name="period_required",
        ),
        Index("ix_reports_status", "status"),
    )

    kind: Mapped[ReportKind] = mapped_column(
        enum_column(ReportKind), default=ReportKind.EVENT, server_default=ReportKind.EVENT.value
    )
    # Set for EVENT reports; PERIOD reports cover period_start..period_end (dates, inclusive).
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="RESTRICT"))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    status: Mapped[ReportStatus] = mapped_column(
        enum_column(ReportStatus), default=ReportStatus.DRAFT, server_default=ReportStatus.DRAFT.value
    )
    title: Mapped[str] = mapped_column(String(255))
    # Admin-provided content.
    objective: Mapped[str | None] = mapped_column(Text)
    activity_description: Mapped[str | None] = mapped_column(Text)
    results: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    # Facts from the database at preparation time.
    facts_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Formal text drafted by AI (or written by hand), edited and approved by an admin.
    body_text: Mapped[str | None] = mapped_column(Text)
    ai_model: Mapped[str | None] = mapped_column(String(64))
    ai_generated_at: Mapped[datetime | None] = mapped_column()
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column()
    pdf_object_key: Mapped[str | None] = mapped_column(String(512))
    pdf_generated_at: Mapped[datetime | None] = mapped_column()
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    archived_at: Mapped[datetime | None] = mapped_column()


class ReportPhoto(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "report_photos"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_positive"),
        Index("ix_report_photos_report_id", "report_id"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"))
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    caption: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
