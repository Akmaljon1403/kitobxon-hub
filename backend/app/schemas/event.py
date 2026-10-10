from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import AttendanceMethod, AttendanceStatus, EventStatus


class ShiftIn(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    attendance_opens_at: AwareDatetime | None = Field(default=None, description="Default: 10 minutes before start")
    attendance_closes_at: AwareDatetime | None = Field(default=None, description="Default: 20 minutes after start")
    capacity: int | None = Field(default=None, ge=1, le=100_000)


class ShiftOut(BaseModel):
    id: uuid.UUID
    position: int
    starts_at: datetime
    ends_at: datetime
    attendance_opens_at: datetime
    attendance_closes_at: datetime
    capacity: int | None
    registered_count: int = 0


class EventCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    book_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    attendance_opens_at: AwareDatetime | None = Field(default=None, description="Default: 10 minutes before start")
    attendance_closes_at: AwareDatetime | None = Field(default=None, description="Default: 20 minutes after start")
    attendance_points: int | None = Field(default=None, ge=0, le=1000, description="Empty = value from settings")
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    responsible_admin_id: uuid.UUID | None = None
    status: Literal["DRAFT", "PUBLISHED"] = "DRAFT"
    shifts: list[ShiftIn] | None = Field(
        default=None, max_length=6, description="Two or more shifts on the same day (each opens attendance itself)"
    )

    @model_validator(mode="after")
    def _times(self) -> EventCreateIn:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    book_id: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    attendance_opens_at: AwareDatetime | None = None
    attendance_closes_at: AwareDatetime | None = None
    attendance_points: int | None = Field(default=None, ge=0, le=1000)
    capacity: int | None = Field(default=None, ge=1, le=100_000)
    responsible_admin_id: uuid.UUID | None = None
    status: EventStatus | None = None
    shifts: list[ShiftIn] | None = Field(default=None, max_length=6, description="Replaces the shifts ([] = none)")


class EventBaseOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    book_id: uuid.UUID | None
    book_title: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime
    attendance_opens_at: datetime
    attendance_closes_at: datetime
    attendance_points: int
    capacity: int | None
    status: EventStatus
    registered_count: int
    attended_count: int
    shifts: list[ShiftOut] = []
    rating: float | None = None
    ratings_count: int = 0


class EventAdminOut(EventBaseOut):
    certificate_background: bool = False
    attendance_points_override: int | None
    responsible_admin_id: uuid.UUID | None
    attendance_open: bool
    created_at: datetime
    pending_requests: int = 0


class EventOut(EventBaseOut):
    is_registered: bool
    my_attendance: AttendanceStatus | None
    my_shift_id: uuid.UUID | None = None


class RegisterIn(BaseModel):
    shift_id: uuid.UUID | None = Field(default=None, description="Required when the event has shifts")


class TopEventOut(BaseModel):
    event_id: uuid.UUID
    title: str
    starts_at: datetime
    average: float
    ratings: int


class RegistrationOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    group_name: str | None
    status: str
    registered_at: datetime
    shift: int | None = None


class CheckInIn(BaseModel):
    token: str | None = Field(default=None, max_length=300, description="Scanned QR content or token")
    code: str | None = Field(default=None, min_length=6, max_length=6, pattern=r"^[A-Za-z0-9]{6}$")
    event_id: uuid.UUID | None = Field(default=None, description="The event the member is checking in to, if known")


class CheckInOut(BaseModel):
    event_id: uuid.UUID
    event_title: str
    points: int
    checked_in_at: datetime


class LiveAttendanceOut(BaseModel):
    event_id: uuid.UUID
    title: str
    location: str | None
    starts_at: datetime
    closes_at: datetime
    checked_in: bool


class AttendanceSessionIn(BaseModel):
    minutes: int | None = Field(default=None, ge=1, le=600, description="Keep attendance open for N minutes")


class AttendanceTokenOut(BaseModel):
    qr_payload: str = Field(description="Text to encode in the QR code")
    token: str
    code: str
    expires_at: datetime
    rotates_at: datetime
    session_closes_at: datetime


class AttendanceRecordOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    faculty_name: str | None
    course: int | None
    group_name: str | None
    method: AttendanceMethod
    status: AttendanceStatus
    checked_in_at: datetime
    suspicious_reason: str | None
    note: str | None
    requested_by_name: str | None = None


class AttendanceOverviewOut(BaseModel):
    event_id: uuid.UUID
    is_open: bool
    closes_at: datetime | None
    shift: int | None = None
    can_approve: bool = False
    registered_count: int
    attended_count: int
    records: list[AttendanceRecordOut]


class ManualCheckInIn(BaseModel):
    user_id: uuid.UUID
    note: str = Field(min_length=5, max_length=1000, description="Why the member is added manually")


class RejectIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class RecordStatusIn(BaseModel):
    status: AttendanceStatus
    reason: str = Field(min_length=5, max_length=1000)
