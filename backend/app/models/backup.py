"""Database backup records: one row per dump created by pg_dump (automatic or manual)."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import BackupKind, BackupStatus


class Backup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "backups"
    __table_args__ = (Index("ix_backups_created_at", "created_at"),)

    kind: Mapped[BackupKind] = mapped_column(enum_column(BackupKind))
    status: Mapped[BackupStatus] = mapped_column(enum_column(BackupStatus))
    # Where the dump is kept in the configured file storage (None when the dump failed).
    storage_key: Mapped[str | None] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default=text("0"))
    sha256: Mapped[str | None] = mapped_column(String(64))  # integrity check for the stored file
    db_name: Mapped[str | None] = mapped_column(String(128))
    # A short, secret-free reason when a backup failed (never the connection string).
    error: Mapped[str | None] = mapped_column(Text)
    # The super admin who pressed «Hozir zaxira olish» (None for the automatic nightly/monthly ones).
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
