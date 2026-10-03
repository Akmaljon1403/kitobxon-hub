"""Premium membership and donations for members (paid with Telegram Stars)."""

from __future__ import annotations

from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession
from app.core.errors import ServiceUnavailableError
from app.schemas.premium import InvoiceIn, InvoiceOut, PremiumStatusOut
from app.services import delivery
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
