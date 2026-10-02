"""Bot redesign: short personal summaries per section, attendance by typing the code (opened
automatically at the event's time), and members' messages to the club's administrators."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    BookRead,
    EventRegistration,
    Notification,
    SupportMessage,
    SupportTicket,
    User,
)
from app.models.enums import (
    AttendanceSessionStatus,
    BookStatus,
    NotificationType,
    ReadingStatus,
    RegistrationStatus,
    ScoreCategory,
    SupportTicketStatus,
)
from app.security.permissions import Perm
from app.services import attendance as attendance_service
from app.services import support as support_service
from app.services.scoring import award_points
from app.workers.sender import _markup
from tests.bot_helpers import BotHarness
from tests.factories import create_book, create_event, create_test, create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


@pytest.fixture(autouse=True)
def _public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")


async def _admin(db: AsyncSession, *permissions: Perm, telegram_id: int | None = None) -> User:
    user = await create_user(db, **({"telegram_id": telegram_id} if telegram_id else {}))
    await db.commit()
    await grant_role(db, user, "ADMIN")
    await grant_permissions(db, user, *permissions)
    return user


# ---------------------------------------------------------------------------- section summaries


async def test_results_and_ranking_summaries(db: AsyncSession) -> None:
    me = await create_user(db, telegram_id=6001, first_name="Malika")
    leader = await create_user(db, first_name="Bekzod", last_name="Ergashev")
    await award_points(db, user_id=leader.id, amount=50, category=ScoreCategory.ATTENDANCE, idempotency_key="l1")
    await award_points(db, user_id=me.id, amount=30, category=ScoreCategory.ATTENDANCE, idempotency_key="m1")
    await award_points(db, user_id=me.id, amount=20, category=ScoreCategory.TEST, idempotency_key="m2")
    await award_points(db, user_id=me.id, amount=10, category=ScoreCategory.BOOK_COMPLETION, idempotency_key="m3")
    await db.commit()
    harness = BotHarness(6001)

    await harness.send(texts.BTN_RESULTS)
    text = harness.last_text()
    assert "Jami: <b>60 ball</b> — <b>1-o'rin</b>" in text
    assert "Shu oy: <b>60 ball</b>" in text
    assert "Davomat: 30 · 📝 Testlar: 20 · 📚 Kitoblar: 10" in text
    button = harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0]
    assert button.text == texts.BTN_MORE and button.web_app.url.endswith("/app/#/results")

    await harness.send(texts.BTN_RANKING)
    text = harness.last_text()
    assert text.index("🥇") < text.index("Malika") < text.index("🥈") < text.index("Bekzod")
    assert "Siz: <b>1-o'rin</b>, 60 ball" in text


async def test_books_events_tests_achievements_summaries(db: AsyncSession) -> None:
    me = await create_user(db, telegram_id=6002)
    book = await create_book(
        db, title="O'tkan kunlar", status=BookStatus.ACTIVE, deadline=date.today() + timedelta(days=5)
    )
    db.add(BookRead(book_id=book.id, user_id=me.id, status=ReadingStatus.READING))
    event = await create_event(db, title="Muhokama", starts_at=datetime.now(UTC) + timedelta(days=2))
    db.add(EventRegistration(event_id=event.id, user_id=me.id, status=RegistrationStatus.REGISTERED))
    await create_test(db, title="1-test", max_score=20)
    await db.commit()
    harness = BotHarness(6002)

    await harness.send(texts.BTN_BOOKS)
    assert "«O'tkan kunlar»" in harness.last_text() and "📖 Siz o'qiyapsiz" in harness.last_text()
    assert "kun qoldi" in harness.last_text()
    await harness.send(texts.BTN_EVENTS)
    assert "«Muhokama»" in harness.last_text() and texts.EVENTS_REGISTERED in harness.last_text()
    await harness.send(texts.BTN_TESTS)
    assert "«1-test»" in harness.last_text() and texts.TESTS_NOT_DONE in harness.last_text()
    await harness.send(texts.BTN_ACHIEVEMENTS)
    assert "Yutuqlarim" in harness.last_text()


async def test_old_keyboard_buttons_still_work_and_refresh_the_menu(db: AsyncSession) -> None:
    await create_user(db, telegram_id=6003, first_name="Aziza")
    await db.commit()
    harness = BotHarness(6003)
    await harness.send("👤 Profilim")
    messages = harness.session.sent_messages()
    assert "Aziza" in harness.session.last_caption()  # the passport picture
    assert messages[-1].text == texts.MENU_UPDATED
    assert isinstance(messages[-1].reply_markup, ReplyKeyboardMarkup)


# ---------------------------------------------------------------------------- attendance


async def test_attendance_opens_by_itself_and_code_can_be_typed(client: httpx.AsyncClient, db: AsyncSession) -> None:
    manager = await _admin(db, Perm.ATTENDANCE_VIEW, Perm.ATTENDANCE_MANAGE)
    member = await create_user(db, telegram_id=6004)
    event = await create_event(db, title="Kitob kechasi")  # attendance window is open now
    db.add(EventRegistration(event_id=event.id, user_id=member.id, status=RegistrationStatus.REGISTERED))
    await db.commit()
    event_id, member_id = event.id, member.id
    harness = BotHarness(6004)

    await harness.send(texts.BTN_ATTENDANCE)
    assert "Davomat ochiq" in harness.last_text() and "«Kitob kechasi»" in harness.last_text()
    scan = harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0]
    assert scan.text == texts.BTN_SCAN_QR and scan.web_app.url.endswith("/app/#/checkin?scan=1")
    # Nobody pressed «open»: the session was created automatically, registered members were told.
    sessions = list(await db.scalars(select(AttendanceSession).where(AttendanceSession.event_id == event_id)))
    assert len(sessions) == 1 and sessions[0].opened_by is None
    assert (
        await db.scalar(
            select(func.count()).select_from(Notification).where(Notification.type == NotificationType.ATTENDANCE_OPEN)
        )
        == 1
    )

    screen = await client.get(f"/api/v1/admin/events/{event_id}/attendance/token", headers=admin_headers(manager))
    code = screen.json()["code"]
    await harness.send("salom")
    assert harness.last_text() == texts.ATTENDANCE_CODE_HINT
    await harness.send(f"{code[:3].lower()} {code[3:].lower()}")  # lower case and a space are fine
    assert "Davomatingiz qayd etildi" in harness.last_text()
    assert await db.scalar(select(func.count()).select_from(AttendanceRecord)) == 1

    await harness.send(texts.BTN_ATTENDANCE)
    assert "qayd etilgansiz" in harness.last_text()
    open_now = await client.get("/api/v1/attendance/open", headers=member_headers(await db.get(User, member_id)))
    assert open_now.json()[0]["checked_in"] is True


async def test_manually_closed_attendance_is_not_reopened(db: AsyncSession) -> None:
    admin = await _admin(db, Perm.ATTENDANCE_MANAGE)
    event = await create_event(db)
    await db.commit()
    assert await attendance_service.open_scheduled_sessions(db) == 1
    assert await attendance_service.open_scheduled_sessions(db) == 0
    await attendance_service.close_session(db, actor_id=admin.id, event_id=event.id)
    assert await attendance_service.open_scheduled_sessions(db) == 0
    # Events outside their window are not opened.
    await create_event(db, starts_at=datetime.now(UTC) + timedelta(hours=3))
    await db.commit()
    assert await attendance_service.open_scheduled_sessions(db) == 0


async def test_finished_sessions_are_marked_closed(db: AsyncSession) -> None:
    event = await create_event(db)
    await db.commit()
    await attendance_service.open_scheduled_sessions(db)
    later = datetime.now(UTC) + timedelta(hours=1)
    await attendance_service.open_scheduled_sessions(db, now=later)
    status = await db.scalar(select(AttendanceSession.status).where(AttendanceSession.event_id == event.id))
    assert status == AttendanceSessionStatus.CLOSED


async def test_no_open_attendance_shows_the_next_event(db: AsyncSession) -> None:
    await create_user(db, telegram_id=6005)
    await create_event(db, title="Yanvar uchrashuvi", starts_at=datetime.now(UTC) + timedelta(days=3))
    await db.commit()
    harness = BotHarness(6005)
    await harness.send("/davomat")
    assert "Hozir ochiq davomat yo'q" in harness.last_text() and "«Yanvar uchrashuvi»" in harness.last_text()


# ---------------------------------------------------------------------------- messages to administrators


async def test_member_writes_admin_answers_in_the_bot(client: httpx.AsyncClient, db: AsyncSession) -> None:
    support_admin = await _admin(db, Perm.SUPPORT_MANAGE, telegram_id=6101)
    other_admin = await _admin(db, Perm.USER_VIEW, telegram_id=6102)
    member = await create_user(db, telegram_id=6103, first_name="Dilnoza", last_name="Karimova")
    await db.commit()
    support_admin_id, other_admin_id, member_id = support_admin.id, other_admin.id, member.id

    harness = BotHarness(6103)
    await harness.send(texts.BTN_HELP)
    assert harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0].callback_data == "sup:new"
    await harness.press("sup:new")
    assert harness.last_text() == texts.SUPPORT_ASK
    await harness.send("Test qachon ochiladi?")
    assert harness.last_text() == texts.SUPPORT_SENT

    ticket = await db.scalar(select(SupportTicket))
    ticket_id = ticket.id
    assert ticket.user_id == member_id and ticket.status == SupportTicketStatus.OPEN and ticket.unread_for_admin
    alerts = list(await db.scalars(select(Notification).where(Notification.type == NotificationType.SUPPORT)))
    assert [n.user_id for n in alerts] == [support_admin_id]  # not the admin without the permission
    assert "Dilnoza Karimova" in alerts[0].text and "Test qachon ochiladi?" in alerts[0].text
    assert alerts[0].payload["buttons"][0]["callback"] == f"sup:ans:{ticket.id}"
    assert other_admin_id not in {n.user_id for n in alerts}

    admin_bot = BotHarness(6101)
    await admin_bot.press(f"sup:ans:{ticket.id}")
    assert admin_bot.last_text() == texts.SUPPORT_REPLY_ASK
    await admin_bot.send("Ertaga soat 10:00 da.")
    assert admin_bot.last_text() == texts.SUPPORT_REPLY_SENT

    reply = await db.scalar(
        select(Notification).where(Notification.type == NotificationType.SUPPORT, Notification.user_id == member_id)
    )
    assert "Klub rahbariyatidan javob" in reply.text and "Ertaga soat 10:00 da." in reply.text
    admin = await db.get(User, support_admin_id)
    assert admin.first_name not in reply.text  # the admin stays anonymous
    db.expire_all()
    assert (await db.get(SupportTicket, ticket_id)).status == SupportTicketStatus.ANSWERED

    # Someone without the permission cannot answer from the bot.
    intruder = BotHarness(6102)
    await intruder.press(f"sup:ans:{ticket_id}")
    assert intruder.session.alerts()[-1] == texts.SUPPORT_NO_PERMISSION


async def test_admin_panel_conversations(client: httpx.AsyncClient, db: AsyncSession) -> None:
    manager = await _admin(db, Perm.SUPPORT_MANAGE)
    outsider = await _admin(db, Perm.USER_VIEW)
    member = await create_user(db, first_name="Jasur")
    await db.commit()
    ticket = await support_service.member_message(db, user=member, text="Sertifikat qachon beriladi?")
    await support_service.member_message(db, user=member, text=None, photo_file_id="AgACphoto")
    await db.commit()

    assert (await client.get("/api/v1/admin/support", headers=admin_headers(outsider))).status_code == 403
    summary = await client.get("/api/v1/admin/support/summary", headers=admin_headers(manager))
    assert summary.json() == {"unread": 1}
    listing = (await client.get("/api/v1/admin/support", headers=admin_headers(manager))).json()
    assert listing["total"] == 1 and listing["items"][0]["message_count"] == 2
    assert listing["items"][0]["member"]["first_name"] == "Jasur"

    detail = (await client.get(f"/api/v1/admin/support/{ticket.id}", headers=admin_headers(manager))).json()
    assert [m["text"] for m in detail["messages"]] == ["Sertifikat qachon beriladi?", "📷 (rasm)"]
    assert detail["messages"][1]["has_photo"] is True
    assert (await client.get("/api/v1/admin/support/summary", headers=admin_headers(manager))).json() == {"unread": 0}

    answer = await client.post(
        f"/api/v1/admin/support/{ticket.id}/reply", json={"text": "Oy oxirida."}, headers=admin_headers(manager)
    )
    assert answer.status_code == 200 and answer.json()["from_admin"] is True
    closed = await client.post(
        f"/api/v1/admin/support/{ticket.id}/status", json={"status": "CLOSED"}, headers=admin_headers(manager)
    )
    assert closed.status_code == 200
    # A new message after closing starts a new conversation.
    second = await support_service.member_message(db, user=member, text="Rahmat!")
    await db.commit()
    assert second.id != ticket.id


async def test_member_message_limits(db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    with pytest.raises(Exception, match="bo'sh"):
        await support_service.member_message(db, user=member, text="   ")
    for index in range(support_service.HOURLY_LIMIT):
        await support_service.member_message(db, user=member, text=f"Savol {index}")
    await db.commit()
    with pytest.raises(Exception, match="Juda ko'p"):
        await support_service.member_message(db, user=member, text="Yana bitta")
    assert await db.scalar(select(func.count()).select_from(SupportMessage)) == support_service.HOURLY_LIMIT


async def test_photo_messages_from_the_bot(db: AsyncSession) -> None:
    await create_user(db, telegram_id=6104)
    await db.commit()
    harness = BotHarness(6104)
    await harness.press("sup:new")
    await harness.send_photo("AgACfile123", caption="Xato chiqyapti")
    assert harness.last_text() == texts.SUPPORT_SENT
    message = await db.scalar(select(SupportMessage))
    assert message.photo_file_id == "AgACfile123" and message.text == "Xato chiqyapti"


def test_notification_buttons_cover_callbacks_and_admin_pages() -> None:
    markup = _markup(
        {
            "buttons": [
                {"text": "Javob", "callback": "sup:ans:1"},
                {"text": "Panel", "admin_route": "support/1"},
                {"text": "Ilova", "app_route": "results"},
            ]
        }
    )
    assert markup is not None
    first, second, third = (row[0] for row in markup.inline_keyboard)
    assert first.callback_data == "sup:ans:1"
    assert second.web_app.url == "https://kitobxon.example.org/admin/#/support/1"
    assert third.web_app.url == "https://kitobxon.example.org/app/#/results"
