from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import BackupKind, BackupStatus


class BackupOut(BaseModel):
    id: uuid.UUID
    kind: BackupKind
    status: BackupStatus
    size_bytes: int
    sha256: str | None
    db_name: str | None
    error: str | None
    created_at: datetime
    created_by_name: str | None = None


class BackupSummaryOut(BaseModel):
    enabled: bool
    retention_daily: int
    retention_monthly: int
    last_success_at: datetime | None
    total: int
    backups: list[BackupOut]
