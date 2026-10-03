"""Feature switches, premium membership (paid with Telegram Stars or granted) and payments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import FeatureMode, PaymentKind, PaymentStatus, PremiumSource


class FeatureFlag(Base):
    """Who may use a bot feature: nobody, every member, or premium members only.

    The catalogue of features lives in code (``app.services.features``); this table stores the
    super admin's choice. A missing row means the feature's default mode.
    """

    __tablename__ = "feature_flags"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[FeatureMode] = mapped_column(enum_column(FeatureMode))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PremiumPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "premium_plans"
    __table_args__ = (
        CheckConstraint("stars > 0", name="stars_positive"),
        CheckConstraint("days > 0", name="days_positive"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    stars: Mapped[int] = mapped_column(Integer)  # price in Telegram Stars (XTR)
    days: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))


class Payment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A Telegram Stars payment (premium or a donation to the club)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_payments_user_id", "user_id"),
        Index("ix_payments_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[PaymentKind] = mapped_column(enum_column(PaymentKind))
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus), default=PaymentStatus.PAID, server_default=PaymentStatus.PAID.value
    )
    currency: Mapped[str] = mapped_column(String(8), default="XTR", server_default="XTR")
    amount: Mapped[int] = mapped_column(Integer)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("premium_plans.id", ondelete="SET NULL"))
    invoice_payload: Mapped[str] = mapped_column(String(128))
    # Telegram's id of the charge: unique, needed for refunds; makes duplicate updates harmless.
    telegram_charge_id: Mapped[str] = mapped_column(String(255), unique=True)
    refunded_at: Mapped[datetime | None] = mapped_column()
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PremiumSubscription(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One period of premium membership. Periods of a member follow each other (no overlap)."""

    __tablename__ = "premium_subscriptions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="period_order"),
        Index("ix_premium_subscriptions_user_id_ends_at", "user_id", "ends_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[PremiumSource] = mapped_column(enum_column(PremiumSource))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("premium_plans.id", ondelete="SET NULL"))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column()
