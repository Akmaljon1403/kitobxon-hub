"""Admin Panel: referral contests («🏁 Taklif tanlovlari») and the all-time inviters."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import ReferralContest
from app.models.enums import ContestRule, ContestStatus
from app.security.permissions import Perm
from app.services import contests as contest_service

router = APIRouter(prefix="/admin/referral-contests", tags=["admin: referral contests"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.REWARD_MANAGE))]
NameFormat = Literal["FULL", "SHORT", "HIDDEN"]


class PrizeIn(BaseModel):
    place: int = Field(ge=1, le=50)
    points: int = Field(default=0, ge=0, le=10_000)
    premium_days: int = Field(default=0, ge=0, le=366)
    reward_id: uuid.UUID | None = None
    text: str | None = Field(default=None, max_length=200, description="A prize handed over in person")


class ContestFields(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    rule: ContestRule | None = None
    min_friend_points: int | None = Field(default=None, ge=0, le=10_000)
    min_friends: int | None = Field(default=None, ge=1, le=1000)
    winners_count: int | None = Field(default=None, ge=1, le=50)
    prizes: list[PrizeIn] | None = Field(default=None, max_length=50)
    participation_points: int | None = Field(default=None, ge=0, le=1000)
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=8)
    show_leaderboard: bool | None = None
    leaderboard_size: int | None = Field(default=None, ge=0, le=100)
    show_counts: bool | None = None
    name_format: NameFormat | None = None
    show_my_place: bool | None = None
    show_prizes: bool | None = None
    freeze_hours: int | None = Field(default=None, ge=0, le=168)
    announce: bool | None = None
    remind_hours: int | None = Field(default=None, ge=0, le=168)
    announce_results: bool | None = None
    post_to_channel: bool | None = None


class ContestIn(ContestFields):
    title: str = Field(min_length=3, max_length=255)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def _period(self) -> ContestIn:
        if self.ends_at <= self.starts_at:
            raise ValueError("Tugash vaqti boshlanishidan keyin bo'lsin.")
        return self


class ReasonIn(BaseModel):
    reason: str = Field(default="", max_length=300)


class ContestOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    status: str
    state: str
    rule: str
    rule_text: str
    min_friend_points: int
    min_friends: int
    winners_count: int
    prizes: list[dict[str, Any]]
    participation_points: int
    faculty_id: uuid.UUID | None
    course: int | None
    show_leaderboard: bool
    leaderboard_size: int
    show_counts: bool
    name_format: str
    show_my_place: bool
    show_prizes: bool
    freeze_hours: int
    announce: bool
    remind_hours: int
    announce_results: bool
    post_to_channel: bool
    announced_at: datetime | None
    finished_at: datetime | None
    excluded: list[dict[str, Any]]
    results: list[dict[str, Any]] | None


class StandingOut(BaseModel):
    place: int
    user_id: uuid.UUID
    name: str
    faculty: str | None
    group_name: str | None
    friends: int
    winner: bool


def _state(contest: ReferralContest) -> str:
    if contest.status == ContestStatus.PUBLISHED:
        return "running" if contest_service.running(contest) else "upcoming"
    return str(contest.status).lower()


def _out(contest: ReferralContest) -> ContestOut:
    return ContestOut(
        id=contest.id,
        title=contest.title,
        description=contest.description,
        starts_at=contest.starts_at,
        ends_at=contest.ends_at,
        status=str(contest.status),
        state=_state(contest),
        rule=str(contest.rule),
        rule_text=contest_service.rule_text(contest),
        min_friend_points=contest.min_friend_points,
        min_friends=contest.min_friends,
        winners_count=contest.winners_count,
        prizes=list(contest.prizes or []),
        participation_points=contest.participation_points,
        faculty_id=contest.faculty_id,
        course=contest.course,
        show_leaderboard=contest.show_leaderboard,
        leaderboard_size=contest.leaderboard_size,
        show_counts=contest.show_counts,
        name_format=contest.name_format,
        show_my_place=contest.show_my_place,
        show_prizes=contest.show_prizes,
        freeze_hours=contest.freeze_hours,
        announce=contest.announce,
        remind_hours=contest.remind_hours,
        announce_results=contest.announce_results,
        post_to_channel=contest.post_to_channel,
        announced_at=contest.announced_at,
        finished_at=contest.finished_at,
        excluded=list(contest.excluded or []),
        results=contest.results,
    )


def _values(payload: ContestFields, *, partial: bool) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=partial, exclude_none=not partial)
    if partial:
        # Only nullable fields may be cleared; the rest ignore an explicit null.
        values = {
            key: value
            for key, value in values.items()
            if value is not None or key in {"description", "faculty_id", "course"}
        }
    if "prizes" in values and values["prizes"] is not None:
        values["prizes"] = [
            {**prize, "reward_id": str(prize["reward_id"]) if prize.get("reward_id") else None}
            for prize in values["prizes"]
        ]
    return values


@router.get("", response_model=list[ContestOut], summary="All referral contests, newest first")
async def list_contests(_: Manager, db: DbSession) -> list[ContestOut]:
    from sqlalchemy import select

    contests = await db.scalars(select(ReferralContest).order_by(ReferralContest.starts_at.desc()).limit(200))
    return [_out(contest) for contest in contests]


@router.post("", response_model=ContestOut, status_code=status.HTTP_201_CREATED, summary="Prepare a contest (draft)")
async def create_contest(payload: ContestIn, current: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.create(db, actor_id=current.id, data=_values(payload, partial=False)))


@router.get("/top-inviters", summary="All time: members who brought the most friends")
async def top_inviters(
    _: Manager,
    db: DbSession,
    rule: Literal["ATTENDED", "REGISTERED"] = "ATTENDED",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    return await contest_service.top_inviters(db, rule=rule, limit=limit)


@router.get("/{contest_id}", response_model=ContestOut, summary="One contest")
async def get_contest(contest_id: uuid.UUID, _: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.get(db, contest_id))


@router.patch("/{contest_id}", response_model=ContestOut, summary="Change a contest (rules are locked once it runs)")
async def update_contest(contest_id: uuid.UUID, payload: ContestFields, current: Manager, db: DbSession) -> ContestOut:
    return _out(
        await contest_service.update(
            db, actor_id=current.id, contest_id=contest_id, changes=_values(payload, partial=True)
        )
    )


@router.post("/{contest_id}/publish", response_model=ContestOut, summary="Announce: members are told at the start")
async def publish_contest(contest_id: uuid.UUID, current: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.publish(db, actor_id=current.id, contest_id=contest_id))


@router.post("/{contest_id}/finish", response_model=ContestOut, summary="Finish now: winners and prizes")
async def finish_contest(contest_id: uuid.UUID, current: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.finish(db, contest_id=contest_id, actor_id=current.id))


@router.post("/{contest_id}/cancel", response_model=ContestOut, summary="Cancel (members are told if it was announced)")
async def cancel_contest(contest_id: uuid.UUID, payload: ReasonIn, current: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.cancel(db, actor_id=current.id, contest_id=contest_id, reason=payload.reason))


@router.get(
    "/{contest_id}/standings", response_model=list[StandingOut], summary="The full table (admins see everything)"
)
async def contest_standings(
    contest_id: uuid.UUID, _: Manager, db: DbSession, limit: Annotated[int, Query(ge=1, le=1000)] = 200
) -> list[StandingOut]:
    contest = await contest_service.get(db, contest_id)
    rows = await contest_service.standings(db, contest, limit=limit)
    return [
        StandingOut(
            place=row.place,
            user_id=row.user_id,
            name=f"{row.last_name} {row.first_name}",
            faculty=row.faculty,
            group_name=row.group_name,
            friends=row.friends,
            winner=row.place <= contest.winners_count and row.friends >= contest.min_friends,
        )
        for row in rows
    ]


@router.get("/{contest_id}/participants/{user_id}/friends", summary="The friends a participant brought (to check them)")
async def participant_friends(
    contest_id: uuid.UUID, user_id: uuid.UUID, _: Manager, db: DbSession
) -> list[dict[str, Any]]:
    contest = await contest_service.get(db, contest_id)
    return await contest_service.friends_of(db, contest, user_id)


@router.post("/{contest_id}/participants/{user_id}/exclude", response_model=ContestOut, summary="Remove from the table")
async def exclude_participant(
    contest_id: uuid.UUID, user_id: uuid.UUID, payload: ReasonIn, current: Manager, db: DbSession
) -> ContestOut:
    return _out(
        await contest_service.set_excluded(
            db, actor_id=current.id, contest_id=contest_id, user_id=user_id, reason=payload.reason
        )
    )


@router.post("/{contest_id}/participants/{user_id}/include", response_model=ContestOut, summary="Put back in the table")
async def include_participant(contest_id: uuid.UUID, user_id: uuid.UUID, current: Manager, db: DbSession) -> ContestOut:
    return _out(
        await contest_service.set_excluded(db, actor_id=current.id, contest_id=contest_id, user_id=user_id, reason=None)
    )


@router.post(
    "/{contest_id}/winners/{user_id}/handed-over", response_model=ContestOut, summary="A prize was handed over"
)
async def handed_over(contest_id: uuid.UUID, user_id: uuid.UUID, current: Manager, db: DbSession) -> ContestOut:
    return _out(await contest_service.mark_handed_over(db, actor_id=current.id, contest_id=contest_id, user_id=user_id))
