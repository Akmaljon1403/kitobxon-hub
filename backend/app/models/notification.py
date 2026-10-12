"""Notification templates and the outgoing Telegram message queue (outbox pattern).

Services only *insert* notifications; the background worker sends them with throttling,
retries and ``FOR UPDATE SKIP LOCKED`` so no message is sent twice.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import NotificationStatus, NotificationType


class NotificationTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_templates"

    type: Mapped[NotificationType] = mapped_column(enum_column(NotificationType), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    # Text with {placeholders}, rendered by the notification service.
    body: Mapped[str] = mapped_column(Text)
    # Critical messages are delivered even when the member turned reminders off.
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql_text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sql_text("true"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        # The worker's queue scan: pending messages ordered by due time.
        Index(
            "ix_notifications_pending_due",
            "priority",
            "scheduled_at",
            postgresql_where=sql_text("status = 'PENDING'"),
        ),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        # Copies of one admin request are found together to show who acted (services/copies).
        Index("ix_notifications_sync_key", "sync_key", postgresql_where=sql_text("sync_key IS NOT NULL")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(enum_column(NotificationType))
    text: Mapped[str] = mapped_column(Text)
    # Optional extras such as inline buttons: {"buttons": [{"text": ..., "url": ...}]}.
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[NotificationStatus] = mapped_column(
        enum_column(NotificationStatus), default=NotificationStatus.PENDING, server_default="PENDING"
    )
    # Lower number = sent first (0 = critical).
    priority: Mapped[int] = mapped_column(SmallInteger, default=5, server_default=sql_text("5"))
    scheduled_at: Mapped[datetime] = mapped_column(server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column()
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    # Prevents duplicates, e.g. "event_reminder:<event id>:<user id>:60".
    dedup_key: Mapped[str | None] = mapped_column(String(160), unique=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    # The request this message is a copy of (``ticket:<id>``, ``card:<id>``, …): when one admin acts, every
    # copy shows it (services/copies.py).
    sync_key: Mapped[str | None] = mapped_column(String(80))
