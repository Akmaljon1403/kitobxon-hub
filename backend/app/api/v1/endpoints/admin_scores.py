"""Admin Panel: points history, manual corrections, reversals and seasons."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import Season
from app.schemas.common import Page
from app.schemas.score import AdminScoreEntryOut, ReverseIn, ScoreAdjustIn, SeasonIn, SeasonOut
from app.security.permissions import Perm
from app.services import ranking as ranking_service
from app.services import scoring
from app.services import seasons as season_service

router = APIRouter(prefix="/admin", tags=["admin: scores and seasons"])
ScoreViewer = Annotated[CurrentUser, Depends(require_permissions(Perm.SCORE_VIEW))]
ScoreManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SCORE_VIEW, Perm.SCORE_MANAGE))]
SeasonManager = Annotated[CurrentUser, Depends(require_permissions(Perm.SEASON_MANAGE))]


@router.get("/scores", response_model=Page[AdminScoreEntryOut], summary="Score ledger (optionally of one member)")
async def list_scores(
    _: ScoreViewer,
    db: DbSession,
    user_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminScoreEntryOut]:
    items, total = await ranking_service.transaction_history(db, user_id=user_id, limit=limit, offset=offset)
    return Page[AdminScoreEntryOut](
        items=[AdminScoreEntryOut(**item) for item in items], total=total, limit=limit, offset=offset
    )


@router.get("/scores/summary", summary="A member's total and breakdown")
async def score_summary(user_id: uuid.UUID, _: ScoreViewer, db: DbSession) -> dict:
    return await ranking_service.score_summary(db, user_id)


@router.post("/scores/adjust", status_code=status.HTTP_201_CREATED, summary="Add or remove points (reason required)")
async def adjust(payload: ScoreAdjustIn, current: ScoreManager, db: DbSession) -> dict[str, uuid.UUID]:
    transaction_id = await scoring.manual_adjustment(
        db, actor_id=current.user.id, user_id=payload.user_id, amount=payload.amount, reason=payload.reason
    )
    return {"transaction_id": transaction_id}


@router.post("/scores/{transaction_id}/reverse", status_code=status.HTTP_201_CREATED, summary="Cancel one ledger entry")
async def reverse(transaction_id: uuid.UUID, payload: ReverseIn, current: ScoreManager, db: DbSession) -> dict:
    reversal_id = await scoring.reverse_transaction(
        db, actor_id=current.user.id, transaction_id=transaction_id, reason=payload.reason
    )
    return {"transaction_id": reversal_id}


def _season_out(season: Season) -> SeasonOut:
    return SeasonOut(
        id=season.id,
        name=season.name,
        starts_on=season.starts_on,
        ends_on=season.ends_on,
        status=season.status.value,
        is_current=season.is_current,
    )


@router.get("/seasons", response_model=list[SeasonOut], summary="Seasons")
async def list_seasons(_: ScoreViewer, db: DbSession) -> list[SeasonOut]:
    return [_season_out(season) for season in await season_service.list_seasons(db)]


@router.post("/seasons", response_model=SeasonOut, status_code=status.HTTP_201_CREATED, summary="Create a season")
async def create_season(payload: SeasonIn, current: SeasonManager, db: DbSession) -> SeasonOut:
    season = await season_service.create_season(
        db,
        actor_id=current.user.id,
        name=payload.name,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        make_current=payload.make_current,
    )
    return _season_out(season)


@router.post("/seasons/{season_id}/activate", response_model=SeasonOut, summary="Make this the current season")
async def activate_season(season_id: uuid.UUID, current: SeasonManager, db: DbSession) -> SeasonOut:
    return _season_out(await season_service.activate_season(db, actor_id=current.user.id, season_id=season_id))
