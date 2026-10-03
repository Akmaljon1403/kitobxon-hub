from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScoreEntryOut(BaseModel):
    id: uuid.UUID
    amount: int
    category: str
    effective_category: str
    source_type: str | None
    source_title: str | None
    reason: str | None
    is_reversed: bool
    created_at: datetime


class AdminScoreEntryOut(ScoreEntryOut):
    user_id: uuid.UUID
    user_name: str


class SeasonTotal(BaseModel):
    name: str | None
    total: int


class MyScoresOut(BaseModel):
    total: int
    breakdown: dict[str, int]
    season: SeasonTotal | None
    history: list[ScoreEntryOut]


class RankingRowOut(BaseModel):
    rank: int
    name: str
    faculty: str | None
    group_name: str | None
    total: int
    attendance: int
    tests: int
    is_me: bool
    premium: bool = False


class RankingOut(BaseModel):
    period: Literal["week", "month", "season", "all"]
    scope: Literal["all", "faculty", "group"]
    starts_at: datetime | None
    items: list[RankingRowOut]
    me: RankingRowOut | None


class FacultyRankingOut(BaseModel):
    rank: int
    faculty: str
    members: int
    total: int
    average: float


class MyRankingOut(BaseModel):
    week: RankingRowOut | None
    month: RankingRowOut | None
    all: RankingRowOut | None


class ScoreAdjustIn(BaseModel):
    user_id: uuid.UUID
    amount: int = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=5, max_length=1000)


class ReverseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class SeasonOut(BaseModel):
    id: uuid.UUID
    name: str
    starts_on: date
    ends_on: date
    status: str
    is_current: bool


class SeasonIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    starts_on: date
    ends_on: date
    make_current: bool = True
