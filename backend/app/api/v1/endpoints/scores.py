"""My points, rankings."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUserDep, DbSession, feature_required
from app.schemas.score import FacultyRankingOut, MyRankingOut, MyScoresOut, RankingOut, RankingRowOut, ScoreEntryOut
from app.services import features, insights
from app.services import ranking as ranking_service

router = APIRouter(tags=["scores and rankings"])
# This week's club-wide ranking is free; other periods and scopes are the «ranking_full» feature.
FREE_RANKING = ("week", "all")


def _row(row: ranking_service.RankingRow | None, viewer_id) -> RankingRowOut | None:
    if row is None:
        return None
    return RankingRowOut(
        rank=row.rank,
        name=row.name,
        faculty=row.faculty,
        group_name=row.group_name,
        total=row.total,
        attendance=row.attendance,
        tests=row.tests,
        is_me=row.user_id == viewer_id,
        premium=row.premium,
    )


@router.get("/me/scores", response_model=MyScoresOut, summary="My points: total, breakdown and history")
async def my_scores(
    current: CurrentUserDep, db: DbSession, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> MyScoresOut:
    summary = await ranking_service.score_summary(db, current.user.id)
    history, _ = await ranking_service.transaction_history(db, user_id=current.user.id, limit=limit, offset=0)
    return MyScoresOut(
        total=summary["total"],
        breakdown=summary["breakdown"],
        season=summary["season"],
        history=[ScoreEntryOut(**item) for item in history],
    )


@router.get(
    "/me/ranking",
    dependencies=[feature_required("ranking")],
    response_model=MyRankingOut,
    summary="My position this week, this month and overall",
)
async def my_ranking(current: CurrentUserDep, db: DbSession) -> MyRankingOut:
    result = {}
    for period in ("week", "month", "all"):
        ranking = await ranking_service.ranking(db, period=period, scope="all", viewer=current.user, limit=0)
        result[period] = _row(ranking.me, current.user.id)
    return MyRankingOut(**result)


@router.get("/rankings", dependencies=[feature_required("ranking")], response_model=RankingOut, summary="Leaderboard")
async def rankings(
    current: CurrentUserDep,
    db: DbSession,
    period: Literal["week", "month", "season", "all"] = "all",
    scope: Literal["all", "faculty", "group"] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RankingOut:
    if (period, scope) != FREE_RANKING:
        await features.require(db, current.user, "ranking_full")
    ranking = await ranking_service.ranking(db, period=period, scope=scope, viewer=current.user, limit=limit)
    return RankingOut(
        period=ranking.period,
        scope=ranking.scope,
        starts_at=ranking.starts_at,
        items=[_row(row, current.user.id) for row in ranking.items],
        me=_row(ranking.me, current.user.id),
    )


@router.get(
    "/rankings/faculties",
    dependencies=[feature_required("ranking"), feature_required("ranking_full")],
    response_model=list[FacultyRankingOut],
    summary="Faculties by average points",
)
async def faculty_rankings(
    _: CurrentUserDep, db: DbSession, period: Literal["week", "month", "season", "all"] = "all"
) -> list[FacultyRankingOut]:
    return [FacultyRankingOut(**item) for item in await ranking_service.faculty_ranking(db, period=period)]


@router.get(
    "/me/stats",
    dependencies=[feature_required("personal_stats")],
    summary="My statistics: points per month, attendance rate, tests, ranking change",
)
async def my_stats(current: CurrentUserDep, db: DbSession) -> dict[str, Any]:
    return await insights.personal_stats(db, current.user)
