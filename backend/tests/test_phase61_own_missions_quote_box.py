"""Round L2–L3: a member sets missions for themself («🎯 O'z missiyam»), the admins see them, take good ideas
for everybody and remove unsuitable ones; the quote box asks «🔒 Shaxsiy» or «🌍 Umumiy» before saving."""

from __future__ import annotations

import itertools

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mission, ScoreTransaction
from app.services import membership
from app.services.settings import update_setting
from tests.factories import create_user
from tests.helpers import admin_headers, grant_role, member_headers

_ids = itertools.count(3_500_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _points(db: AsyncSession, user_id: object) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user_id, ScoreTransaction.source_type == "MISSION"
            )
        )
    )


async def test_a_member_sets_a_mission_for_themself(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    other = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)

    options = (await client.get("/api/v1/me/missions/options", headers=headers)).json()
    assert options["enabled"] and options["points"] == 2 and "🔥" in options["icons"]
    pages = next(item for item in options["metrics"] if item["code"] == "PAGES")
    assert (pages["min"], pages["points_from"]) == (5, 50)

    bad = await client.post(
        "/api/v1/me/missions",
        json={"title": "Bir kunda o'n kun", "metric": "READING_DAYS", "target": 10, "period_days": 7},
        headers=headers,
    )
    assert bad.status_code == 400 and "muddatni uzaytiring" in bad.json()["error"]["message"]
    created = await client.post(
        "/api/v1/me/missions",
        json={"title": "  Imtihondan  oldin 60 bet ", "icon": "🧠", "metric": "PAGES", "target": 60, "period_days": 7},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    mine = next(item for item in created.json() if item["personal"])
    assert (mine["title"], mine["icon"], mine["status"], mine["reward_points"]) == (
        "Imtihondan oldin 60 bet",
        "🧠",
        "ACTIVE",
        2,
    )  # started at once
    # nobody else sees it, and nobody else can take it
    others = (await client.get("/api/v1/me/missions", headers=member_headers(other))).json()
    assert all(item["id"] != mine["id"] for item in others)
    stolen = await client.post(f"/api/v1/me/missions/{mine['id']}/take", headers=member_headers(other))
    assert stolen.status_code == 404
    assert (await client.delete(f"/api/v1/me/missions/{mine['id']}", headers=member_headers(other))).status_code == 404

    # it counts real reading and pays the small reward
    item = (await client.post("/api/v1/me/shelf", json={"title": "Kecha va kunduz"}, headers=headers)).json()
    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 60}, headers=headers)
    done = next(m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["id"] == mine["id"])
    assert done["status"] == "COMPLETED"
    assert await _points(db, member.id) == 2

    # a very easy goal is fine for oneself, but earns nothing
    easy = await client.post(
        "/api/v1/me/missions",
        json={"title": "Besh bet", "metric": "PAGES", "target": 5, "period_days": 1},
        headers=headers,
    )
    easy_id = next(m["id"] for m in easy.json() if m["personal"] and m["title"] == "Besh bet")
    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 5}, headers=headers)
    finished = next(m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["id"] == easy_id)
    assert finished["status"] == "COMPLETED" and await _points(db, member.id) == 2

    removed = await client.delete(f"/api/v1/me/missions/{easy_id}", headers=headers)
    assert removed.status_code == 200 and all(m["id"] != easy_id for m in removed.json())

    # the admins can switch it off
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await update_setting(db, key="missions.personal_enabled", value=False, actor_id=boss.id)
    closed = await client.post(
        "/api/v1/me/missions",
        json={"title": "Yana bir", "metric": "BOOKS_FINISHED", "target": 1, "period_days": 30},
        headers=headers,
    )
    assert closed.status_code == 409


async def test_the_monthly_cap_and_the_admins_view(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids), first_name="Dilnoza", last_name="Aliyeva", group_name="5424")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await update_setting(db, key="missions.personal_monthly_limit", value=1, actor_id=boss.id)
    headers = member_headers(member)
    item = (await client.post("/api/v1/me/shelf", json={"title": "Ikki eshik orasi"}, headers=headers)).json()
    ids = []
    for title in ("Birinchi ellik", "Ikkinchi ellik"):
        created = await client.post(
            "/api/v1/me/missions",
            json={"title": title, "metric": "PAGES", "target": 50, "period_days": 7},
            headers=headers,
        )
        ids.append(next(m["id"] for m in created.json() if m["title"] == title))
    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 50}, headers=headers)
    await client.get("/api/v1/me/missions", headers=headers)
    assert await _points(db, member.id) == 2  # only one a month earns points

    admin = admin_headers(boss)
    overview = (await client.get("/api/v1/admin/missions/personal", headers=admin)).json()
    assert (overview["created"], overview["members"], overview["completed"]) == (2, 1, 2)
    assert overview["items"][0]["owner_name"] == "Aliyeva Dilnoza" and overview["popular"][0]["metric"] == "PAGES"
    club = (await client.get("/api/v1/admin/missions", headers=admin)).json()
    assert all(m["id"] not in ids for m in club)  # members' own missions are not the club's list
    # the club's editor cannot change a member's mission
    edit = await client.put(
        f"/api/v1/admin/missions/{ids[0]}",
        json={"title": "Boshqa", "metric": "PAGES", "target": 50, "period_days": 7},
        headers=admin,
    )
    assert edit.status_code == 404

    promoted = await client.post(f"/api/v1/admin/missions/personal/{ids[0]}/promote", headers=admin)
    draft = await db.get(Mission, promoted.json()["id"])
    assert (draft.title, draft.status.value, draft.owner_id) == ("Birinchi ellik", "DRAFT", None)
    gone = await client.delete(f"/api/v1/admin/missions/personal/{ids[1]}", headers=admin)
    assert gone.status_code == 204 and await db.get(Mission, ids[1]) is None

    # erasing the member's data removes their own missions too
    await membership.erase(db, member, actor_id=None, reason="test")
    assert await db.scalar(select(func.count()).select_from(Mission).where(Mission.owner_id == member.id)) == 0


async def test_saved_quotes_are_private_to_the_reading_diary(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    reader = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)
    item = (await client.post("/api/v1/me/shelf", json={"title": "Mehrobdan chayon"}, headers=headers)).json()

    saved = await client.post(
        "/api/v1/me/quotes",
        json={"text": "Faqat menga kerakli jumla.", "shelf_item_id": item["id"]},
        headers=headers,
    )
    assert saved.status_code == 201 and "shared" not in saved.json()

    # a saved line lives only on its book's page in «📚 Javonim» — never in the public «A'zolar fikrlari» feed
    detail = (await client.get(f"/api/v1/me/shelf/{item['id']}", headers=headers)).json()
    assert [quote["text"] for quote in detail["quotes"]] == ["Faqat menga kerakli jumla."]
    feed = (await client.get("/api/v1/community", headers=member_headers(reader))).json()
    assert feed == []

    # the standalone quote box and its public-sharing paths are gone for good
    assert (await client.get("/api/v1/me/quotes/options", headers=headers)).status_code in (404, 405)
    gone = await client.post("/api/v1/community/from-box", json={"saved_quote_id": saved.json()["id"]}, headers=headers)
    assert gone.status_code in (404, 405)

    # removing a quote is the member's own action
    removed = await client.delete(f"/api/v1/me/quotes/{saved.json()['id']}", headers=headers)
    assert removed.status_code == 204
