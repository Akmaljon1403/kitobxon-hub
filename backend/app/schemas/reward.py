from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, Field

from app.models.enums import RewardCodeStatus, RewardStatus, RewardType, UserRewardStatus


class RewardIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=3000)
    type: RewardType
    value: str | None = Field(default=None, max_length=255, description="E.g. '20% chegirma', 'Kitob: O'tkan kunlar'")
    expires_at: AwareDatetime | None = None
    status: RewardStatus = RewardStatus.ACTIVE


class RewardUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=3000)
    type: RewardType | None = None
    value: str | None = Field(default=None, max_length=255)
    expires_at: AwareDatetime | None = None
    status: RewardStatus | None = None


class RewardOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    type: RewardType
    value: str | None
    expires_at: datetime | None
    status: RewardStatus
    codes_total: int
    codes_available: int
    recipients: int
    created_at: datetime


class CodesIn(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=500)
    expires_at: AwareDatetime | None = None


class CodesAddedOut(BaseModel):
    added: int
    duplicates: int


class RewardCodeOut(BaseModel):
    id: uuid.UUID
    masked: str
    status: RewardCodeStatus
    expires_at: datetime | None
    assigned_to: str | None
    created_at: datetime


class AssignIn(BaseModel):
    user_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)
    allow_repeat: bool = Field(default=False, description="Give again even if the member already has this reward")


class TestPlaceIn(BaseModel):
    test_id: uuid.UUID
    place: int = Field(ge=1, le=3)


class TestPlaceOut(BaseModel):
    place: int
    user_id: uuid.UUID
    name: str
    group_name: str | None
    score: int
    max_score: int
    given_reward: str | None = Field(description="The reward this place already received, if any")
    given_at: datetime | None


class TestWinnersOut(BaseModel):
    test_id: uuid.UUID
    title: str
    event_title: str | None
    closed_at: datetime
    places: list[TestPlaceOut]


class RecipientOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    first_name: str
    last_name: str
    group_name: str | None
    status: UserRewardStatus
    has_code: bool
    note: str | None
    assigned_at: datetime
    delivered_at: datetime | None
    redeemed_at: datetime | None


class RewardStatusIn(BaseModel):
    status: UserRewardStatus
    note: str | None = Field(default=None, max_length=1000)


class MemberRewardOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    type: RewardType
    value: str | None
    expires_at: datetime | None
    status: UserRewardStatus
    has_code: bool
    assigned_at: datetime
    redeemed_at: datetime | None


class RevealedCodeOut(BaseModel):
    code: str
    expires_at: datetime | None
