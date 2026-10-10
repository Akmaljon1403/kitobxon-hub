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


def _rankings_changed() -> None:
    from app.services import ranking

    ranking.forget()  # the member sees their new place at once


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
    _rankings_changed()
    return await session.scalar(statement)


async def reverse_latest_award(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: ScoreCategory,
    source_type: str,
    source_id: uuid.UUID,
    created_by: uuid.UUID | None,
    reason: str,
) -> uuid.UUID | None:
    """Cancel the most recent not-yet-reversed award for a business fact with a REVERSAL row.

    Returns the id of the reversal transaction, or None when there was nothing to reverse.
    """
    from sqlalchemy.orm import aliased

    reversal = aliased(ScoreTransaction)
    original = await session.scalar(
        select(ScoreTransaction)
        .outerjoin(reversal, reversal.reverses_transaction_id == ScoreTransaction.id)
        .where(
            ScoreTransaction.user_id == user_id,
            ScoreTransaction.category == category,
            ScoreTransaction.source_type == source_type,
            ScoreTransaction.source_id == source_id,
            reversal.id.is_(None),
        )
        .order_by(ScoreTransaction.created_at.desc())
        .limit(1)
    )
    if original is None:
        return None
    _rankings_changed()
    return await session.scalar(
        insert(ScoreTransaction)
        .values(
            user_id=user_id,
            season_id=original.season_id,
            amount=-original.amount,
            category=ScoreCategory.REVERSAL,
            source_type=source_type,
            source_id=source_id,
            reason=reason,
            idempotency_key=f"reversal:{original.id}",
            reverses_transaction_id=original.id,
            created_by=created_by,
        )
        .on_conflict_do_nothing(index_elements=[ScoreTransaction.idempotency_key])
        .returning(ScoreTransaction.id)
    )


async def user_total(session: AsyncSession, user_id: uuid.UUID) -> int:
    from sqlalchemy import func

    return int(
        await session.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(ScoreTransaction.user_id == user_id)
        )
    )


async def manual_adjustment(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, amount: int, reason: str
) -> uuid.UUID:
    """Admin correction (requires SCORE_MANAGE at the API). Audited with the total before and after."""
    from app.core.errors import BadRequestError, NotFoundError
    from app.models import User
    from app.services.audit import record_audit

    member = await session.get(User, user_id)
    if member is None or member.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    if amount == 0:
        raise BadRequestError("INVALID_AMOUNT", "Ball 0 bo'lishi mumkin emas.")
    before = await user_total(session, user_id)
    transaction_id = await award_points(
        session,
        user_id=user_id,
        amount=amount,
        category=ScoreCategory.MANUAL,
        idempotency_key=f"manual:{uuid.uuid4()}",
        source_type="MANUAL",
        created_by=actor_id,
        reason=reason,
    )
    assert transaction_id is not None
    record_audit(
        session,
        actor_id=actor_id,
        action="SCORE_ADJUST",
        entity_type="user",
        entity_id=user_id,
        before={"total": before},
        after={"total": before + amount, "amount": amount},
        reason=reason,
    )
    await session.commit()
    return transaction_id


async def reverse_transaction(
    session: AsyncSession, *, actor_id: uuid.UUID, transaction_id: uuid.UUID, reason: str
) -> uuid.UUID:
    """Cancel one ledger row with an opposite REVERSAL row (the original stays for history)."""
    from app.core.errors import BadRequestError, ConflictError, NotFoundError
    from app.services.audit import record_audit

    original = await session.get(ScoreTransaction, transaction_id)
    if original is None:
        raise NotFoundError("TRANSACTION_NOT_FOUND", "Ball yozuvi topilmadi.")
    if original.category == ScoreCategory.REVERSAL:
        raise BadRequestError("CANNOT_REVERSE_REVERSAL", "Bekor qilish yozuvini qayta bekor qilib bo'lmaydi.")
    before = await user_total(session, original.user_id)
    _rankings_changed()
    reversal_id = await session.scalar(
        insert(ScoreTransaction)
        .values(
            user_id=original.user_id,
            season_id=original.season_id,
            amount=-original.amount,
            category=ScoreCategory.REVERSAL,
            source_type=original.source_type,
            source_id=original.source_id,
            reason=reason,
            idempotency_key=f"reversal:{original.id}",
            reverses_transaction_id=original.id,
            created_by=actor_id,
        )
        .on_conflict_do_nothing()
        .returning(ScoreTransaction.id)
    )
    if reversal_id is None:
        await session.rollback()
        raise ConflictError("ALREADY_REVERSED", "Bu ball allaqachon bekor qilingan.")
    record_audit(
        session,
        actor_id=actor_id,
        action="SCORE_REVERSE",
        entity_type="score_transaction",
        entity_id=original.id,
        before={"total": before},
        after={"total": before - original.amount, "reversed_amount": original.amount},
        reason=reason,
    )
    await session.commit()
    return reversal_id
