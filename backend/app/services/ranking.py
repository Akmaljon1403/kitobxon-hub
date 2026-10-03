"""Score summaries and deterministic rankings computed from the ledger.

Tie-break rules (documented in docs/ARCHITECTURE.md §8):
  1. total points (higher first)
  2. attendance points (higher first)
  3. test points incl. test place bonuses (higher first)
  4. time the member reached the total = their latest scoring transaction (earlier first)
  5. registration time (earlier first), then the member id (a stable final key)

A reversal is attributed to the period, season and category of the transaction it cancels,
so correcting last week's attendance never changes this week's ranking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Book, Event, Faculty, ScoreTransaction, Season, Test, User
from app.models.enums import ScoreCategory, UserStatus
from app.services.scoring import current_season_id
from app.services.settings import get_setting
from app.utils.timezone import local_tz

Period = Literal["week", "month", "season", "all"]
Scope = Literal["all", "faculty", "group"]

_original = aliased(ScoreTransaction)
EFFECTIVE_CATEGORY = case(
    (ScoreTransaction.category == ScoreCategory.REVERSAL, _original.category), else_=ScoreTransaction.category
)
EFFECTIVE_TIME = func.coalesce(_original.created_at, ScoreTransaction.created_at)
TEST_CATEGORIES = (ScoreCategory.TEST, ScoreCategory.TEST_RANK_BONUS)


def period_start(period: Period, now: datetime | None = None) -> datetime | None:
    """Start of the current calendar week (Monday) or month in the club's time zone."""
    current = (now or datetime.now(local_tz())).astimezone(local_tz())
    midnight = datetime.combine(current.date(), time.min, tzinfo=local_tz())
    if period == "week":
        return midnight - timedelta(days=current.weekday())
    if period == "month":
        return midnight.replace(day=1)
    return None


def display_name(first_name: str, last_name: str, name_format: str) -> str:
    if name_format == "FULL":
        return f"{first_name} {last_name}"
    return f"{first_name} {last_name[:1]}." if last_name else first_name


async def _aggregate(session: AsyncSession, period: Period, between: tuple[datetime, datetime] | None = None) -> Select:
    conditions: list[Any] = []
    start = period_start(period)
    if between is not None:
        conditions.extend([EFFECTIVE_TIME >= between[0], EFFECTIVE_TIME < between[1]])
    elif start is not None:
        conditions.append(EFFECTIVE_TIME >= start)
    if period == "season":
        season_id = await current_season_id(session)
        conditions.append(func.coalesce(_original.season_id, ScoreTransaction.season_id) == season_id)
    return (
        select(
            ScoreTransaction.user_id.label("user_id"),
            func.sum(ScoreTransaction.amount).label("total"),
            func.coalesce(
                func.sum(ScoreTransaction.amount).filter(EFFECTIVE_CATEGORY == ScoreCategory.ATTENDANCE), 0
            ).label("attendance"),
            func.coalesce(func.sum(ScoreTransaction.amount).filter(EFFECTIVE_CATEGORY.in_(TEST_CATEGORIES)), 0).label(
                "tests"
            ),
            func.max(ScoreTransaction.created_at).label("last_at"),
        )
        .outerjoin(_original, _original.id == ScoreTransaction.reverses_transaction_id)
        .where(*conditions)
        .group_by(ScoreTransaction.user_id)
    )


@dataclass(frozen=True)
class RankingRow:
    rank: int
    user_id: uuid.UUID
    name: str
    faculty: str | None
    group_name: str | None
    total: int
    attendance: int
    tests: int
    premium: bool = False  # shown with a 💎 next to the name


@dataclass(frozen=True)
class Ranking:
    period: Period
    scope: Scope
    starts_at: datetime | None
    items: list[RankingRow]
    me: RankingRow | None


