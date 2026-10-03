"""Premium membership and donations for members (paid with Telegram Stars)."""

from __future__ import annotations

import uuid
from typing import Annotated

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, File, Form, UploadFile

from app.api.deps import CurrentUserDep, DbSession
from app.core.errors import BadRequestError, ServiceUnavailableError
from app.models import CardPayment, PremiumPlan
from app.schemas.premium import CardPaymentOut, InvoiceIn, InvoiceOut, PremiumStatusOut
from app.services import card_payments, delivery
from app.services import premium as premium_service

router = APIRouter(prefix="/me/premium", tags=["premium"])


@router.get("", response_model=PremiumStatusOut, summary="My premium status, plans and what Premium gives")
async def status(current: CurrentUserDep, db: DbSession) -> PremiumStatusOut:
    return PremiumStatusOut(**await premium_service.member_status(db, current.user))


@router.post("/invoice", response_model=InvoiceOut, summary="Invoice link for Telegram.WebApp.openInvoice")
async def invoice(payload: InvoiceIn, current: CurrentUserDep, db: DbSession) -> InvoiceOut:
    bot = delivery.runtime_bot()
    try:
        url = await premium_service.invoice_link(db, bot, current.user, plan_id=payload.plan_id, amount=payload.amount)
    except TelegramAPIError as exc:
        raise ServiceUnavailableError(
            "BOT_UNAVAILABLE", "To'lov oynasini ochib bo'lmadi. Birozdan keyin urinib ko'ring."
        ) from exc
    return InvoiceOut(url=url)


def card_payment_out(payment: CardPayment, plan_title: str | None) -> CardPaymentOut:
    return CardPaymentOut(
        id=payment.id,
        kind=payment.kind,
        status=payment.status,
        amount_uzs=payment.amount_uzs,
        plan_title=plan_title,
        created_at=payment.created_at,
        decided_at=payment.decided_at,
        reject_reason=payment.reject_reason,
    )


@router.post(
    "/card-payments",
    response_model=CardPaymentOut,
    status_code=201,
    summary="I paid to the club's card: send the receipt (multipart)",
)
async def submit_card_payment(
    current: CurrentUserDep,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    plan_id: Annotated[uuid.UUID | None, Form()] = None,
    amount_uzs: Annotated[int | None, Form(ge=1, le=100_000_000)] = None,
) -> CardPaymentOut:
    if (plan_id is None) == (amount_uzs is None):
        raise BadRequestError("CHOOSE_ONE", "Tarifni yoki hissa miqdorini tanlang.")
    data = await file.read(card_payments.MAX_RECEIPT_BYTES + 1)
    payment = await card_payments.submit(db, current.user, receipt=data, plan_id=plan_id, amount_uzs=amount_uzs)
    plan = await db.get(PremiumPlan, payment.plan_id) if payment.plan_id else None
    return card_payment_out(payment, plan.title if plan else None)


@router.get("/card-payments", response_model=list[CardPaymentOut], summary="My card payments and their status")
async def my_card_payments(current: CurrentUserDep, db: DbSession) -> list[CardPaymentOut]:
    return [card_payment_out(p, title) for p, title in await card_payments.member_payments(db, current.user.id)]
