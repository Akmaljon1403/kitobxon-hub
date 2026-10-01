"""Seasons: competition periods. Switching the current season never deletes history."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Season
from app.models.enums import SeasonStatus
from app.services.audit import record_audit


async def list_seasons(session: AsyncSession) -> list[Season]:
    return list(await session.scalars(select(Season).order_by(Season.starts_on.desc())))


async def create_season(
    session: AsyncSession, *, actor_id: uuid.UUID, name: str, starts_on: date, ends_on: date, make_current: bool
) -> Season:
    if ends_on < starts_on:
        raise BadRequestError("INVALID_DATES", "Mavsum tugash sanasi boshlanishidan oldin bo'lishi mumkin emas.")
    season = Season(name=name.strip(), starts_on=starts_on, ends_on=ends_on, status=SeasonStatus.PLANNED)
    session.add(season)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("SEASON_EXISTS", "Bunday nomli mavsum allaqachon mavjud.") from exc
    record_audit(
        session,
        actor_id=actor_id,
        action="SEASON_CREATE",
        entity_type="season",
        entity_id=season.id,
        after={"name": season.name, "starts_on": str(starts_on), "ends_on": str(ends_on)},
    )
    await session.commit()
    if make_current:
        return await activate_season(session, actor_id=actor_id, season_id=season.id)
    return season


async def activate_season(session: AsyncSession, *, actor_id: uuid.UUID, season_id: uuid.UUID) -> Season:
    season = await session.get(Season, season_id)
    if season is None:
        raise NotFoundError("SEASON_NOT_FOUND", "Mavsum topilmadi.")
    previous = await session.scalar(select(Season).where(Season.is_current.is_(True)))
    if previous is not None and previous.id != season.id:
        previous.is_current = False
        previous.status = SeasonStatus.CLOSED
        await session.flush()
    await session.execute(
        update(Season).where(Season.id == season.id).values(is_current=True, status=SeasonStatus.ACTIVE)
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="SEASON_ACTIVATE",
        entity_type="season",
        entity_id=season.id,
        before={"current": previous.name if previous else None},
        after={"current": season.name},
    )
    await session.commit()
    await session.refresh(season)
    return season
