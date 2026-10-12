"""Admin Panel: «🎯 Missiyalar» — personal goals for members («7 kunda 100 bet»), with how many took
and finished each."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models.enums import MissionMetric, MissionStatus
from app.security.permissions import Perm
from app.services import missions

router = APIRouter(prefix="/admin/missions", tags=["admin: missions"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.SEASON_MANAGE))]


class MissionIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    icon: str = Field(default="🎯", min_length=1, max_length=16)
    metric: MissionMetric
    target: int = Field(gt=0, le=100_000)
    period_days: int = Field(gt=0, le=366)
    reward_points: int = Field(default=0, ge=0, le=1000)
    status: MissionStatus = MissionStatus.ACTIVE


class AdminMissionOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    metric: MissionMetric
    metric_title: str
    unit: str
    target: int
    period_days: int
    reward_points: int
    status: MissionStatus
    taken: int
    completed: int
    running: int
    completion_rate: int | None


class MetricOut(BaseModel):
    code: MissionMetric
    title: str
    unit: str


@router.get("", response_model=list[AdminMissionOut], summary="Missions with how many took and finished them")
async def list_missions(_: Manager, db: DbSession) -> list[AdminMissionOut]:
    return [
        AdminMissionOut(**{key: value for key, value in item.items() if key in AdminMissionOut.model_fields})
        for item in await missions.admin_list(db)
    ]


@router.get("/metrics", response_model=list[MetricOut], summary="What a mission can count")
async def metrics(_: Manager) -> list[MetricOut]:
    return [MetricOut(code=code, title=title, unit=unit) for code, (unit, title) in missions.METRICS.items()]


@router.post("", response_model=dict[str, str], summary="Create a mission")
async def create_mission(payload: MissionIn, current: Manager, db: DbSession) -> dict[str, str]:
    mission = await missions.save(db, actor_id=current.user.id, data=payload.model_dump())
    return {"id": str(mission.id)}


@router.put("/{mission_id}", response_model=dict[str, str], summary="Change a mission (or archive it)")
async def update_mission(mission_id: uuid.UUID, payload: MissionIn, current: Manager, db: DbSession) -> dict[str, str]:
    mission = await missions.save(db, actor_id=current.user.id, data=payload.model_dump(), mission_id=mission_id)
    return {"id": str(mission.id)}


# ---------------------------------------------------------------------------- members' own missions


class PersonalMissionOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    metric: MissionMetric
    unit: str
    target: int
    period_days: int
    status: str | None
    progress: int
    deadline: datetime | None
    completed_at: datetime | None
    owner_id: uuid.UUID
    owner_name: str
    group_name: str | None
    created_at: datetime


class PopularOut(BaseModel):
    metric: MissionMetric
    title: str
    count: int


class PersonalOverviewOut(BaseModel):
    created: int
    members: int
    running: int
    completed: int
    popular: list[PopularOut]
    items: list[PersonalMissionOut]


@router.get("/personal", response_model=PersonalOverviewOut, summary="Missions members set for themselves")
async def personal_missions(_: Manager, db: DbSession) -> PersonalOverviewOut:
    data = await missions.personal_overview(db)
    fields = PersonalMissionOut.model_fields
    items = [
        PersonalMissionOut(**{key: value for key, value in item.items() if key in fields}) for item in data["items"]
    ]
    return PersonalOverviewOut(**{**data, "items": items})


@router.post("/personal/{mission_id}/promote", response_model=dict[str, str], summary="Make it a club mission (draft)")
async def promote_personal(mission_id: uuid.UUID, current: Manager, db: DbSession) -> dict[str, str]:
    mission = await missions.promote_personal(db, actor_id=current.user.id, mission_id=mission_id)
    return {"id": str(mission.id)}


@router.delete("/personal/{mission_id}", status_code=204, summary="Remove a member's own mission")
async def remove_personal(mission_id: uuid.UUID, current: Manager, db: DbSession) -> None:
    await missions.remove_personal(db, actor_id=current.user.id, mission_id=mission_id)
