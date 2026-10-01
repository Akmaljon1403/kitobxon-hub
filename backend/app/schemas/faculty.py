from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class FacultyAdminOut(BaseModel):
    id: uuid.UUID
    name: str
    short_name: str | None
    is_active: bool
    sort_order: int


class FacultyIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    short_name: str | None = Field(default=None, max_length=32)
    sort_order: int = Field(default=0, ge=0, le=10_000)
    is_active: bool = True


class FacultyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    short_name: str | None = Field(default=None, max_length=32)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    is_active: bool | None = None
