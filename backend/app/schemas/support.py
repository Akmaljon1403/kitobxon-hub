"""Members' messages to administrators (Admin Panel views)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SupportTicketKind, SupportTicketStatus


class SupportMemberOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    faculty: str | None
    course: int | None
    group_name: str | None
    telegram_username: str | None


class SupportTicketOut(BaseModel):
    id: uuid.UUID
    status: SupportTicketStatus
    kind: SupportTicketKind = SupportTicketKind.GENERAL
    unread: bool
    last_message_at: datetime
    created_at: datetime
    last_text: str
    message_count: int
    member: SupportMemberOut


class SupportMessageOut(BaseModel):
    id: uuid.UUID
    from_admin: bool
    admin_name: str | None = Field(description="Shown to administrators only; members never see it")
    text: str
    has_photo: bool
    created_at: datetime


class SupportTicketDetailOut(BaseModel):
    id: uuid.UUID
    status: SupportTicketStatus
    kind: SupportTicketKind = SupportTicketKind.GENERAL
    created_at: datetime
    member: SupportMemberOut
    messages: list[SupportMessageOut]


class SupportReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class SupportStatusIn(BaseModel):
    status: SupportTicketStatus


class SupportSummaryOut(BaseModel):
    unread: int
