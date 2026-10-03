"""Super admin: feature switches (off / everyone / premium only), premium plans, payments, grants."""

from __future__ import annotations

import uuid
from typing import Annotated

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Query

from app.api.deps import DbSession, SuperAdminDep
from app.core.errors import ServiceUnavailableError
from app.models import PremiumPlan, User
from app.schemas.common import Page, ReasonIn
from app.schemas.premium import (
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
from app.services import delivery, features
from app.services import premium as premium_service
from app.services.passport import member_number

router = APIRouter(prefix="/admin", tags=["admin: features and premium"])


def _member(user: User) -> MemberBrief:
    return MemberBrief(
        user_id=user.id, first_name=user.first_name, last_name=user.last_name, member_number=member_number(user)
    )


def _plan(plan: PremiumPlan) -> AdminPlanOut:
    return AdminPlanOut(
        id=plan.id,
        code=plan.code,
        title=plan.title,
        description=plan.description,
        stars=plan.stars,
        days=plan.days,
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


@router.post("/premium/grant", response_model=SubscriptionOut, status_code=201, summary="Give Premium for N days")
async def grant(payload: GrantIn, current: SuperAdminDep, db: DbSession) -> SubscriptionOut:
    subscription = await premium_service.grant(
        db, actor_id=current.user.id, user_id=payload.user_id, days=payload.days, note=payload.note
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


@router.post("/premium/subscriptions/{subscription_id}/revoke", response_model=dict[str, str], summary="End a period")
async def revoke(
    subscription_id: uuid.UUID, payload: ReasonIn, current: SuperAdminDep, db: DbSession
) -> dict[str, str]:
    await premium_service.revoke_subscription(
        db, actor_id=current.user.id, subscription_id=subscription_id, reason=payload.reason
    )
    return {"status": "REVOKED"}
