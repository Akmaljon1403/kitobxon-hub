from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import UserStatus


class FacultyOut(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None


class SubscriptionChannelOut(BaseModel):
    title: str
    url: str


class SubscriptionOut(BaseModel):
    ok: bool
    channels: list[SubscriptionChannelOut]


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
    # What the super admin switched on: feature code -> "on" | "premium" (needs Premium) | "off".
    features: dict[str, str]
    is_premium: bool
    premium_until: datetime | None
    premium_lifetime: bool = False
    passport_photo: bool  # the member uploaded their own passport photo
    # Premium only thanks to the free trial: the app marks what belongs to Premium.
    premium_trial: bool = False
    premium_features: list[str] = []  # feature codes that need Premium
    # Required channels the member has not joined (empty: nothing to do).
    subscription_missing: list[SubscriptionChannelOut] = []


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
    left_at: datetime | None = None
    left_reason: str | None = None
    restore_requested_at: datetime | None = None


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


class EraseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
    confirm: str = Field(description="Type O'CHIRISH to confirm: the personal data cannot be brought back")


class ReferralsOut(BaseModel):
    enabled: bool
    link: str | None = Field(description="https://t.me/<bot>?start=ref_<member number>")
    invited: int
    rewarded: int
    points: int = Field(description="Points for each friend who comes to an event")
    premium_days: int
    monthly_limit: int = Field(description="Rewards a month at most (0 — no limit)")
