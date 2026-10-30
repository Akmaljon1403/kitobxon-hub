"""Round J: «📚 Mening mutolaam» — the bookshelf and reading diary, «Kitobdan keyin 3 savol», the quote box
with shareable cards, «🪪 Kitobxonlik kartam» and personal missions."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendPhoto
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import BookQuote, BookRead, Mission, Notification, ReadingLog, ScoreTransaction, UserMission
from app.models.enums import BookStatus, FeatureMode, QuoteStatus, ReadingStatus, UserMissionStatus
from app.services import features, missions, reading_journal
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_user
from tests.helpers import admin_headers, grant_role, member_headers

_ids = itertools.count(2_500_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _points(db: AsyncSession, user_id: object, source: str) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user_id, ScoreTransaction.source_type == source
            )
        )
    )


async def test_the_shelf_follows_the_club_books_and_keeps_own_books(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    book = await create_book(db, title="O'tkan kunlar", status=BookStatus.ACTIVE, pages=320)
    draft = await create_book(db, title="Qoralama", status=BookStatus.DRAFT)
    await db.commit()
    headers = member_headers(member)

    added = await client.post("/api/v1/me/shelf", json={"book_id": str(book.id), "status": "READING"}, headers=headers)
    assert added.status_code == 201, added.text
    item = added.json()
    assert (item["title"], item["club_book"], item["pages_total"], item["status"]) == (
        "O'tkan kunlar",
        True,
        320,
        "READING",
    )
    read = await db.scalar(select(BookRead).where(BookRead.user_id == member.id, BookRead.book_id == book.id))
    assert read is not None and read.status == ReadingStatus.READING  # the club list follows the shelf
    again = await client.post("/api/v1/me/shelf", json={"book_id": str(book.id)}, headers=headers)
    assert again.status_code == 409
    hidden = await client.post("/api/v1/me/shelf", json={"book_id": str(draft.id)}, headers=headers)
    assert hidden.status_code == 404

    own = await client.post(
        "/api/v1/me/shelf", json={"title": "Alkimyogar", "author": "Paulo Koelo", "pages_total": 200}, headers=headers
    )
    assert own.status_code == 201 and own.json()["status"] == "WANT"
    nameless = await client.post("/api/v1/me/shelf", json={"title": "  "}, headers=headers)
    assert nameless.status_code == 400

    finished = await client.patch(
        f"/api/v1/me/shelf/{item['id']}", json={"status": "FINISHED", "rating": 5}, headers=headers
    )
    assert finished.json()["status"] == "FINISHED" and finished.json()["rating"] == 5
    await db.refresh(read)
    assert read.status == ReadingStatus.COMPLETED

    # Pressing «O'qiyapman» on a club book page puts it on the shelf too.
    other = await create_book(db, title="Mehrobdan chayon", status=BookStatus.ACTIVE)
    await db.commit()
    await client.post(f"/api/v1/books/{other.id}/reading", json={"action": "start"}, headers=headers)
    shelf = (await client.get("/api/v1/me/shelf", headers=headers)).json()
    assert {(entry["title"], entry["status"]) for entry in shelf["items"]} == {
        ("O'tkan kunlar", "FINISHED"),
        ("Alkimyogar", "WANT"),
        ("Mehrobdan chayon", "READING"),
    }
    assert shelf["items"][0]["status"] == "READING"  # «O'qiyapman» first
    assert shelf["stats"]["shelf"] == {"WANT": 1, "READING": 1, "FINISHED": 1, "LATER": 0}

    removed = await client.delete(f"/api/v1/me/shelf/{own.json()['id']}", headers=headers)
    assert removed.status_code == 204


async def test_the_reading_diary_streak_and_daily_limit(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)
    item = (
        await client.post("/api/v1/me/shelf", json={"title": "Sariq devni minib", "pages_total": 100}, headers=headers)
    ).json()

    logged = await client.post(
        f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 30, "note": "Kulgili!"}, headers=headers
    )
    assert logged.status_code == 200
    assert (logged.json()["status"], logged.json()["pages_read"], logged.json()["percent"]) == ("READING", 30, 30)
    too_old = await client.post(
        f"/api/v1/me/shelf/{item['id']}/logs",
        json={"pages": 5, "day": (reading_journal.today() - timedelta(days=9)).isoformat()},
        headers=headers,
    )
    assert too_old.status_code == 400
    await update_setting(db, key="reading.daily_page_limit", value=50, actor_id=None)
    over = await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 25}, headers=headers)
    assert over.status_code == 400 and "50" in over.json()["error"]["message"]

    # Yesterday and the day before: a three-day streak.
    for back in (1, 2):
        await client.post(
            f"/api/v1/me/shelf/{item['id']}/logs",
            json={"pages": 10, "day": (reading_journal.today() - timedelta(days=back)).isoformat()},
            headers=headers,
        )
    stats = (await client.get("/api/v1/me/shelf", headers=headers)).json()["stats"]
    assert (stats["today_pages"], stats["streak"], stats["best_streak"]) == (30, 3, 3)
    assert stats["last_days"][-1]["pages"] == 30 and len(stats["last_days"]) == 14

    diary = (await client.get("/api/v1/me/diary", headers=headers)).json()
    assert diary[0]["note"] == "Kulgili!" and diary[0]["title"] == "Sariq devni minib"
    gone = await client.delete(f"/api/v1/me/diary/{diary[0]['id']}", headers=headers)
    assert gone.status_code == 204
    detail = (await client.get(f"/api/v1/me/shelf/{item['id']}", headers=headers)).json()
    assert detail["pages_read"] == 20 and len(detail["diary"]) == 2

    assert reading_journal.streaks([], reading_journal.today()) == (0, 0)


async def test_three_questions_after_a_book(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)
    first = (await client.post("/api/v1/me/shelf", json={"title": "Ufq"}, headers=headers)).json()
    answers = {
        "main_idea": "Vatan va inson taqdiri haqida",
        "favorite_moment": "Qaytish sahnasi juda ta'sirli",
        "apply_in_life": "Sabr va mehnatni qadrlash",
    }
    early = await client.put(f"/api/v1/me/shelf/{first['id']}/reflection", json=answers, headers=headers)
    assert early.status_code == 409

    # A book of one's own that was never read (no diary) earns nothing — answers are still kept.
    unread = (
        await client.post("/api/v1/me/shelf", json={"title": "Bo'sh", "status": "FINISHED"}, headers=headers)
    ).json()
    nothing = await client.put(f"/api/v1/me/shelf/{unread['id']}/reflection", json=answers, headers=headers)
    assert nothing.status_code == 200 and nothing.json()["points"] == 0

    await client.post(f"/api/v1/me/shelf/{first['id']}/logs", json={"pages": 40}, headers=headers)
    await client.patch(f"/api/v1/me/shelf/{first['id']}", json={"status": "FINISHED"}, headers=headers)
    short = await client.put(
        f"/api/v1/me/shelf/{first['id']}/reflection", json={**answers, "main_idea": "Yaxshi"}, headers=headers
    )
    assert short.status_code == 400
    saved = await client.put(f"/api/v1/me/shelf/{first['id']}/reflection", json=answers, headers=headers)
    assert saved.status_code == 200 and saved.json()["points"] == 5
    edited = await client.put(
        f"/api/v1/me/shelf/{first['id']}/reflection",
        json={**answers, "apply_in_life": "Har kuni o'qishni odat qilish"},
        headers=headers,
    )
    assert edited.json()["points"] == 0 and edited.json()["apply_in_life"].startswith("Har kuni")  # points once
    assert await _points(db, member.id, "REFLECTION") == 5

    await update_setting(db, key="reading.reflection_monthly_limit", value=1, actor_id=None)
    second = (
        await client.post("/api/v1/me/shelf", json={"title": "Kecha va kunduz", "status": "FINISHED"}, headers=headers)
    ).json()
    await client.post(f"/api/v1/me/shelf/{second['id']}/logs", json={"pages": 30}, headers=headers)
    capped = await client.put(f"/api/v1/me/shelf/{second['id']}/reflection", json=answers, headers=headers)
    assert capped.json()["points"] == 0  # this month's limit is reached
    detail = (await client.get(f"/api/v1/me/shelf/{second['id']}", headers=headers)).json()
    assert detail["reflection"]["main_idea"] == answers["main_idea"]


async def test_the_quote_box_and_shareable_cards(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    member = await create_user(db, telegram_id=next(_ids), first_name="Madina", last_name="Karimova")
    book = await create_book(db, title="O'tkan kunlar", author="Abdulla Qodiriy", status=BookStatus.ACTIVE)
    club = BookQuote(book_id=book.id, text="Ilm — saodat kaliti.", status=QuoteStatus.SENT)
    db.add(club)
    await db.commit()
    headers = member_headers(member)
    item = (await client.post("/api/v1/me/shelf", json={"book_id": str(book.id)}, headers=headers)).json()

    typed = await client.post(
        "/api/v1/me/quotes",
        json={"text": "Kitob — eng sodiq do'st.", "shelf_item_id": item["id"], "page": 12, "note": "1-bob"},
        headers=headers,
    )
    assert typed.status_code == 201 and typed.json()["source"] == "Abdulla Qodiriy — O'tkan kunlar"
    saved = await client.post("/api/v1/me/quotes", json={"book_quote_id": str(club.id)}, headers=headers)
    twice = await client.post("/api/v1/me/quotes", json={"book_quote_id": str(club.id)}, headers=headers)
    assert saved.json()["id"] == twice.json()["id"]  # a club quote is kept once
    empty = await client.post("/api/v1/me/quotes", json={"text": "   "}, headers=headers)
    assert empty.status_code == 400

    # the saved lines live on the book's page in «📚 Javonim» (the reading diary)
    detail = (await client.get(f"/api/v1/me/shelf/{item['id']}", headers=headers)).json()
    assert "Kitob — eng sodiq do'st." in [quote["text"] for quote in detail["quotes"]]

    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.runtime_bot", lambda: bot)
    my_card = await client.get("/api/v1/me/reading-card.png", headers=headers)
    assert my_card.status_code == 200 and my_card.content.startswith(b"\x89PNG")
    await client.post("/api/v1/me/reading-card/send", headers=headers)
    assert any(isinstance(request, SendPhoto) for request in session.requests)

    removed = await client.delete(f"/api/v1/me/quotes/{saved.json()['id']}", headers=headers)
    assert removed.status_code == 204
    stranger = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    foreign = await client.get(f"/api/v1/me/shelf/{item['id']}", headers=member_headers(stranger))
    assert foreign.status_code == 404  # nobody sees another member's shelf or its quotes


async def test_personal_missions_count_real_activity(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)
    listed = (await client.get("/api/v1/me/missions", headers=headers)).json()
    assert {mission["title"] for mission in listed} >= {"7 kunda 100 bet", "5 kun ketma-ket o'qish"}  # ready-made
    pages = next(mission for mission in listed if mission["metric"] == "PAGES")

    item = (await client.post("/api/v1/me/shelf", json={"title": "Dunyoning ishlari"}, headers=headers)).json()
    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 60}, headers=headers)  # before taking it
    taken = await client.post(f"/api/v1/me/missions/{pages['id']}/take", headers=headers)
    mine = next(mission for mission in taken.json() if mission["id"] == pages["id"])
    assert (mine["status"], mine["progress"]) == ("ACTIVE", 0)  # only what is read after taking it counts
    again = await client.post(f"/api/v1/me/missions/{pages['id']}/take", headers=headers)
    assert again.status_code == 409

    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 70}, headers=headers)
    await client.post(f"/api/v1/me/shelf/{item['id']}/logs", json={"pages": 40}, headers=headers)
    done = next(m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["id"] == pages["id"])
    assert (done["status"], done["progress"]) == ("COMPLETED", 100)
    assert await _points(db, member.id, "MISSION") == 15
    message = await db.scalar(select(Notification).where(Notification.dedup_key.like("mission-done:%")))
    assert "Missiya bajarildi: 7 kunda 100 bet" in message.text and message.payload["mood"] == "CELEBRATE"
    finished_again = await client.post(f"/api/v1/me/missions/{pages['id']}/take", headers=headers)
    assert finished_again.status_code == 409

    # A mission that runs out can be taken again; giving up closes it.
    streak = next(mission for mission in listed if mission["metric"] == "STREAK")
    await client.post(f"/api/v1/me/missions/{streak['id']}/take", headers=headers)
    running = await db.scalar(select(UserMission).where(UserMission.mission_id == streak["id"]))
    running.deadline = datetime.now(UTC) - timedelta(minutes=1)
    running.updated_at = datetime.now(UTC) - timedelta(hours=1)
    await db.commit()
    assert await missions.check_running(db) == 0
    await db.refresh(running)
    assert running.status == UserMissionStatus.EXPIRED
    retried = await client.post(f"/api/v1/me/missions/{streak['id']}/take", headers=headers)
    assert next(m for m in retried.json() if m["id"] == streak["id"])["attempts"] == 2
    gave_up = await client.post(f"/api/v1/me/missions/{streak['id']}/give-up", headers=headers)
    assert next(m for m in gave_up.json() if m["id"] == streak["id"])["status"] == "EXPIRED"


async def test_missions_in_the_admin_panel_and_switches(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await create_user(db, telegram_id=next(_ids))
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    headers = admin_headers(boss)
    metrics = (await client.get("/api/v1/admin/missions/metrics", headers=headers)).json()
    assert {metric["code"] for metric in metrics} >= {"PAGES", "EVENTS", "QUOTES"}
    created = await client.post(
        "/api/v1/admin/missions",
        json={"title": "3 ta iqtibos", "metric": "QUOTES", "target": 3, "period_days": 7, "reward_points": 4},
        headers=headers,
    )
    mission_id = created.json()["id"]
    await client.post(f"/api/v1/me/missions/{mission_id}/take", headers=member_headers(member))
    locked = await client.put(
        f"/api/v1/admin/missions/{mission_id}",
        json={"title": "3 ta iqtibos", "metric": "QUOTES", "target": 1, "period_days": 7},
        headers=headers,
    )
    assert locked.status_code == 400  # members took it: the goal stays as it was
    archived = await client.put(
        f"/api/v1/admin/missions/{mission_id}",
        json={"title": "3 ta iqtibos", "metric": "QUOTES", "target": 3, "period_days": 7, "status": "ARCHIVED"},
        headers=headers,
    )
    assert archived.status_code == 200
    listing = (await client.get("/api/v1/admin/missions", headers=headers)).json()
    row = next(item for item in listing if item["id"] == mission_id)
    assert (row["status"], row["taken"], row["running"]) == ("ARCHIVED", 1, 1)
    assert await db.scalar(select(func.count()).select_from(Mission)) == len(missions.DEFAULTS) + 1

    await features.set_mode(db, actor_id=boss.id, code="shelf", new_mode=FeatureMode.OFF, announce=False)
    off = await client.get("/api/v1/me/shelf", headers=member_headers(member))
    assert off.status_code == 403 and off.json()["error"]["code"] == "FEATURE_OFF"


async def test_the_bot_diary_shelf_and_card(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids), first_name="Bobur")
    await db.commit()
    harness = BotHarness(member.telegram_id)
    await harness.send("/oqidim 20")
    assert harness.last_text() == texts.READ_NO_BOOK

    item = await reading_journal.add(
        db, member, title="Shum bola", pages_total=40, status=reading_journal.ShelfStatus.READING
    )
    await harness.send("/oqidim")
    assert "Shum bola" in harness.last_text() and "/oqidim 25" in harness.last_text()
    await harness.send("/oqidim 25 Juda kulgili")
    assert "+25 bet" in harness.last_text() and "25/40 bet (62%)" in harness.last_text()
    entry = await db.scalar(select(ReadingLog).where(ReadingLog.shelf_item_id == item.id))
    assert entry.note == "Juda kulgili"
    await harness.send("/oqidim 15")
    assert "Kitobni tugatdingizmi?" in harness.last_text()
    await harness.send("/oqidim 9999")
    assert "betdan ko'p" in harness.last_text()

    await harness.send("/javonim")
    assert "Shum bola — 40/40 bet (100%)" in harness.last_text() and "seriya: 1 kun" in harness.last_text()
    await harness.send("/kartam")
    photo = next(request for request in reversed(harness.session.requests) if isinstance(request, SendPhoto))
    assert "Kitobxonlik kartangiz" in photo.caption


async def test_oqidim_rejects_junk_page_counts_without_crashing(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids), first_name="Jahongir")
    await db.commit()
    await reading_journal.add(
        db, member, title="Mehrobdan chayon", pages_total=100, status=reading_journal.ShelfStatus.READING
    )
    harness = BotHarness(member.telegram_id)

    # "²" passes str.isdigit() but int() rejects it — this used to crash the handler.
    await harness.send("/oqidim ²")
    assert "Mehrobdan chayon" in harness.last_text() and "/oqidim 25" in harness.last_text()
    # Zero / negative / words also fall back to the help instead of logging a bogus entry.
    for junk in ("0", "-5", "ko'p", "25.5"):
        await harness.send(f"/oqidim {junk}")
        assert "/oqidim 25" in harness.last_text()
    assert await db.scalar(select(func.count()).select_from(ReadingLog).where(ReadingLog.user_id == member.id)) == 0


async def test_unread_own_books_do_not_finish_a_mission(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    headers = member_headers(member)
    books = next(
        m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["metric"] == "BOOKS_FINISHED"
    )
    await client.post(f"/api/v1/me/missions/{books['id']}/take", headers=headers)
    for title in ("Bir", "Ikki"):
        await client.post("/api/v1/me/shelf", json={"title": title, "status": "FINISHED"}, headers=headers)
    mine = next(m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["id"] == books["id"])
    assert (mine["status"], mine["progress"]) == ("ACTIVE", 0)  # nothing was read

    club = await create_book(db, title="Klub kitobi", status=BookStatus.ACTIVE)
    await db.commit()
    own = (
        await client.post("/api/v1/me/shelf", json={"title": "O'qilgan", "status": "READING"}, headers=headers)
    ).json()
    await client.post(f"/api/v1/me/shelf/{own['id']}/logs", json={"pages": 25}, headers=headers)
    await client.patch(f"/api/v1/me/shelf/{own['id']}", json={"status": "FINISHED"}, headers=headers)
    await client.post("/api/v1/me/shelf", json={"book_id": str(club.id), "status": "FINISHED"}, headers=headers)
    done = next(m for m in (await client.get("/api/v1/me/missions", headers=headers)).json() if m["id"] == books["id"])
    assert (done["status"], done["progress"]) == ("COMPLETED", 2)