async def ranking(
    session: AsyncSession,
    *,
    period: Period,
    scope: Scope,
    viewer: User | None,
    limit: int = 50,
    between: tuple[datetime, datetime] | None = None,
) -> Ranking:
    """``between`` ranks an explicit time window instead of the current period (e.g. last month)."""
    aggregate = (await _aggregate(session, period, between)).subquery()
    conditions = [User.status == UserStatus.ACTIVE, User.deleted_at.is_(None), aggregate.c.total > 0]
    if scope == "faculty" and viewer is not None:
        conditions.append(User.faculty_id == viewer.faculty_id)
    if scope == "group" and viewer is not None:
        conditions.append(User.group_name == viewer.group_name)
        conditions.append(User.faculty_id == viewer.faculty_id)
    order = (
        aggregate.c.total.desc(),
        aggregate.c.attendance.desc(),
        aggregate.c.tests.desc(),
        aggregate.c.last_at.asc(),
        User.registered_at.asc().nulls_last(),
        User.id.asc(),
    )
    ranked = (
        select(
            func.row_number().over(order_by=order).label("rank"),
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.group_name,
            Faculty.name.label("faculty"),
            aggregate.c.total,
            aggregate.c.attendance,
            aggregate.c.tests,
        )
        .join(User, User.id == aggregate.c.user_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(*conditions)
    ).subquery()

    name_format = await get_setting(session, "ranking.public_name_format")

    rows = (await session.execute(select(ranked).where(ranked.c.rank <= limit).order_by(ranked.c.rank))).all()
    mine = (
        (await session.execute(select(ranked).where(ranked.c.user_id == viewer.id))).first()
        if viewer is not None
        else None
    )
    premium_ids = await _premium_among(session, [row.user_id for row in rows] + ([mine.user_id] if mine else []))

    def to_row(row: Any) -> RankingRow:
        return RankingRow(
            rank=int(row.rank),
            user_id=row.user_id,
            name=display_name(row.first_name, row.last_name, name_format),
            faculty=row.faculty,
            group_name=row.group_name,
            total=int(row.total),
            attendance=int(row.attendance),
            tests=int(row.tests),
            premium=row.user_id in premium_ids,
        )

    me = to_row(mine) if mine else None
    return Ranking(period=period, scope=scope, starts_at=period_start(period), items=[to_row(r) for r in rows], me=me)


async def _premium_among(session: AsyncSession, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not user_ids:
        return set()
    from app.models import PremiumSubscription

    now = datetime.now(UTC)
    return set(
        await session.scalars(
            select(PremiumSubscription.user_id).where(
                PremiumSubscription.user_id.in_(user_ids),
                PremiumSubscription.revoked_at.is_(None),
                PremiumSubscription.starts_at <= now,
                PremiumSubscription.ends_at > now,
            )
        )
    )


async def faculty_ranking(session: AsyncSession, *, period: Period) -> list[dict[str, Any]]:
    aggregate = (await _aggregate(session, period)).subquery()
    members = (
        select(User.faculty_id, func.count().label("members"))
        .where(User.status == UserStatus.ACTIVE, User.deleted_at.is_(None))
        .group_by(User.faculty_id)
        .subquery()
    )
    rows = await session.execute(
        select(
            Faculty.name,
            func.coalesce(members.c.members, 0).label("members"),
            func.coalesce(func.sum(aggregate.c.total), 0).label("total"),
        )
        .outerjoin(members, members.c.faculty_id == Faculty.id)
        .outerjoin(
            User,
            (User.faculty_id == Faculty.id) & (User.status == UserStatus.ACTIVE) & User.deleted_at.is_(None),
        )
        .outerjoin(aggregate, aggregate.c.user_id == User.id)
        .where(Faculty.is_active.is_(True))
        .group_by(Faculty.id, Faculty.name, members.c.members)
    )
    result = [
        {
            "faculty": name,
            "members": int(count),
            "total": int(total),
            "average": round(int(total) / int(count), 1) if count else 0.0,
        }
        for name, count, total in rows
    ]
    # Ranked by average points per member (fair between large and small faculties), then total.
    result.sort(key=lambda item: (-item["average"], -item["total"], item["faculty"]))
    for index, item in enumerate(result, start=1):
        item["rank"] = index
    return result


# ---------------------------------------------------------------------------- personal summary


async def score_summary(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    by_category = dict(
        (
            await session.execute(
                select(EFFECTIVE_CATEGORY, func.sum(ScoreTransaction.amount))
                .select_from(ScoreTransaction)
                .outerjoin(_original, _original.id == ScoreTransaction.reverses_transaction_id)
                .where(ScoreTransaction.user_id == user_id)
                .group_by(EFFECTIVE_CATEGORY)
            )
        ).all()
    )
    season_id = await current_season_id(session)
    season_total = None
    if season_id is not None:
        season_total = await session.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user_id, ScoreTransaction.season_id == season_id
            )
        )
    season_name = await session.scalar(select(Season.name).where(Season.id == season_id)) if season_id else None
    return {
        "total": int(sum(by_category.values())),
        "breakdown": {str(category): int(amount) for category, amount in by_category.items() if amount},
        "season": {"name": season_name, "total": int(season_total or 0)} if season_id else None,
    }


async def transaction_history(
    session: AsyncSession, *, user_id: uuid.UUID | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    conditions = [ScoreTransaction.user_id == user_id] if user_id else []
    total = await session.scalar(select(func.count()).select_from(ScoreTransaction).where(*conditions))
    rows = list(
        (
            await session.execute(
                select(ScoreTransaction, EFFECTIVE_CATEGORY.label("effective"), User.first_name, User.last_name)
                .outerjoin(_original, _original.id == ScoreTransaction.reverses_transaction_id)
                .join(User, User.id == ScoreTransaction.user_id)
                .where(*conditions)
                .order_by(ScoreTransaction.created_at.desc(), ScoreTransaction.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    titles = await _source_titles(session, [row[0] for row in rows])
    reversed_ids = set(
        await session.scalars(
            select(ScoreTransaction.reverses_transaction_id).where(
                ScoreTransaction.reverses_transaction_id.in_([row[0].id for row in rows])
            )
        )
    )
    items = [
        {
            "id": tx.id,
            "user_id": tx.user_id,
            "user_name": f"{first} {last}",
            "amount": tx.amount,
            "category": tx.category,
            "effective_category": effective,
            "source_type": tx.source_type,
            "source_title": titles.get((tx.source_type, tx.source_id)),
            "reason": tx.reason,
            "is_reversed": tx.id in reversed_ids,
            "created_at": tx.created_at,
        }
        for tx, effective, first, last in rows
    ]
    return items, int(total or 0)


async def _source_titles(session: AsyncSession, transactions: list[ScoreTransaction]) -> dict[tuple[str, Any], str]:
    wanted: dict[str, set[uuid.UUID]] = {}
    for tx in transactions:
        if tx.source_type and tx.source_id:
            wanted.setdefault(tx.source_type, set()).add(tx.source_id)
    titles: dict[tuple[str, Any], str] = {}
    for source_type, model in (("EVENT", Event), ("BOOK", Book), ("TEST", Test)):
        ids = wanted.get(source_type)
        if ids:
            for source_id, title in (
                await session.execute(select(model.id, model.title).where(model.id.in_(ids)))
            ).all():
                titles[(source_type, source_id)] = title
    return titles
