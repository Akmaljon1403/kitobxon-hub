from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import CampaignStatus


class CampaignBookOut(BaseModel):
    id: uuid.UUID
    title: str
    author: str


class CampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    status: CampaignStatus
    points_per_book: int
    completion_bonus: int
    books: list[CampaignBookOut]
    participants: int
    verified: int
    # Set when the contest was attached to an event (its window follows the event); managed there too.
    event_id: uuid.UUID | None = None


class CampaignUpsertIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    points_per_book: int = Field(default=0, ge=0, le=1000)
    completion_bonus: int = Field(default=0, ge=0, le=1000)
    book_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _dates(self) -> CampaignUpsertIn:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CampaignStatusIn(BaseModel):
    status: CampaignStatus
    announce: bool = Field(default=False, description="Post the contest to the channel when activating")


class CampaignParticipantOut(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    member_number: str
    group_name: str | None
    completed_at: datetime | None
    verified_at: datetime | None
