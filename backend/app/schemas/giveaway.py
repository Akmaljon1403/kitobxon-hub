from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, Field

from app.models.enums import GiveawayAudience, GiveawayRule, GiveawayStatus


class GiveawayIn(BaseModel):
    title: str = Field(min_length=3, max_length=255, description="E.g. «Oy testi g'olibi»")
    reward_id: uuid.UUID
    rule: GiveawayRule
    audience: GiveawayAudience = GiveawayAudience.ALL
    winners_count: int = Field(ge=1, le=100, description="EVENT_PLACES: places per event (1-10)")
    premium_bonus: bool = True
    period_start: date
    period_end: date
    scheduled_at: AwareDatetime | None = Field(default=None, description="Drawn automatically at this time")
    announce: bool = True
    repeat_monthly: bool = False


class GiveawayUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    reward_id: uuid.UUID | None = None
    rule: GiveawayRule | None = None
    audience: GiveawayAudience | None = None
    winners_count: int | None = Field(default=None, ge=1, le=100)
    premium_bonus: bool | None = None
    period_start: date | None = None
    period_end: date | None = None
    scheduled_at: AwareDatetime | None = None
    announce: bool | None = None
    repeat_monthly: bool | None = None


class GiveawayWinnerOut(BaseModel):
    user_id: uuid.UUID | None = None
    name: str
    full_name: str | None = None
    reason: str
    place: int | None = None
    error: str | None = None


class GiveawayOut(BaseModel):
    id: uuid.UUID
    title: str
    reward_id: uuid.UUID
    reward_title: str
    codes_available: int | None = Field(description="None: the reward has no codes")
    rule: GiveawayRule
    rule_title: str
    audience: GiveawayAudience
    winners_count: int
    premium_bonus: bool
    period_start: date
    period_end: date
    period_label: str
    status: GiveawayStatus
    scheduled_at: datetime | None
    announce: bool
    repeat_monthly: bool
    drawn_at: datetime | None
    seed: str | None
    winners: list[GiveawayWinnerOut]
    created_at: datetime


class GiveawayPreviewOut(BaseModel):
    eligible: int
    premium: int
    winners: list[GiveawayWinnerOut]
    codes_available: int | None
    notes: list[str]


class PublicWinnerOut(BaseModel):
    name: str
    reason: str
    place: int | None = None


class PublicGiveawayOut(BaseModel):
    id: uuid.UUID
    title: str
    reward: str
    rule: GiveawayRule
    rule_title: str
    winners_count: int
    period: str
    premium_bonus: bool
    audience: GiveawayAudience
    scheduled_at: datetime | None
    drawn_at: datetime | None
    winners: list[PublicWinnerOut]


class MemberGiveawaysOut(BaseModel):
    upcoming: list[PublicGiveawayOut]
    recent: list[PublicGiveawayOut]
