"""Score ledger.

Every change of a member's points is one immutable row. Totals and rankings are sums
over this table; there is no editable "total score" column. A database trigger rejects
UPDATE and DELETE (see the initial migration), and corrections are new rows that
reference the original transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import ScoreCategory


class ScoreTransaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "score_transactions"
    __table_args__ = (
        CheckConstraint("amount <> 0", name="amount_non_zero"),
        CheckConstraint(
            "category NOT IN ('MANUAL', 'REVERSAL') OR (reason IS NOT NULL AND length(trim(reason)) >= 5)",
            name="manual_requires_reason",
        ),
        Index("ix_score_transactions_user_id_created_at", "user_id", "created_at"),
        Index("ix_score_transactions_season_id_user_id", "season_id", "user_id"),
        Index("ix_score_transactions_created_at", "created_at"),
        Index("ix_score_transactions_source", "source_type", "source_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    season_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seasons.id", ondelete="RESTRICT"))
    amount: Mapped[int] = mapped_column(Integer)
    category: Mapped[ScoreCategory] = mapped_column(enum_column(ScoreCategory))
    # What caused the transaction, e.g. ("EVENT", <event id>) or ("TEST", <test id>).
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_id: Mapped[uuid.UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    # Guarantees one transaction per business fact, e.g. "attendance:<record id>".
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    # A transaction can be reversed at most once.
    reverses_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("score_transactions.id", ondelete="RESTRICT"), unique=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
