from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import BackupKind, BackupStatus


class BackupOut(BaseModel):
    id: uuid.UUID
    kind: BackupKind
    status: BackupStatus
    size_bytes: int
    sha256: str | None
    encrypted: bool = False
    in_drive: bool = False  # a copy also exists on Google Drive
    db_name: str | None
    error: str | None
    created_at: datetime
    created_by_name: str | None = None


class BackupSummaryOut(BaseModel):
    enabled: bool
    encryption_enabled: bool
    gdrive_enabled: bool  # a second copy of each backup is also sent to Google Drive
    # Whether a super admin may overwrite the live database from the panel (ALLOW_IN_APP_RESTORE).
    restore_live_enabled: bool
    retention_daily: int
    retention_monthly: int
    last_success_at: datetime | None
    total: int
    backups: list[BackupOut]


class RestoreIn(BaseModel):
    # Must equal backups.RESTORE_CONFIRM_PHRASE; the panel asks the admin to type it.
    confirm: str = Field(min_length=1, max_length=100)
    # Request the live overwrite (only honoured when ALLOW_IN_APP_RESTORE is on); otherwise validate only.
    live: bool = False


class RestoreResultOut(BaseModel):
    validated: bool
    entries: int
    pre_restore_backup_id: uuid.UUID
    live_restored: bool
    live_available: bool
    message: str
