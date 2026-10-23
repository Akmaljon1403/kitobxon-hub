"""Round K1: «💬 A'zolar fikrlari» — members' quotes, thoughts, impressions and testimonials: the common
feed (after an admin approves), the member's quote box, likes, six card designs, and the club using them
anywhere: the channel, a message to members, the quote of the day, the admin's own chat."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendPhoto
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import (
    AttendanceRecord,
    BookQuote,
    ChannelPost,
    Contribution,
    EventFeedback,
    Faculty,
    Notification,
    SavedQuote,
    ScoreTransaction,
)
from app.models.enums import (
    AttendanceMethod,
    AttendanceStatus,
    BookStatus,
    ContributionKind,
    ContributionStatus,
    QuoteStatus,
    ShelfStatus,
)
from app.security.permissions import Perm
from app.services import community, membership, reading_journal, share_cards
from app.services.settings import update_setting
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_book, create_event, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

_ids = itertools.count(2_900_000)


async def _club(db: AsyncSession) -> dict:
    faculty = Faculty(name="Pediatriya", short_name="PED")
    db.add(faculty)
    await db.flush()
    author = await create_user(
        db, telegram_id=next(_ids), first_name="Madina", last_name="Karimova", faculty_id=faculty.id
    )
    reader = await create_user(db, telegram_id=next(_ids))
    moderator = await create_user(db, telegram_id=next(_ids))
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, moderator, "ADMIN")
    await grant_permissions(db, moderator, Perm.COMMUNITY_MANAGE)
    await grant_role(db, boss, "SUPER_ADMIN")
    return {"author": author, "reader": reader, "moderator": moderator, "boss": boss}


async def test_members_write_and_the_club_approves(client: httpx.AsyncClient, db: AsyncSession) -> None:
    club = await _club(db)
    author, reader, moderator = club["author"], club["reader"], club["moderator"]
    headers = member_headers(author)

    options = (await client.get("/api/v1/community/options", headers=headers)).json()
    assert {style["code"] for style in options["styles"]} == set(share_cards.STYLES)
    assert [kind["code"] for kind in options["kinds"]] == ["QUOTE", "THOUGHT", "BOOK", "EVENT", "CLUB"]

    sent = await client.post(
        "/api/v1/community",
        json={
            "kind": "QUOTE",
            "text": "Ilm — aql chirog'idir.",
            "source": "Alisher Navoiy — Mahbub ul-qulub",
            "style": "paper",
        },
        headers=headers,
    )
    assert sent.status_code == 201, sent.text
    item = sent.json()
    assert item["status"] == "PENDING" and item["style"] == "paper"
    # also kept in the member's own quote box, with its source
    kept = await db.scalar(select(SavedQuote).where(SavedQuote.user_id == author.id))
    assert kept.text == "Ilm — aql chirog'idir." and kept.source == "Alisher Navoiy — Mahbub ul-qulub"
    # the moderators are told, with buttons to decide in the chat
    alert = await db.scalar(
        select(Notification).where(Notification.dedup_key == f"contribution-new:{item['id']}:{moderator.id}")
    )
    assert alert is not None and "cm:ok:" in str(alert.payload)

    # nobody sees it before an approval; the author sees it in their own list
    assert (await client.get("/api/v1/community", headers=member_headers(reader))).json() == []
    mine = (await client.get("/api/v1/community/mine", headers=headers)).json()
    assert mine[0]["status"] == "PENDING"
    hidden = await client.get(f"/api/v1/community/{item['id']}/card.png", headers=member_headers(reader))
    assert hidden.status_code == 404

    # the same text again, too short, and the daily limit
    again = await client.post(
        "/api/v1/community", json={"kind": "QUOTE", "text": "Ilm — aql chirog'idir."}, headers=headers
    )
    assert again.status_code == 409
    short = await client.post("/api/v1/community", json={"kind": "THOUGHT", "text": "Zo'r"}, headers=headers)
    assert short.status_code == 422
    await update_setting(db, key="community.daily_limit", value=1, actor_id=None)
    limited = await client.post(
        "/api/v1/community", json={"kind": "CLUB", "text": "Klub menga kitob sevgisini berdi."}, headers=headers
    )
    assert limited.status_code == 409 and "ertaga" in limited.json()["error"]["message"]

    # a plain admin without the right cannot moderate
    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, plain, "ADMIN")
    assert (await client.get("/api/v1/admin/community", headers=admin_headers(plain))).status_code == 403

    listing = (await client.get("/api/v1/admin/community?status=PENDING", headers=admin_headers(moderator))).json()
    assert listing["counts"]["PENDING"] == 1 and listing["items"][0]["member"] == "Karimova Madina"
    approved = await client.post(
        f"/api/v1/admin/community/{item['id']}/moderate", json={"action": "approve"}, headers=admin_headers(moderator)
    )
    assert approved.json()["status"] == "APPROVED"
    points = await db.scalar(
        select(func.sum(ScoreTransaction.amount)).where(
            ScoreTransaction.idempotency_key == f"contribution:{item['id']}"
        )
    )
    assert points == 2
    told = await db.scalar(select(Notification).where(Notification.dedup_key == f"contribution-accepted:{item['id']}"))
    assert "(+2 ball)" in told.text

    feed = (await client.get("/api/v1/community", headers=member_headers(reader))).json()
    assert feed[0]["author"] == "Madina K., Pediatriya" and feed[0]["liked"] is False
    liked = (await client.post(f"/api/v1/community/{item['id']}/like", headers=member_headers(reader))).json()
    assert liked == {"liked": True, "likes": 1}
    unliked = (await client.post(f"/api/v1/community/{item['id']}/like", headers=member_headers(reader))).json()
    assert unliked == {"liked": False, "likes": 0}
    card = await client.get(f"/api/v1/community/{item['id']}/card.png?style=night", headers=member_headers(reader))
    assert card.status_code == 200 and card.content.startswith(b"\x89PNG")

    # featured: extra points once and a congratulation
    await client.post(
        f"/api/v1/admin/community/{item['id']}/moderate", json={"action": "feature"}, headers=admin_headers(moderator)
    )
    await client.post(
        f"/api/v1/admin/community/{item['id']}/moderate", json={"action": "unfeature"}, headers=admin_headers(moderator)
    )
    await client.post(
        f"/api/v1/admin/community/{item['id']}/moderate", json={"action": "feature"}, headers=admin_headers(moderator)
    )
    stars = await db.scalar(
        select(func.count())
        .select_from(ScoreTransaction)
        .where(ScoreTransaction.idempotency_key == f"contribution-star:{item['id']}")
    )
    assert stars == 1

    # a typo is fixed by an admin; the author can take the text back (their box keeps it)
    fixed = await client.patch(
        f"/api/v1/admin/community/{item['id']}",
        json={"text": "Ilm — aql chirog'idir!", "source": "Alisher Navoiy"},
        headers=admin_headers(moderator),
    )
    assert fixed.json()["text"] == "Ilm — aql chirog'idir!"
    gone = await client.delete(f"/api/v1/community/{item['id']}", headers=headers)
    assert gone.status_code == 204
    assert await db.scalar(select(func.count()).select_from(SavedQuote).where(SavedQuote.user_id == author.id)) == 1


async def test_the_club_uses_a_text_anywhere(client: httpx.AsyncClient, db: AsyncSession, monkeypatch) -> None:
    club = await _club(db)
    author, boss, moderator = club["author"], club["boss"], club["moderator"]
    item = await community.submit(
        db, author, kind=ContributionKind.CLUB, text="Bu klubda kitobni sevib qoldim va do'stlar orttirdim."
    )
    assert item.saved_quote_id is None  # testimonials do not go to the quote box

    # the channel needs a NOTIFICATION_SEND right too
    denied = await client.post(f"/api/v1/admin/community/{item.id}/channel", json={}, headers=admin_headers(moderator))
    assert denied.status_code == 403
    await update_setting(db, key="channel.chat_id", value="@club_channel", actor_id=None)
    posted = await client.post(
        f"/api/v1/admin/community/{item.id}/channel",
        json={"style": "emerald", "caption": "🌟 A'zolarimiz klub haqida"},
        headers=admin_headers(boss),
    )
    assert posted.status_code == 200, posted.text
    post = await db.get(ChannelPost, posted.json()["post_id"])
    assert post.photo_key and post.text.startswith("🌟 A'zolarimiz klub haqida")
    await db.refresh(item)
    assert item.status == ContributionStatus.APPROVED and item.uses[0]["where"] == "channel"
    assert item.uses[0]["style"] == "emerald"

    count = await client.post(
        f"/api/v1/admin/community/{item.id}/members", json={"dry_run": True}, headers=admin_headers(boss)
    )
    assert count.json()["recipients"] >= 4
    sent = await client.post(
        f"/api/v1/admin/community/{item.id}/members", json={"style": "sunrise"}, headers=admin_headers(boss)
    )
    recipients = sent.json()["recipients"]
    messages = list(await db.scalars(select(Notification).where(Notification.dedup_key.like("contribution-send:%"))))
    assert len(messages) == recipients and messages[0].payload["photo_key"].startswith("community/")

    day = await client.post(
        f"/api/v1/admin/community/{item.id}/quote-of-day", json={}, headers=admin_headers(moderator)
    )
    quote = await db.get(BookQuote, day.json()["quote_id"])
    assert quote.status == QuoteStatus.SCHEDULED and quote.scheduled_date > datetime.now(UTC).date()
    assert quote.author == "Madina K."  # a testimonial is signed by its author
    again = await client.post(
        f"/api/v1/admin/community/{item.id}/quote-of-day",
        json={"day": quote.scheduled_date.isoformat()},
        headers=admin_headers(moderator),
    )
    assert again.status_code == 409

    session = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.runtime_bot", lambda: bot)
    mine = await client.post(
        f"/api/v1/admin/community/{item.id}/me", json={"style": "minimal"}, headers=admin_headers(moderator)
    )
    assert mine.json() == {"sent": True}
    photo = next(request for request in session.requests if isinstance(request, SendPhoto))
    assert photo.chat_id == moderator.telegram_id and "Madina K., Pediatriya" in photo.caption

    listing = (await client.get("/api/v1/admin/community?status=APPROVED", headers=admin_headers(moderator))).json()
    assert [use["title"] for use in listing["items"][0]["uses"]] == [
        "📣 Kanalda",
        "📢 A'zolarga yuborilgan",
        "📜 Kun iqtibosi",
        "📨 Adminga yuborilgan",
    ]
    download = await client.get(
        f"/api/v1/admin/community/{item.id}/card.png?style=paper&download=true", headers=admin_headers(moderator)
    )
    assert download.status_code == 200 and "attachment" in download.headers["content-disposition"]


async def test_the_bot_the_shelf_and_events_invite_texts(db: AsyncSession) -> None:
    club = await _club(db)
    author, moderator = club["author"], club["moderator"]

    harness = BotHarness(author.telegram_id)
    await harness.send("/fikr")
    assert "A'zolar fikrlari" in harness.last_text()
    await harness.press("cmw:QUOTE")
    await harness.send("Kitob o'qigan odam ming umr ko'radi.")
    assert harness.last_text() == texts.COMMUNITY_ASK_SOURCE
    await harness.press("cmw:skip")
    assert "Yuborildi" in harness.last_text() and "Iqtiboslar sandig'i" in harness.last_text()
    item = await db.scalar(select(Contribution).where(Contribution.user_id == author.id))
    assert item.kind == ContributionKind.QUOTE and item.source is None

    admin = BotHarness(moderator.telegram_id)
    await admin.press(f"cm:star:{item.id.hex}")
    await db.refresh(item)
    assert item.status == ContributionStatus.APPROVED and item.featured is True
    reader = BotHarness(club["reader"].telegram_id)
    await reader.press(f"cm:ok:{item.id.hex}")
    assert texts.COMMUNITY_NO_RIGHT in reader.session.alerts()
    await harness.press(f"cm:card:{item.id.hex}")
    assert any(isinstance(request, SendPhoto) for request in harness.session.requests)

    # a finished book: «write a line you liked»
    book = await create_book(db, title="Shum bola", status=BookStatus.ACTIVE)
    shelf = await reading_journal.add(db, author, book_id=book.id, status=ShelfStatus.READING)
    await reading_journal.update(db, author, shelf.id, status=ShelfStatus.FINISHED)
    ask = await db.scalar(select(Notification).where(Notification.dedup_key == f"ask-book:{author.id}:{book.id}"))
    assert "Shum bola" in ask.text
    # Q11: the member is led to rate the book + answer the 3 questions (reading diary).
    assert f"shelf/{shelf.id}" in str(ask.payload)
    # The optional club-impression invite stays, but the standalone book-quote nudge is gone (Q2).
    assert f"community/new?kind=BOOK&book={book.id}" in str(ask.payload)
    assert "kind=QUOTE" not in str(ask.payload)

    # an event comment with 5 ⭐: «share it with everybody?»
    event = await create_event(
        db, starts_at=datetime.now(UTC) - timedelta(hours=3), ends_at=datetime.now(UTC) - timedelta(hours=1)
    )
    db.add(
        AttendanceRecord(
            event_id=event.id, user_id=author.id, method=AttendanceMethod.CODE, status=AttendanceStatus.VERIFIED
        )
    )
    db.add(EventFeedback(event_id=event.id, user_id=author.id, rating=5))
    await db.commit()
    await harness.press(f"fbc:{event.id.hex}")
    await harness.send("Davra suhbati juda qiziqarli o'tdi, rahmat!")
    assert texts.COMMUNITY_EVENT_OFFER in harness.all_text()
    await harness.press(f"cmfb:{event.id.hex}")
    shared = await db.scalar(select(Contribution).where(Contribution.kind == ContributionKind.EVENT))
    assert shared.event_id == event.id and shared.text.startswith("Davra suhbati") and shared.source.startswith("«")

    # the member's data is erased: their texts go too
    await membership.erase(db, author, actor_id=None, reason="test")
    await db.commit()
    assert await db.scalar(select(func.count()).select_from(Contribution).where(Contribution.user_id == author.id)) == 0


async def test_published_at_once_and_shared_from_the_box(client: httpx.AsyncClient, db: AsyncSession) -> None:
    club = await _club(db)
    author = club["author"]
    await update_setting(db, key="community.auto_publish", value=True, actor_id=None)
    headers = member_headers(author)
    saved = await client.post(
        "/api/v1/me/quotes",
        json={"text": "Sabr — kitobxonning eng yaxshi do'sti.", "source": "O'z fikrim"},
        headers=headers,
    )
    shared = await client.post(
        "/api/v1/community/from-box", json={"saved_quote_id": saved.json()["id"]}, headers=headers
    )
    assert shared.status_code == 201 and shared.json()["status"] == "APPROVED" and shared.json()["kind"] == "THOUGHT"
    twice = await client.post(
        "/api/v1/community/from-box", json={"saved_quote_id": saved.json()["id"]}, headers=headers
    )
    assert twice.json()["id"] == shared.json()["id"]
    assert await db.scalar(select(func.count()).select_from(SavedQuote).where(SavedQuote.user_id == author.id)) == 1
    feed = (await client.get("/api/v1/community?kind=THOUGHT", headers=member_headers(club["reader"]))).json()
    assert len(feed) == 1

    # a member writes about an event only after coming to it
    event = await create_event(db)
    await db.commit()
    refused = await client.post(
        "/api/v1/community",
        json={"kind": "EVENT", "text": "Juda zo'r tadbir bo'ldi!", "event_id": str(event.id)},
        headers=headers,
    )
    assert refused.status_code == 409
