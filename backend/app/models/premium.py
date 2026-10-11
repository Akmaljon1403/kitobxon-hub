"""Feature switches, premium membership (paid with Telegram Stars or granted) and payments."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin, enum_column
from app.models.enums import CardPaymentStatus, FeatureMode, PaymentKind, PaymentStatus, PremiumSource


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
        CheckConstraint("price_uzs IS NULL OR price_uzs > 0", name="price_uzs_positive"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    stars: Mapped[int] = mapped_column(Integer)  # price in Telegram Stars (XTR)
    price_uzs: Mapped[int | None] = mapped_column(Integer)  # price for card payments; None = not sold by card
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


class CardPayment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A payment to the club's bank card: the member sends the receipt, the super admin confirms it."""

    __tablename__ = "card_payments"
    __table_args__ = (
        CheckConstraint("amount_uzs > 0", name="amount_positive"),
        Index("ix_card_payments_status_created_at", "status", "created_at"),
        Index("ix_card_payments_user_id", "user_id"),
        Index("ix_card_payments_receipt_sha256", "receipt_sha256"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[PaymentKind] = mapped_column(enum_column(PaymentKind))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("premium_plans.id", ondelete="SET NULL"))
    amount_uzs: Mapped[int] = mapped_column(Integer)
    receipt_key: Mapped[str] = mapped_column(String(512))
    # The uploaded file's SHA-256: the very same receipt sent again (by anyone) is flagged to the admins.
    receipt_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[CardPaymentStatus] = mapped_column(
        enum_column(CardPaymentStatus),
        default=CardPaymentStatus.PENDING,
        server_default=CardPaymentStatus.PENDING.value,
    )
    decided_at: Mapped[datetime | None] = mapped_column()
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    # STARS: how many Stars the member asked for, and when the admin gifted them in Telegram.
    stars: Mapped[int | None] = mapped_column(Integer)
    delivered_at: Mapped[datetime | None] = mapped_column()
    delivered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    discount_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("premium_discounts.id", ondelete="SET NULL"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("premium_subscriptions.id", ondelete="SET NULL")
    )


class PremiumDiscount(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A personal discount on Premium (e.g. won by the first members who joined). Used once."""

    __tablename__ = "premium_discounts"
    __table_args__ = (
        CheckConstraint("percent BETWEEN 1 AND 100", name="percent_range"),
        Index("ix_premium_discounts_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    percent: Mapped[int] = mapped_column(SmallInteger)
    valid_until: Mapped[datetime] = mapped_column()
    note: Mapped[str | None] = mapped_column(String(255))
    giveaway_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("giveaways.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column()
    used_for: Mapped[str | None] = mapped_column(String(64))  # "payment:<id>" or "card:<id>"
