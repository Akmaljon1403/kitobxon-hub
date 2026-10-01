from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AchievementCriteria


class AchievementOut(BaseModel):
    code: str
    title: str
    description: str
    icon: str
    criteria: AchievementCriteria
    threshold: int
    points: int
    progress: int | None
    unlocked_at: datetime | None


class AchievementAdminOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    description: str
    icon: str
    criteria: AchievementCriteria
    threshold: int
    points: int
    is_active: bool
    sort_order: int
    holders: int


class AchievementCreateIn(BaseModel):
    code: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    title: str = Field(min_length=2, max_length=128)
    description: str = Field(min_length=2, max_length=1000)
    icon: str = Field(default="🏅", min_length=1, max_length=16)
    criteria: AchievementCriteria
    threshold: int = Field(default=1, ge=1, le=1000)
    points: int = Field(default=0, ge=0, le=1000)
    is_active: bool = True
    sort_order: int = Field(default=100, ge=0, le=10_000)


class AchievementUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=128)
    description: str | None = Field(default=None, min_length=2, max_length=1000)
    icon: str | None = Field(default=None, min_length=1, max_length=16)
    threshold: int | None = Field(default=None, ge=1, le=1000)
    points: int | None = Field(default=None, ge=0, le=1000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class AchievementHolderOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    group_name: str | None
    unlocked_at: datetime
    granted: bool


class GrantIn(BaseModel):
    user_id: uuid.UUID
    reason: str = Field(min_length=5, max_length=1000)
