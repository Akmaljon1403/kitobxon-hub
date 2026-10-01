"""Score ledger writes.

Only this module creates score transactions. Callers pass a deterministic idempotency key
(e.g. ``book:<book id>:user:<user id>``) so the same business fact can never award points
twice, even when a request is retried. The caller commits, so points and the business
change that caused them are saved in one transaction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScoreTransaction, Season
from app.models.enums import ScoreCategory


async def current_season_id(session: AsyncSession) -> uuid.UUID | None:
    return await session.scalar(select(Season.id).where(Season.is_current.is_(True)))


async def award_points(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount: int,
    category: ScoreCategory,
    idempotency_key: str,
    source_type: str | None = None,
    source_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    reason: str | None = None,
) -> uuid.UUID | None:
    """Insert a ledger row. Returns its id, or None if nothing was awarded (zero or duplicate)."""
    if amount == 0:
        return None
    statement = (
        insert(ScoreTransaction)
        .values(
            user_id=user_id,
            season_id=await current_season_id(session),
            amount=amount,
            category=category,
            source_type=source_type,
            source_id=source_id,
            reason=reason,
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        .on_conflict_do_nothing(index_elements=[ScoreTransaction.idempotency_key])
        .returning(ScoreTransaction.id)
    )
    return await session.scalar(statement)
