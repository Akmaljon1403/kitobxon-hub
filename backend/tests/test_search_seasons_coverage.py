"""Extra coverage for the admin search box (book/event/test/reward and number branches) and for
seasons (date validation, duplicate names, switching the current season)."""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Reward
from app.models.enums import RewardType, SeasonStatus
from app.security.permissions import Perm
from app.services import seasons
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role


async def test_search_finds_books_events_tests_rewards_and_numbers(client: httpx.AsyncClient, db: AsyncSession) -> None:
    await create_user(db, first_name="Dilshod", last_name="Rahimov", phone="998901234567")
    await create_book(db, title="Alkimyogar", author="Paulo Koelo")
    await create_event(db, title="Bahorgi kitob uchrashuvi")
    await create_test(db, title="Biologiya yakuniy testi")
    admin = await create_user(db)
    db.add(Reward(title="Sovrin: chegirma kitob", type=next(iter(RewardType))))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(
        db, admin, Perm.USER_VIEW, Perm.BOOK_VIEW, Perm.EVENT_VIEW, Perm.TEST_VIEW, Perm.REWARD_MANAGE
    )
    headers = admin_headers(admin)

    async def kinds(q: str) -> set[str]:
        found = (await client.get("/api/v1/admin/search", params={"q": q}, headers=headers)).json()
        return {item["kind"] for item in found}

    assert "book" in await kinds("alkimyogar")
    assert "event" in await kinds("bahorgi")
    assert "test" in await kinds("biologiya")
    assert "reward" in await kinds("sovrin")

    # The number branch (phone / membership number): three or more digits trigger a phone-digit search.
    by_phone = (await client.get("/api/v1/admin/search", params={"q": "901234567"}, headers=headers)).json()
    assert any(item["kind"] == "member" and item["title"] == "Rahimov Dilshod" for item in by_phone)


async def test_seasons_validation_and_switching(db: AsyncSession) -> None:
    admin = await create_user(db)
    await db.commit()
    actor = admin.id

    # End before start is rejected.
    with pytest.raises(BadRequestError):
        await seasons.create_season(
            db, actor_id=actor, name="Xato", starts_on=date(2027, 6, 1), ends_on=date(2027, 1, 1), make_current=False
        )

    planned = await seasons.create_season(
        db, actor_id=actor, name="Kuz 2026", starts_on=date(2026, 9, 1), ends_on=date(2026, 12, 31), make_current=False
    )
    assert planned.status == SeasonStatus.PLANNED and not planned.is_current

    # A duplicate name conflicts (and the session recovers).
    with pytest.raises(ConflictError):
        await seasons.create_season(
            db,
            actor_id=actor,
            name="Kuz 2026",
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 12, 31),
            make_current=False,
        )

    # make_current activates the new season; a later current season closes the previous one.
    first = await seasons.create_season(
        db, actor_id=actor, name="Bahor 2027", starts_on=date(2027, 1, 1), ends_on=date(2027, 6, 30), make_current=True
    )
    assert first.is_current and first.status == SeasonStatus.ACTIVE
    second = await seasons.create_season(
        db, actor_id=actor, name="Yoz 2027", starts_on=date(2027, 7, 1), ends_on=date(2027, 9, 30), make_current=True
    )
    assert second.is_current and second.status == SeasonStatus.ACTIVE
    reloaded = next(s for s in await seasons.list_seasons(db) if s.id == first.id)
    assert not reloaded.is_current and reloaded.status == SeasonStatus.CLOSED

    # Activating a season that does not exist is a clear not-found error.
    with pytest.raises(NotFoundError):
        await seasons.activate_season(db, actor_id=actor, season_id=uuid.uuid4())
