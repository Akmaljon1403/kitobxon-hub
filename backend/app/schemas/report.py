from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ReportStatus


class ReportCreateIn(BaseModel):
    event_id: uuid.UUID


class ReportUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    objective: str | None = Field(default=None, max_length=3000)
    activity_description: str | None = Field(default=None, max_length=10000)
    results: str | None = Field(default=None, max_length=5000)
    conclusion: str | None = Field(default=None, max_length=5000)
    recommendations: str | None = Field(default=None, max_length=5000)
    body_text: str | None = Field(default=None, max_length=30000)


class GenerateIn(BaseModel):
    use_ai: bool = True


class ReportListItem(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    event_title: str
    version: int
    status: ReportStatus
    title: str
    created_at: datetime
    approved_at: datetime | None
    pdf_ready: bool


class ReportPhotoOut(BaseModel):
    id: uuid.UUID
    caption: str | None
    size_bytes: int


class ReportDetailOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    version: int
    status: ReportStatus
    title: str
    objective: str | None
    activity_description: str | None
    results: str | None
    conclusion: str | None
    recommendations: str | None
    body_text: str | None
    facts: dict[str, Any]
    photos: list[ReportPhotoOut]
    number_issues: list[str]
    ai_available: bool
    ai_model: str | None
    ai_generated_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
    pdf_ready: bool
    created_at: datetime
