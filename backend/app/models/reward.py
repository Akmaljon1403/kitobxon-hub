"""Rewards (books, certificates, partner codes) and their distribution.

Promo codes are provided by administrators. They are stored encrypted (``code_encrypted``)
and are only shown to the member they were assigned to. ``code_hash`` prevents loading the
same code twice without decrypting anything.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import RewardCodeStatus, RewardStatus, RewardType, UserRewardStatus


class Reward(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "rewards"

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[RewardType] = mapped_column(enum_column(RewardType))
    value: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime | None] = mapped_column()
    status: Mapped[RewardStatus] = mapped_column(
        enum_column(RewardStatus), default=RewardStatus.ACTIVE, server_default=RewardStatus.ACTIVE.value
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class RewardCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reward_codes"
    __table_args__ = (
        UniqueConstraint("reward_id", "code_hash"),
        Index("ix_reward_codes_reward_id_status", "reward_id", "status"),
    )

    reward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rewards.id", ondelete="RESTRICT"))
    code_encrypted: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[RewardCodeStatus] = mapped_column(
        enum_column(RewardCodeStatus), default=RewardCodeStatus.AVAILABLE, server_default="AVAILABLE"
    )
    expires_at: Mapped[datetime | None] = mapped_column()
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class UserReward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_rewards"
    __table_args__ = (
        Index("ix_user_rewards_user_id", "user_id"),
        Index("ix_user_rewards_reward_id", "reward_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rewards.id", ondelete="RESTRICT"))
    # A code can be handed out only once.
    reward_code_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reward_codes.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[UserRewardStatus] = mapped_column(
        enum_column(UserRewardStatus), default=UserRewardStatus.ASSIGNED, server_default="ASSIGNED"
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column()
    redeemed_at: Mapped[datetime | None] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text)
    # Repeating the same assignment request never creates a second reward.
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
