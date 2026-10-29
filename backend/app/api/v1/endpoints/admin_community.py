"""Admin Panel: «💬 A'zolar fikrlari» — what members wrote (quotes, thoughts, impressions, testimonials):
approve, feature, hide, fix a typo, and use it anywhere: a card in the channel, a message to members,
the quote of the day, or the admin's own chat to forward."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models.enums import ContributionKind
from app.security.permissions import Perm
from app.services import community, share_cards

router = APIRouter(prefix="/admin/community", tags=["admin: community"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.COMMUNITY_MANAGE))]
Sender = Annotated[CurrentUser, Depends(require_permissions(Perm.COMMUNITY_MANAGE, Perm.NOTIFICATION_SEND))]
PNG = {200: {"content": {"image/png": {}}}}


class ModerateIn(BaseModel):
    action: Literal["approve", "hide", "feature", "unfeature", "pending"]


class EditIn(BaseModel):
    text: str = Field(min_length=community.MIN_TEXT, max_length=community.MAX_TEXT)
    source: str | None = Field(default=None, max_length=community.MAX_SOURCE)


class ChannelIn(BaseModel):
    style: str | None = Field(default=None, max_length=16)
    caption: str | None = Field(default=None, max_length=900)
    scheduled_at: datetime | None = None


class MembersIn(BaseModel):
    style: str | None = Field(default=None, max_length=16)
    caption: str | None = Field(default=None, max_length=900)
    faculty_id: uuid.UUID | None = None
    course: int | None = Field(default=None, ge=1, le=10)
    group_name: str | None = Field(default=None, max_length=16)
    dry_run: bool = False


class StyleIn(BaseModel):
    style: str | None = Field(default=None, max_length=16)


class QuoteDayIn(BaseModel):
    day: date | None = None


@router.get("", summary="Members' texts with filters, and the counts per tab")
async def list_contributions(
    _: Manager,
    db: DbSession,
    status: Literal["PENDING", "APPROVED", "HIDDEN", "FEATURED"] | None = None,
    kind: ContributionKind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return {
        "counts": await community.admin_counts(db),
        "items": await community.admin_list(db, status=status, kind=kind, q=q, limit=limit, offset=offset),
        "styles": [{"code": style.code, "title": style.title} for style in share_cards.STYLES.values()],
        "kinds": [{"code": kind, "title": title} for kind, (title, _, _) in community.KINDS.items()],
        "next_quote_day": await community.next_free_quote_day(db),
    }


@router.post("/{contribution_id}/moderate", summary="Approve, feature, hide")
async def moderate(contribution_id: uuid.UUID, payload: ModerateIn, current: Manager, db: DbSession) -> dict[str, Any]:
    item = await community.moderate(
        db, actor_id=current.user.id, contribution_id=contribution_id, action=payload.action
    )
    return {"id": item.id, "status": item.status, "featured": item.featured}


@router.patch("/{contribution_id}", summary="Fix the text or its source")
async def edit(contribution_id: uuid.UUID, payload: EditIn, current: Manager, db: DbSession) -> dict[str, Any]:
    item = await community.edit(
        db, actor_id=current.user.id, contribution_id=contribution_id, text=payload.text, source=payload.source
    )
    return {"id": item.id, "text": item.text, "source": item.source}


@router.get("/{contribution_id}/card.png", response_class=Response, responses=PNG, summary="The card in a design")
async def card(
    contribution_id: uuid.UUID,
    _: Manager,
    db: DbSession,
    style: Annotated[str | None, Query(max_length=16)] = None,
    download: bool = False,
) -> Response:
    item = await community.get(db, contribution_id)
    user, faculty = await community.author_of(db, item)
    image = await community.card_png(db, item, user, faculty, style)
    headers = {"Content-Disposition": f'attachment; filename="{community.card_filename(item)}"'} if download else {}
    return Response(content=image, media_type="image/png", headers=headers)


@router.post("/{contribution_id}/channel", summary="Post the card in the club channel (now or later)")
async def to_channel(contribution_id: uuid.UUID, payload: ChannelIn, current: Sender, db: DbSession) -> dict[str, Any]:
    return await community.to_channel(
        db,
        actor_id=current.user.id,
        contribution_id=contribution_id,
        style=payload.style,
        caption=payload.caption,
        scheduled_at=payload.scheduled_at,
    )


@router.post("/{contribution_id}/members", summary="Send the card to members (all, or a faculty/course/group)")
async def to_members(contribution_id: uuid.UUID, payload: MembersIn, current: Sender, db: DbSession) -> dict[str, int]:
    count = await community.to_members(
        db,
        actor_id=current.user.id,
        contribution_id=contribution_id,
        style=payload.style,
        caption=payload.caption,
        faculty_id=payload.faculty_id,
        course=payload.course,
        group_name=payload.group_name,
        dry_run=payload.dry_run,
    )
    return {"recipients": count}


@router.post("/{contribution_id}/me", summary="The bot sends the card to my chat (to forward anywhere)")
async def to_me(contribution_id: uuid.UUID, payload: StyleIn, current: Manager, db: DbSession) -> dict[str, bool]:
    await community.to_me(db, actor=current.user, contribution_id=contribution_id, style=payload.style)
    return {"sent": True}


@router.post("/{contribution_id}/quote-of-day", summary="Schedule the text as the quote of the day")
async def to_quote_of_day(
    contribution_id: uuid.UUID, payload: QuoteDayIn, current: Manager, db: DbSession
) -> dict[str, Any]:
    quote = await community.to_quote_of_day(
        db, actor_id=current.user.id, contribution_id=contribution_id, day=payload.day
    )
    return {"quote_id": quote.id, "day": quote.scheduled_date}
