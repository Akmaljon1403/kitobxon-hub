from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import UserStatus


class FacultyOut(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None


class MeOut(BaseModel):
    """The signed-in member's own profile (only ever returned to that member)."""

    id: uuid.UUID
    member_number: str
    first_name: str
    last_name: str
    telegram_username: str | None
    photo_url: str | None
    phone: str | None
    faculty: FacultyOut | None
    course: int | None
    group_name: str | None
    status: UserStatus
    registered_at: datetime | None
    is_admin: bool
    roles: list[str]
    max_course: int


class MeUpdateIn(BaseModel):
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=8)
    group_name: str | None = Field(default=None, min_length=1, max_length=16)


class NotificationSettingsOut(BaseModel):
    event_reminders: bool
    test_reminders: bool
    reading_reminders: bool
    quote_of_day: bool
    ranking_updates: bool
    achievement_alerts: bool


class NotificationSettingsIn(BaseModel):
    event_reminders: bool | None = None
    test_reminders: bool | None = None
    reading_reminders: bool | None = None
    quote_of_day: bool | None = None
    ranking_updates: bool | None = None
    achievement_alerts: bool | None = None


class AdminUserOut(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    telegram_username: str | None
    phone: str | None = Field(description="Only returned with the USER_CONTACT_VIEW permission")
    faculty_id: uuid.UUID | None
    faculty_name: str | None
    course: int | None
    group_name: str | None
    status: UserStatus
    registered_at: datetime | None
    last_seen_at: datetime | None


class AdminUserDetailOut(AdminUserOut):
    roles: list[str]


class AdminUserUpdateIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=2, max_length=64)
    last_name: str | None = Field(default=None, min_length=2, max_length=64)
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=8)
    group_name: str | None = Field(default=None, min_length=1, max_length=16)


class UserStatusIn(BaseModel):
    status: UserStatus
    reason: str = Field(min_length=5, max_length=1000)
