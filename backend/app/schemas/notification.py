from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BroadcastIn(BaseModel):
    message: str = Field(min_length=3, max_length=3500)
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=8)
    group_name: str | None = Field(default=None, max_length=32)
    with_app_button: bool = True
    buttons: str | None = Field(default=None, max_length=2000, description="Lines «Text | https://link»")
    dry_run: bool = Field(default=False, description="Only count the recipients")
    test: bool = Field(default=False, description="Send only to me, to see it in the bot first")


class BroadcastPreviewOut(BaseModel):
    text: str  # Telegram HTML, exactly as members get it
    buttons: list[dict[str, str]]
    recipients: int


class BroadcastOut(BaseModel):
    recipients: int
    queued: bool


class BroadcastHistoryItem(BaseModel):
    at: datetime
    actor: str | None
    message: str
    recipients: int
    filters: dict[str, Any]


class NotificationSummaryOut(BaseModel):
    pending: int
    sent_24h: int
    failed_24h: int
    skipped_24h: int
    worker_enabled: bool
    bot_configured: bool
    recent_broadcasts: list[BroadcastHistoryItem]
