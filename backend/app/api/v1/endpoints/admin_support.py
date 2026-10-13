"""Admin Panel: members' messages ("Murojaatlar") and answers."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.core.errors import ForbiddenError, ServiceUnavailableError
from app.models.enums import SupportTicketKind, SupportTicketStatus
from app.schemas.common import Page
from app.schemas.support import (
    SupportMessageOut,
    SupportReplyIn,
    SupportStatusIn,
    SupportSummaryOut,
    SupportTicketDetailOut,
    SupportTicketOut,
)
from app.security.permissions import Perm
from app.services import support as support_service

router = APIRouter(prefix="/admin/support", tags=["admin: support"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.SUPPORT_MANAGE))]


@router.get("", response_model=Page[SupportTicketOut], summary="General conversations, unread first")
async def list_tickets(
    _: Manager,
    db: DbSession,
    status: SupportTicketStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SupportTicketOut]:
    # The panel «Murojaatlar» is for general questions; money conversations live in the payments channel.
    items, total = await support_service.list_tickets(
        db, status=status, limit=limit, offset=offset, kind=SupportTicketKind.GENERAL
    )
    return Page(items=[SupportTicketOut(**item) for item in items], total=total, limit=limit, offset=offset)


def _guard_payment(ticket_kind: SupportTicketKind, current: CurrentUser) -> None:
    """A money conversation in the panel is only for the owners and the admins given «💳 To'lov savollari» —
    a general-support admin never sees or answers it here (it belongs to the payments channel)."""
    if ticket_kind == SupportTicketKind.PAYMENT and Perm.PAYMENT_SUPPORT.value not in current.permissions:
        raise ForbiddenError("PAYMENT_SUPPORT_REQUIRED", "To'lov bo'yicha murojaat to'lovlar kanalida hal qilinadi.")


@router.get("/summary", response_model=SupportSummaryOut, summary="Number of conversations waiting for an answer")
async def summary(_: Manager, db: DbSession) -> SupportSummaryOut:
    return SupportSummaryOut(unread=await support_service.unread_count(db))


@router.get("/{ticket_id}", response_model=SupportTicketDetailOut, summary="Conversation (marks it as read)")
async def detail(ticket_id: uuid.UUID, current: Manager, db: DbSession) -> SupportTicketDetailOut:
    ticket = await support_service.get_ticket(db, ticket_id)
    _guard_payment(ticket.kind, current)
    return SupportTicketDetailOut(**await support_service.ticket_detail(db, ticket_id))


@router.post("/{ticket_id}/reply", response_model=SupportMessageOut, summary="Answer (sent to the member by the bot)")
async def reply(ticket_id: uuid.UUID, payload: SupportReplyIn, current: Manager, db: DbSession) -> SupportMessageOut:
    ticket = await support_service.get_ticket(db, ticket_id)
    payment = ticket.kind == SupportTicketKind.PAYMENT
    _guard_payment(ticket.kind, current)
    message = await support_service.admin_reply(
        db, actor_id=current.user.id, ticket_id=ticket_id, text=payload.text, payment=payment
    )
    return SupportMessageOut(
        id=message.id,
        from_admin=True,
        admin_name=current.user.full_name,
        text=message.text,
        has_photo=False,
        created_at=message.created_at,
    )


@router.post("/{ticket_id}/status", response_model=SupportSummaryOut, summary="Close or reopen a conversation")
async def set_status(
    ticket_id: uuid.UUID, payload: SupportStatusIn, current: Manager, db: DbSession
) -> SupportSummaryOut:
    ticket = await support_service.get_ticket(db, ticket_id)
    _guard_payment(ticket.kind, current)
    await support_service.set_status(db, actor_id=current.user.id, ticket_id=ticket_id, status=payload.status)
    return SupportSummaryOut(unread=await support_service.unread_count(db))


@router.get("/messages/{message_id}/photo", summary="Photo attached by the member (downloaded through the bot)")
async def photo(message_id: uuid.UUID, _: Manager, db: DbSession) -> Response:
    from app.bot.setup import get_bot_runtime

    file_id = await support_service.photo_file_id(db, message_id)
    runtime = get_bot_runtime()
    if runtime is None:
        raise ServiceUnavailableError("BOT_UNAVAILABLE", "Bot ishlamayapti, rasmni yuklab bo'lmadi.")
    telegram_file = await runtime.bot.get_file(file_id)
    assert telegram_file.file_path is not None
    data = await runtime.bot.download_file(telegram_file.file_path)
    assert data is not None
    return Response(content=data.read(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
