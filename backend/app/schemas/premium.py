from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CardPaymentStatus, FeatureMode, PaymentKind, PaymentStatus, PremiumSource


class PlanOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    stars: int
    days: int
    price_uzs: int | None = None
    # The prices for this member right now (after a personal discount, if any).
    stars_now: int | None = None
    price_uzs_now: int | None = None


class DiscountOut(BaseModel):
    percent: int
    valid_until: datetime
    note: str | None


class StarsPackageOut(BaseModel):
    stars: int
    price_uzs: int


class CardDetailsOut(BaseModel):
    number: str
    holder: str


class PremiumFeatureOut(BaseModel):
    code: str
    title: str
    description: str


class PerkOut(BaseModel):
    icon: str
    title: str
    description: str


class PremiumStatusOut(BaseModel):
    is_premium: bool
    lifetime: bool = False  # super administrators and gifts "for life"
    until: datetime | None
    store_open: bool
    donations_open: bool
    plans: list[PlanOut]
    donation_amounts: list[int]
    premium_features: list[PremiumFeatureOut]
    perks: list[PerkOut]
    card: CardDetailsOut | None = None
    trial_days: int = 0  # the free trial the member can still start
    discount: DiscountOut | None = None
    stars_packages: list[StarsPackageOut] = []


class InvoiceIn(BaseModel):
    plan_id: uuid.UUID | None = None
    amount: int | None = Field(default=None, ge=1, le=10_000, description="Donation in Stars")

    @model_validator(mode="after")
    def _one_of(self) -> InvoiceIn:
        if (self.plan_id is None) == (self.amount is None):
            raise ValueError("Give either plan_id or amount")
        return self


class InvoiceOut(BaseModel):
    url: str


# ---- admin ----


class FeatureOut(BaseModel):
    code: str
    title: str
    description: str
    mode: FeatureMode
    default: FeatureMode
    premium_allowed: bool


class FeatureModeIn(BaseModel):
    mode: FeatureMode
    announce: bool = Field(default=True, description="Tell members when a feature is switched on")


class FeatureModeOut(BaseModel):
    code: str
    mode: FeatureMode
    announced_to: int


class AdminPlanOut(PlanOut):
    code: str
    is_active: bool
    sort_order: int


class PlanUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    stars: int | None = Field(default=None, ge=1, le=100_000)
    price_uzs: int | None = Field(default=None, ge=1, le=100_000_000, description="Card price; null: not sold by card")
    days: int | None = Field(default=None, ge=1, le=3660)
    is_active: bool | None = None


class PremiumOverviewOut(BaseModel):
    premium_members: int
    stars_total: int
    stars_this_month: int
    premium_stars: int
    donation_stars: int
    payments: int
    uzs_total: int = 0
    uzs_this_month: int = 0
    card_pending: int = 0


class MemberBrief(BaseModel):
    user_id: uuid.UUID
    first_name: str
    last_name: str
    member_number: str
    telegram_username: str | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    kind: PaymentKind
    status: PaymentStatus
    amount: int
    plan_title: str | None
    created_at: datetime
    refunded_at: datetime | None
    member: MemberBrief


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    source: PremiumSource
    starts_at: datetime
    ends_at: datetime
    note: str | None
    revoked_at: datetime | None
    member: MemberBrief


class GrantIn(BaseModel):
    user_id: uuid.UUID
    days: int | None = Field(default=None, ge=1, le=3660)
    lifetime: bool = False
    note: str | None = Field(default=None, max_length=500)


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    rating: int
    comment: str | None
    updated_at: datetime


class FeedbackSummaryOut(BaseModel):
    count: int
    average: float | None
    distribution: dict[str, int]
    comments: list[dict[str, object]]


class CardPaymentOut(BaseModel):
    id: uuid.UUID
    kind: PaymentKind
    status: CardPaymentStatus
    amount_uzs: int
    plan_title: str | None
    created_at: datetime
    decided_at: datetime | None
    reject_reason: str | None
    stars: int | None = None
    delivered_at: datetime | None = None


class AdminCardPaymentOut(CardPaymentOut):
    member: MemberBrief
    duplicate: bool = False  # the very same receipt file was also sent with another payment
