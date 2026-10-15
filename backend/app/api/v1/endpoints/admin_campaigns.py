"""Admin Panel: reading contests («1 hafta — 1 kitob» …) — each one isolated from the others."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.api.v1.endpoints.my_documents import file_response
from app.models import Book, Campaign
from app.schemas.campaign import (
    CampaignBookOut,
    CampaignOut,
    CampaignParticipantOut,
    CampaignStatusIn,
    CampaignUpsertIn,
)
from app.security.permissions import Perm
from app.services import campaigns as campaign_service
from app.services import document_render
from app.services.document_render import MIME
from app.services.passport import member_number

router = APIRouter(prefix="/admin/campaigns", tags=["admin: reading contests"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.SEASON_MANAGE))]
Format = Literal["xlsx", "pdf", "docx"]


def _out(campaign: Campaign, books: list[Book], counts: tuple[int, int]) -> CampaignOut:
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        status=campaign.status,
        points_per_book=campaign.points_per_book,
        completion_bonus=campaign.completion_bonus,
        books=[CampaignBookOut(id=book.id, title=book.title, author=book.author) for book in books],
        participants=counts[0],
        verified=counts[1],
    )


async def _one(db: DbSession, campaign: Campaign) -> CampaignOut:
    books = await campaign_service.books_of(db, campaign.id)
    counts = (await campaign_service._counts(db, [campaign.id])).get(campaign.id, (0, 0))
    return _out(campaign, books, counts)


@router.get("", response_model=list[CampaignOut], summary="All reading contests")
async def list_campaigns(_: Manager, db: DbSession) -> list[CampaignOut]:
    return [_out(campaign, books, counts) for campaign, books, counts in await campaign_service.list_campaigns(db)]


@router.post("", response_model=CampaignOut, status_code=201, summary="Create a reading contest")
async def create_campaign(payload: CampaignUpsertIn, current: Manager, db: DbSession) -> CampaignOut:
    campaign = await campaign_service.create(
        db,
        actor_id=current.user.id,
        name=payload.name,
        description=payload.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        points_per_book=payload.points_per_book,
        completion_bonus=payload.completion_bonus,
        book_ids=payload.book_ids,
    )
    return await _one(db, campaign)


@router.get("/{campaign_id}", response_model=CampaignOut, summary="One contest")
async def get_campaign(campaign_id: uuid.UUID, _: Manager, db: DbSession) -> CampaignOut:
    return await _one(db, await campaign_service.get(db, campaign_id))


@router.put("/{campaign_id}", response_model=CampaignOut, summary="Edit a contest")
async def update_campaign(
    campaign_id: uuid.UUID, payload: CampaignUpsertIn, current: Manager, db: DbSession
) -> CampaignOut:
    campaign = await campaign_service.get(db, campaign_id)
    campaign = await campaign_service.update(
        db,
        actor_id=current.user.id,
        campaign=campaign,
        name=payload.name,
        description=payload.description,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        points_per_book=payload.points_per_book,
        completion_bonus=payload.completion_bonus,
        book_ids=payload.book_ids,
    )
    return await _one(db, campaign)


@router.delete("/{campaign_id}", status_code=204, summary="Remove a contest")
async def delete_campaign(campaign_id: uuid.UUID, current: Manager, db: DbSession) -> Response:
    campaign = await campaign_service.get(db, campaign_id)
    await campaign_service.delete_campaign(db, actor_id=current.user.id, campaign=campaign)
    return Response(status_code=204)


@router.post("/{campaign_id}/status", response_model=CampaignOut, summary="Start, finish or archive a contest")
async def set_status(campaign_id: uuid.UUID, payload: CampaignStatusIn, current: Manager, db: DbSession) -> CampaignOut:
    campaign = await campaign_service.get(db, campaign_id)
    campaign = await campaign_service.set_status(
        db, actor_id=current.user.id, campaign=campaign, status=payload.status, announce=payload.announce
    )
    return await _one(db, campaign)


@router.post("/{campaign_id}/announce", status_code=204, summary="Post the contest to the channel")
async def announce(campaign_id: uuid.UUID, current: Manager, db: DbSession) -> Response:
    campaign = await campaign_service.get(db, campaign_id)
    await campaign_service.announce_to_channel(db, campaign, actor_id=current.user.id)
    return Response(status_code=204)


@router.get("/{campaign_id}/participants", response_model=list[CampaignParticipantOut], summary="Who is taking part")
async def participants(campaign_id: uuid.UUID, _: Manager, db: DbSession) -> list[CampaignParticipantOut]:
    await campaign_service.get(db, campaign_id)
    rows = await campaign_service.participants(db, campaign_id)
    return [
        CampaignParticipantOut(
            user_id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            member_number=member_number(user),
            group_name=user.group_name,
            completed_at=participant.completed_at,
            verified_at=participant.verified_at,
        )
        for participant, user in rows
    ]


@router.post(
    "/{campaign_id}/participants/{user_id}/verify",
    status_code=204,
    summary="Confirm a member finished the contest's book (awards the points once)",
)
async def verify(campaign_id: uuid.UUID, user_id: uuid.UUID, current: Manager, db: DbSession) -> Response:
    await campaign_service.verify(db, actor_id=current.user.id, campaign_id=campaign_id, user_id=user_id)
    return Response(status_code=204)


@router.get("/{campaign_id}/report", summary="Download this contest's report (isolated)", response_class=Response)
async def report(
    campaign_id: uuid.UUID, _: Manager, db: DbSession, format: Annotated[Format, Query()] = "xlsx"
) -> Response:
    campaign = await campaign_service.get(db, campaign_id)
    document = await campaign_service.report(db, campaign)
    data = await document_render.render(document, format)
    return file_response(data, MIME[format], f"{document.filename}.{format}", attachment=True)
