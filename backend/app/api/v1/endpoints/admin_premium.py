"""Super admin: feature switches (off / everyone / premium only), premium plans, payments, grants."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from app.api.deps import DbSession, SuperAdminDep
from app.api.v1.endpoints.premium import card_payment_out
from app.core.errors import ServiceUnavailableError
from app.models import PremiumPlan, User
from app.models.enums import CardPaymentStatus
from app.schemas.common import Page, ReasonIn
from app.schemas.premium import (
    AdminCardPaymentOut,
    AdminPlanOut,
    FeatureModeIn,
    FeatureModeOut,
    FeatureOut,
    GrantIn,
    MemberBrief,
    PaymentOut,
    PlanUpdateIn,
    PremiumOverviewOut,
    SubscriptionOut,
)
from app.services import card_payments, delivery, features
from app.services import premium as premium_service
from app.services.passport import member_number

router = APIRouter(prefix="/admin", tags=["admin: features and premium"])


def _member(user: User) -> MemberBrief:
    return MemberBrief(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        member_number=member_number(user),
        telegram_username=user.telegram_username,
    )


def _plan(plan: PremiumPlan) -> AdminPlanOut:
    return AdminPlanOut(
        id=plan.id,
        code=plan.code,
        title=plan.title,
        description=plan.description,
        stars=plan.stars,
        days=plan.days,
        price_uzs=plan.price_uzs,
        is_active=plan.is_active,
        sort_order=plan.sort_order,
    )


@router.get("/features", response_model=list[FeatureOut], summary="Bot features and who may use them")
async def list_features(_: SuperAdminDep, db: DbSession) -> list[FeatureOut]:
    current = await features.modes(db)
    return [
        FeatureOut(
            code=feature.code,
            title=feature.title,
            description=feature.description,
            mode=current[feature.code],
            default=feature.default,
            premium_allowed=feature.premium_allowed,
        )
        for feature in features.FEATURES
    ]


@router.put("/features/{code}", response_model=FeatureModeOut, summary="Switch a feature (and announce it)")
async def set_feature(code: str, payload: FeatureModeIn, current: SuperAdminDep, db: DbSession) -> FeatureModeOut:
    told = await features.set_mode(
        db, actor_id=current.user.id, code=code, new_mode=payload.mode, announce=payload.announce
    )
    return FeatureModeOut(code=code, mode=payload.mode, announced_to=told)


@router.get("/premium/overview", response_model=PremiumOverviewOut, summary="Premium members and Stars received")
async def overview(_: SuperAdminDep, db: DbSession) -> PremiumOverviewOut:
    return PremiumOverviewOut(**await premium_service.overview(db))


@router.get("/premium/plans", response_model=list[AdminPlanOut], summary="All plans (also those not on sale)")
async def plans(_: SuperAdminDep, db: DbSession) -> list[AdminPlanOut]:
    return [_plan(plan) for plan in await premium_service.list_plans(db, active_only=False)]


@router.patch("/premium/plans/{plan_id}", response_model=AdminPlanOut, summary="Change a plan's price or length")
async def update_plan(plan_id: uuid.UUID, payload: PlanUpdateIn, current: SuperAdminDep, db: DbSession) -> AdminPlanOut:
    plan = await premium_service.update_plan(
        db, actor_id=current.user.id, plan_id=plan_id, changes=payload.model_dump(exclude_unset=True)
    )
    return _plan(plan)


@router.get("/premium/payments", response_model=Page[PaymentOut], summary="Stars payments, newest first")
async def payments(
    _: SuperAdminDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[PaymentOut]:
    rows, total = await premium_service.list_payments(db, limit=limit, offset=offset)
    plan_titles = {plan.id: plan.title for plan in await premium_service.list_plans(db, active_only=False)}
    return Page(
        items=[
            PaymentOut(
                id=payment.id,
                kind=payment.kind,
                status=payment.status,
                amount=payment.amount,
                plan_title=plan_titles.get(payment.plan_id) if payment.plan_id else None,
                created_at=payment.created_at,
                refunded_at=payment.refunded_at,
                member=_member(user),
            )
            for payment, user in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/premium/payments/{payment_id}/refund", response_model=dict[str, str], summary="Give the Stars back")
async def refund(payment_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> dict[str, str]:
    try:
        payment = await premium_service.refund(
            db, delivery.runtime_bot(), actor_id=current.user.id, payment_id=payment_id
        )
    except TelegramAPIError as exc:
        raise ServiceUnavailableError("REFUND_FAILED", f"Telegram qaytarishni rad etdi: {exc.message}") from exc
    return {"status": str(payment.status)}


@router.get("/premium/subscriptions", response_model=Page[SubscriptionOut], summary="Premium periods")
async def subscriptions(
    _: SuperAdminDep,
    db: DbSession,
    active: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SubscriptionOut]:
    rows, total = await premium_service.list_subscriptions(db, active_only=active, limit=limit, offset=offset)
    return Page(
        items=[
            SubscriptionOut(
                id=subscription.id,
                source=subscription.source,
                starts_at=subscription.starts_at,
                ends_at=subscription.ends_at,
                note=subscription.note,
                revoked_at=subscription.revoked_at,
                member=_member(user),
            )
            for subscription, user in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/premium/grant", response_model=SubscriptionOut, status_code=201, summary="Give Premium (N days or for life)"
)
async def grant(payload: GrantIn, current: SuperAdminDep, db: DbSession) -> SubscriptionOut:
    subscription = await premium_service.grant(
        db,
        actor_id=current.user.id,
        user_id=payload.user_id,
        days=payload.days,
        note=payload.note,
        lifetime=payload.lifetime,
    )
    user = await db.get(User, subscription.user_id)
    assert user is not None
    return SubscriptionOut(
        id=subscription.id,
        source=subscription.source,
        starts_at=subscription.starts_at,
        ends_at=subscription.ends_at,
        note=subscription.note,
        revoked_at=subscription.revoked_at,
        member=_member(user),
    )


class BulkGrantIn(BaseModel):
    days: int = Field(ge=1, le=premium_service.MAX_BULK_DAYS)
    note: str | None = Field(
        default=None, max_length=200, description="Shown to members: «Bilimlar kuni munosabati bilan»"
    )
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=10)
    group_name: str | None = Field(default=None, max_length=16)
    only_without_premium: bool = False
    dry_run: bool = False


@router.post("/premium/grant-bulk", summary="Give Premium for N days to everybody, a faculty, a course or a group")
async def grant_bulk(payload: BulkGrantIn, current: SuperAdminDep, db: DbSession) -> dict[str, Any]:
    return await premium_service.grant_many(db, actor_id=current.user.id, **payload.model_dump())


@router.post("/premium/subscriptions/{subscription_id}/revoke", response_model=dict[str, str], summary="End a period")
async def revoke(
    subscription_id: uuid.UUID, payload: ReasonIn, current: SuperAdminDep, db: DbSession
) -> dict[str, str]:
    await premium_service.revoke_subscription(
        db, actor_id=current.user.id, subscription_id=subscription_id, reason=payload.reason
    )
    return {"status": "REVOKED"}


@router.get("/premium/card-payments", response_model=Page[AdminCardPaymentOut], summary="Card payments (receipts)")
async def card_payment_list(
    _: SuperAdminDep,
    db: DbSession,
    status: CardPaymentStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AdminCardPaymentOut]:
    rows, total = await card_payments.list_payments(db, status=status, limit=limit, offset=offset)
    repeated = await card_payments.repeated_receipts(db, [payment for payment, _, _ in rows])
    return Page(
        items=[
            AdminCardPaymentOut(
                **card_payment_out(payment, title).model_dump(), member=_member(user), duplicate=payment.id in repeated
            )
            for payment, user, title in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/premium/card-payments/{payment_id}/receipt", summary="The receipt image", response_class=Response)
async def card_payment_receipt(payment_id: uuid.UUID, _: SuperAdminDep, db: DbSession) -> Response:
    payment = await card_payments.get(db, payment_id)
    return Response(content=await card_payments.receipt(db, payment), media_type="image/jpeg")


@router.post("/premium/card-payments/{payment_id}/approve", response_model=dict[str, str], summary="Confirm")
async def card_payment_approve(payment_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> dict[str, str]:
    payment = await card_payments.approve(db, actor_id=current.user.id, payment_id=payment_id)
    return {"status": str(payment.status)}


@router.post(
    "/premium/card-payments/{payment_id}/delivered",
    response_model=dict[str, str],
    summary="Stars purchase: I gifted the Stars in Telegram (the member is told)",
)
async def card_payment_delivered(payment_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> dict[str, str]:
    payment = await card_payments.mark_delivered(db, actor_id=current.user.id, payment_id=payment_id)
    return {"status": "DELIVERED" if payment.delivered_at else str(payment.status)}


@router.post(
    "/premium/card-payments/{payment_id}/undo",
    response_model=dict[str, str],
    summary="Undo a decision taken by mistake (within 48 hours): back to «waiting»",
)
async def card_payment_undo(payment_id: uuid.UUID, current: SuperAdminDep, db: DbSession) -> dict[str, str]:
    payment = await card_payments.undo(db, actor_id=current.user.id, payment_id=payment_id)
    return {"status": str(payment.status)}


@router.post("/premium/card-payments/{payment_id}/reject", response_model=dict[str, str], summary="Reject")
async def card_payment_reject(
    payment_id: uuid.UUID, payload: ReasonIn, current: SuperAdminDep, db: DbSession
) -> dict[str, str]:
    payment = await card_payments.reject(db, actor_id=current.user.id, payment_id=payment_id, reason=payload.reason)
    return {"status": str(payment.status)}


@router.get("/premium/payments-chat", summary="The payments channel: which one, and can the bot write there")
async def payments_chat_status(_: SuperAdminDep, db: DbSession) -> dict[str, object]:
    from app.services import payments_chat

    return await payments_chat.describe(db)


@router.post("/premium/payments-chat/test", summary="A test message in the payments channel")
async def payments_chat_test(_: SuperAdminDep, db: DbSession) -> dict[str, object]:
    from app.services import payments_chat

    sent = await payments_chat.send_test(db)
    return {"sent": sent, **(await payments_chat.describe(db))}


@router.get("/premium/money-summary", summary="Money of the last N days (card payments and Telegram Stars)")
async def money_summary(
    _: SuperAdminDep, db: DbSession, days: Annotated[int, Query(ge=1, le=366)] = 7
) -> dict[str, str]:
    from datetime import UTC, datetime, timedelta

    from app.services import payments_chat

    until = datetime.now(UTC)
    return {"text": await payments_chat.summary_text(db, until - timedelta(days=days), until)}
