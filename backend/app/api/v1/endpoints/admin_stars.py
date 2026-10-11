"""Admin Panel: «⭐ Stars buyurtmalari» — Telegram Stars that members bought with a bank card.

The super admin confirms the receipt; the order then waits here (and in the private chat of the admins
given «⭐ Stars yuborish») until someone gifts the Stars in Telegram and presses «✅ Yuborildi».
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import CardPayment, User
from app.models.enums import CardPaymentStatus, PaymentKind
from app.security.permissions import Perm
from app.services import card_payments

router = APIRouter(prefix="/admin/stars-orders", tags=["admin: stars orders"])
Sender = Annotated[CurrentUser, Depends(require_permissions(Perm.STARS_SEND))]


class StarsOrderOut(BaseModel):
    id: uuid.UUID
    stars: int
    amount_uzs: int
    member_name: str
    member_username: str | None
    member_telegram_id: int
    approved_at: datetime | None
    approved_by: str | None
    delivered_at: datetime | None
    delivered_by: str | None


class StarsOrdersOut(BaseModel):
    items: list[StarsOrderOut]
    waiting: int
    senders: str  # who receives new orders in the bot


def _full(user: User | None) -> str | None:
    return f"{user.first_name} {user.last_name}".strip() if user else None


@router.get("", response_model=StarsOrdersOut, summary="Confirmed Stars orders: waiting to be gifted, or sent")
async def list_orders(
    _: Sender, db: DbSession, state: Annotated[Literal["waiting", "sent"], Query()] = "waiting"
) -> StarsOrdersOut:
    member, boss, sender = aliased(User), aliased(User), aliased(User)
    base = (
        select(CardPayment, member, boss, sender)
        .join(member, member.id == CardPayment.user_id)
        .outerjoin(boss, boss.id == CardPayment.decided_by)
        .outerjoin(sender, sender.id == CardPayment.delivered_by)
        .where(CardPayment.kind == PaymentKind.STARS, CardPayment.status == CardPaymentStatus.APPROVED)
    )
    waiting_query = base.where(CardPayment.delivered_at.is_(None))
    query = (
        waiting_query.order_by(CardPayment.decided_at)
        if state == "waiting"
        else base.where(CardPayment.delivered_at.is_not(None)).order_by(CardPayment.delivered_at.desc()).limit(100)
    )
    rows = (await db.execute(query)).all()
    waiting = len((await db.execute(waiting_query)).all()) if state != "waiting" else len(rows)
    return StarsOrdersOut(
        items=[
            StarsOrderOut(
                id=payment.id,
                stars=payment.stars or 0,
                amount_uzs=payment.amount_uzs,
                member_name=f"{who.last_name} {who.first_name}".strip(),
                member_username=who.telegram_username,
                member_telegram_id=who.telegram_id,
                approved_at=payment.decided_at,
                approved_by=_full(approver),
                delivered_at=payment.delivered_at,
                delivered_by=_full(giver),
            )
            for payment, who, approver, giver in rows
        ],
        waiting=waiting,
        senders=await card_payments.stars_senders_text(db),
    )


@router.post("/{payment_id}/delivered", response_model=dict[str, str], summary="I gifted the Stars in Telegram")
async def delivered(payment_id: uuid.UUID, current: Sender, db: DbSession) -> dict[str, str]:
    payment = await card_payments.mark_delivered(db, actor_id=current.user.id, payment_id=payment_id)
    return {"status": "delivered", "id": str(payment.id)}
