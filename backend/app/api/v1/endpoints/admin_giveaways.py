"""Admin Panel: promo-code giveaways (random draw, test leaders, event places, ranking)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession, require_permissions
from app.models import Giveaway
from app.models.enums import GiveawayRule
from app.schemas.giveaway import (
    GiveawayIn,
    GiveawayOut,
    GiveawayPreviewOut,
    GiveawayUpdateIn,
    GiveawayWinnerOut,
)
from app.security.permissions import Perm
from app.services import giveaways as giveaway_service

router = APIRouter(prefix="/admin/giveaways", tags=["admin: giveaways"])
Manager = Annotated[CurrentUser, Depends(require_permissions(Perm.REWARD_MANAGE))]


def _out(giveaway: Giveaway, reward_title: str, codes: int | None) -> GiveawayOut:
    return GiveawayOut(
        id=giveaway.id,
        title=giveaway.title,
        prize=giveaway.prize,
        prize_value=giveaway.prize_value,
        reward_id=giveaway.reward_id,
        reward_title=reward_title,
        codes_available=codes,
        rule=giveaway.rule,
        rule_title=giveaway_service.RULE_TITLES[GiveawayRule(giveaway.rule)],
        audience=giveaway.audience,
        winners_count=giveaway.winners_count,
        premium_bonus=giveaway.premium_bonus,
        period_start=giveaway.period_start,
        period_end=giveaway.period_end,
        period_label=giveaway_service.period_label(giveaway.period_start, giveaway.period_end),
        status=giveaway.status,
        scheduled_at=giveaway.scheduled_at,
        announce=giveaway.announce,
        repeat_monthly=giveaway.repeat_monthly,
        drawn_at=giveaway.drawn_at,
        seed=giveaway.seed,
        winners=[GiveawayWinnerOut(**entry) for entry in giveaway.results or []],
        created_at=giveaway.created_at,
    )


async def _one(db, giveaway_id: uuid.UUID) -> GiveawayOut:
    for giveaway, reward_title, codes in await giveaway_service.list_all(db):
        if giveaway.id == giveaway_id:
            return _out(giveaway, reward_title, codes)
    raise AssertionError("giveaway disappeared")


@router.get("", response_model=list[GiveawayOut], summary="Giveaways: planned first, then the latest drawn")
async def list_giveaways(_: Manager, db: DbSession) -> list[GiveawayOut]:
    return [_out(*row) for row in await giveaway_service.list_all(db)]


@router.post("", response_model=GiveawayOut, status_code=status.HTTP_201_CREATED, summary="Create a giveaway")
async def create_giveaway(payload: GiveawayIn, current: Manager, db: DbSession) -> GiveawayOut:
    giveaway = await giveaway_service.create(db, actor_id=current.user.id, data=payload.model_dump())
    return await _one(db, giveaway.id)


@router.patch("/{giveaway_id}", response_model=GiveawayOut, summary="Edit a planned giveaway")
async def update_giveaway(
    giveaway_id: uuid.UUID, payload: GiveawayUpdateIn, current: Manager, db: DbSession
) -> GiveawayOut:
    await giveaway_service.update(
        db, actor_id=current.user.id, giveaway_id=giveaway_id, changes=payload.model_dump(exclude_unset=True)
    )
    return await _one(db, giveaway_id)


@router.get("/{giveaway_id}/preview", response_model=GiveawayPreviewOut, summary="Who would win now (dry run)")
async def preview_giveaway(giveaway_id: uuid.UUID, _: Manager, db: DbSession) -> GiveawayPreviewOut:
    return GiveawayPreviewOut(**await giveaway_service.preview(db, giveaway_id))


@router.post("/{giveaway_id}/draw", response_model=GiveawayOut, summary="Draw now and hand out the codes")
async def draw_giveaway(giveaway_id: uuid.UUID, current: Manager, db: DbSession) -> GiveawayOut:
    await giveaway_service.draw(db, actor_id=current.user.id, giveaway_id=giveaway_id)
    return await _one(db, giveaway_id)


@router.post("/{giveaway_id}/cancel", response_model=GiveawayOut, summary="Cancel a planned giveaway")
async def cancel_giveaway(giveaway_id: uuid.UUID, current: Manager, db: DbSession) -> GiveawayOut:
    await giveaway_service.cancel(db, actor_id=current.user.id, giveaway_id=giveaway_id)
    return await _one(db, giveaway_id)
