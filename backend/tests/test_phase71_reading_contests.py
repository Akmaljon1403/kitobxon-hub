"""Round N7: reading contests («1 hafta — 1 kitob», «1 oy — 1 kitob» …) that never mix.

Several contests can run at once; each has its own book(s), its own participants, its own channel
post and its own report. Joining or finishing one must not touch another.
"""

from __future__ import annotations

import itertools
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, ChannelPost, ScoreTransaction
from app.models.enums import CampaignStatus, ChannelPostKind, ScoreCategory
from app.services import campaigns
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_role

_ids = itertools.count(4_800_000)


async def _boss(db: AsyncSession):
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    return boss


async def _make(db: AsyncSession, boss, book, *, name: str, points: int = 10, bonus: int = 0) -> Campaign:
    now = datetime.now(UTC)
    return await campaigns.create(
        db,
        actor_id=boss.id,
        name=name,
        description=None,
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=7),
        points_per_book=points,
        completion_bonus=bonus,
        book_ids=[book.id],
    )


async def test_two_contests_stay_separate(db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids))
    book_a = await create_book(db, title="Hafta kitobi")
    book_b = await create_book(db, title="Oy kitobi")
    await db.commit()
    week = await _make(db, boss, book_a, name="1 hafta — 1 kitob")
    month = await _make(db, boss, book_b, name="1 oy — 1 kitob")
    await campaigns.set_status(db, actor_id=boss.id, campaign=week, status=CampaignStatus.ACTIVE)
    await campaigns.set_status(db, actor_id=boss.id, campaign=month, status=CampaignStatus.ACTIVE)

    # the member joins ONLY the weekly contest and finishes it
    await campaigns.join(db, user_id=member.id, campaign_id=week.id)
    await campaigns.mark_completed(db, user_id=member.id, campaign_id=week.id)

    week_participants = await campaigns.participants(db, week.id)
    month_participants = await campaigns.participants(db, month.id)
    assert len(week_participants) == 1 and week_participants[0][1].id == member.id
    assert month_participants == []  # the other contest is untouched


async def test_verify_awards_points_once(db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids))
    book = await create_book(db, title="Tanlov kitobi")
    await db.commit()
    campaign = await _make(db, boss, book, name="Tanlov", points=15, bonus=5)
    await campaigns.set_status(db, actor_id=boss.id, campaign=campaign, status=CampaignStatus.ACTIVE)
    await campaigns.join(db, user_id=member.id, campaign_id=campaign.id)
    await campaigns.mark_completed(db, user_id=member.id, campaign_id=campaign.id)

    await campaigns.verify(db, actor_id=boss.id, campaign_id=campaign.id, user_id=member.id)
    await campaigns.verify(db, actor_id=boss.id, campaign_id=campaign.id, user_id=member.id)  # idempotent

    rows = list(
        await db.scalars(
            select(ScoreTransaction).where(
                ScoreTransaction.user_id == member.id, ScoreTransaction.category == ScoreCategory.CAMPAIGN
            )
        )
    )
    assert len(rows) == 1 and rows[0].amount == 20  # 15 per book + 5 bonus, once


async def test_complete_needs_join_and_active(db: AsyncSession) -> None:
    import pytest

    from app.core.errors import AppError

    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids))
    book = await create_book(db)
    await db.commit()
    campaign = await _make(db, boss, book, name="Hali boshlanmagan")  # still DRAFT
    with pytest.raises(AppError):
        await campaigns.join(db, user_id=member.id, campaign_id=campaign.id)  # not active


async def test_admin_flow_and_isolated_channel_posts(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids))
    book_a = await create_book(db, title="A kitob")
    book_b = await create_book(db, title="B kitob")
    await db.commit()
    headers = admin_headers(boss)
    now = datetime.now(UTC)
    base = {
        "description": None,
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "points_per_book": 10,
        "completion_bonus": 0,
    }
    first = await client.post(
        "/api/v1/admin/campaigns", json={**base, "name": "Tanlov A", "book_ids": [str(book_a.id)]}, headers=headers
    )
    second = await client.post(
        "/api/v1/admin/campaigns", json={**base, "name": "Tanlov B", "book_ids": [str(book_b.id)]}, headers=headers
    )
    assert first.status_code == 201 and second.status_code == 201
    a_id, b_id = first.json()["id"], second.json()["id"]

    # start both and announce both — each gets its own channel post, nothing shared
    for cid in (a_id, b_id):
        started = await client.post(
            f"/api/v1/admin/campaigns/{cid}/status", json={"status": "ACTIVE", "announce": True}, headers=headers
        )
        assert started.status_code == 200
    posts = list(await db.scalars(select(ChannelPost).where(ChannelPost.kind == ChannelPostKind.CAMPAIGN)))
    assert {post.dedup_key for post in posts} == {f"campaign:{a_id}", f"campaign:{b_id}"}

    # the member joins A, finishes it; the admin confirms and the report lists them
    await campaigns.join(db, user_id=member.id, campaign_id=uuid.UUID(a_id))
    await campaigns.mark_completed(db, user_id=member.id, campaign_id=uuid.UUID(a_id))
    verified = await client.post(f"/api/v1/admin/campaigns/{a_id}/participants/{member.id}/verify", headers=headers)
    assert verified.status_code == 204

    listed = await client.get("/api/v1/admin/campaigns", headers=headers)
    by_id = {item["id"]: item for item in listed.json()}
    assert by_id[a_id]["verified"] == 1 and by_id[b_id]["participants"] == 0  # B untouched

    report = await client.get(f"/api/v1/admin/campaigns/{a_id}/report?format=xlsx", headers=headers)
    assert report.status_code == 200 and len(report.content) > 0


async def test_point_defaults_remember_last_used(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """The contest form (now inside Tadbirlar) starts from the last-used points."""
    boss = await _boss(db)
    book = await create_book(db)
    await db.commit()
    headers = admin_headers(boss)
    now = datetime.now(UTC)
    body = {
        "name": "Default sinovi",
        "description": None,
        "starts_at": (now - timedelta(days=1)).isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "points_per_book": 25,
        "completion_bonus": 7,
        "book_ids": [str(book.id)],
    }
    created = await client.post("/api/v1/admin/campaigns", json=body, headers=headers)
    assert created.status_code == 201
    defaults = await client.get("/api/v1/admin/campaigns/defaults", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json() == {"points_per_book": 25, "completion_bonus": 7}


async def test_delete_hides_contest(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    book = await create_book(db)
    await db.commit()
    campaign = await _make(db, boss, book, name="O'chiriladi")
    removed = await client.delete(f"/api/v1/admin/campaigns/{campaign.id}", headers=admin_headers(boss))
    assert removed.status_code == 204
    remaining = await db.scalar(select(func.count()).select_from(Campaign).where(Campaign.deleted_at.is_(None)))
    assert remaining == 0
