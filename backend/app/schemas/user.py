from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import UserStatus


class FacultyOut(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None


class MeOut(BaseModel):
    """The signed-in member's own profile (only ever returned to that member)."""

    id: uuid.UUID
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
