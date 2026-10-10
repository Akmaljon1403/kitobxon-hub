"""Phase 5: Telegram bot — registration conversation, menu, admin login link, webhook."""

from __future__ import annotations

import pytest
from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import AuditLog, BotFsmState, Faculty, SystemSetting, User, UserNotificationSettings, UserRole
from app.models.enums import UserStatus
from tests.bot_helpers import BotHarness
from tests.factories import create_user
from tests.helpers import grant_role


async def _faculty(db: AsyncSession, name: str = "Davolash ishi") -> Faculty:
    faculty = Faculty(name=name)
    db.add(faculty)
    await db.commit()
    return faculty


async def _register(harness: BotHarness, faculty: Faculty | None, phone: str = "998901234567") -> None:
    await harness.send("/start")
    await harness.send("akmaljon")
    await harness.send("Bahodirov")
    await harness.share_contact(phone)
    if faculty is not None:
        await harness.press(f"reg:fac:{faculty.id}")
    await harness.press("reg:course:3")
    await harness.send("301-a")
    await harness.press("reg:confirm")


async def _member(db: AsyncSession, telegram_id: int) -> User | None:
    db.expire_all()
    return await db.scalar(select(User).where(User.telegram_id == telegram_id))


# ---------------------------------------------------------------------------- registration


async def test_full_registration(db: AsyncSession) -> None:
    faculty = await _faculty(db)
    faculty_id = faculty.id
    harness = BotHarness(5001)

    await harness.send("/start")
    assert "Kitobxon Hub</b> — kitobxonlar klubimizning rasmiy boti" in harness.all_text()
    assert "1/6" in harness.last_text()

    await harness.send("akmaljon")
    assert "2/6" in harness.last_text()
    await harness.send("Bahodirov")
    assert "3/6" in harness.last_text()
    assert isinstance(harness.session.sent_messages()[-1].reply_markup, ReplyKeyboardMarkup)

    await harness.share_contact("998 90 123 45 67")
    assert "4/6" in harness.last_text()
    await harness.press(f"reg:fac:{faculty_id}")
    assert "5/6" in harness.last_text()
    await harness.press("reg:course:3")
    assert "6/6" in harness.last_text()
    await harness.send("301-a")
    summary = harness.last_text()
    assert "Akmaljon Bahodirov" in summary
    assert "Davolash ishi" in summary
    assert "301-A" in summary

    await harness.press("reg:confirm")
    welcome = next(m for m in harness.session.sent_messages() if "Tabriklaymiz" in m.text)
    assert isinstance(welcome.reply_markup, ReplyKeyboardMarkup)
    assert "Qisqa sayohat" in harness.all_text()  # then a short tour of the club

    user = await _member(db, 5001)
    assert user is not None
    assert (user.first_name, user.last_name) == ("Akmaljon", "Bahodirov")
    assert user.phone == "+998901234567"
    assert user.faculty_id == faculty_id
    assert (user.course, user.group_name) == (3, "301-A")
    assert user.status == UserStatus.ACTIVE
    assert user.telegram_username == "akmal_reader"
    assert await db.get(UserNotificationSettings, user.id) is not None
    assert await db.scalar(select(AuditLog.action).where(AuditLog.entity_id == str(user.id))) == "USER_REGISTER"
    # Conversation state is removed once registration is complete.
    assert await db.scalar(select(func.count()).select_from(BotFsmState)) == 0


async def test_registration_without_faculties_skips_that_step(db: AsyncSession) -> None:
    harness = BotHarness(5002)
    await harness.send("/start")
    assert "1/5" in harness.last_text()
    await harness.send("Dilnoza")
    await harness.send("Karimova")
    await harness.share_contact("+998911112233")
    assert "4/5" in harness.last_text()  # course question comes right after the phone
    await harness.press("reg:course:1")
    await harness.send("101")
    await harness.press("reg:confirm")
    user = await _member(db, 5002)
    assert user is not None and user.faculty_id is None


async def test_registration_survives_server_restart(db: AsyncSession) -> None:
    harness = BotHarness(5003)
    await harness.send("/start")
    await harness.send("Jasur")
    harness.restart_server()
    await harness.send("Toshmatov")
    assert "3/5" in harness.last_text()
    harness.restart_server()
    await harness.share_contact("+998935554433")
    await harness.press("reg:course:2")
    await harness.send("202")
    await harness.press("reg:confirm")
    user = await _member(db, 5003)
    assert user is not None and user.first_name == "Jasur"


async def test_contact_of_another_person_is_rejected(db: AsyncSession) -> None:
    harness = BotHarness(5004)
    await harness.send("/start")
    await harness.send("Ali")
    await harness.send("Valiyev")
    await harness.share_contact("+998901111111", owner_id=999)
    assert harness.last_text() == texts.PHONE_NOT_YOURS
    state = await db.scalar(select(BotFsmState.state))
    assert state == "Registration:phone"


async def test_typed_phone_number_is_not_accepted(db: AsyncSession) -> None:
    harness = BotHarness(5005)
    await harness.send("/start")
    await harness.send("Ali")
    await harness.send("Valiyev")
    await harness.send("+998901234567")
    assert harness.last_text() == texts.ASK_PHONE_USE_BUTTON


@pytest.mark.parametrize("bad_name", ["A", "Ali123", "<b>Ali</b>", "x" * 70])
async def test_invalid_names_are_rejected(db: AsyncSession, bad_name: str) -> None:
    harness = BotHarness(5006)
    await harness.send("/start")
    await harness.send(bad_name)
    assert "faqat harflardan" in harness.last_text()
    assert await db.scalar(select(BotFsmState.state)) == "Registration:first_name"


async def test_phone_used_by_another_member_is_rejected(db: AsyncSession) -> None:
    await create_user(db, phone="+998907777777")
    await db.commit()
    harness = BotHarness(5007)
    await harness.send("/start")
    await harness.send("Ali")
    await harness.send("Valiyev")
    await harness.share_contact("+998907777777")
    assert "boshqa hisobga bog'langan" in harness.last_text()


async def test_cancel_and_help_during_registration(db: AsyncSession) -> None:
    harness = BotHarness(5008)
    await harness.send("/start")
    await harness.send("/help")
    assert "Yordam" in harness.last_text() and texts.NOT_REGISTERED in harness.last_text()
    await harness.send("/cancel")
    assert harness.last_text() == texts.REGISTRATION_CANCELLED
    assert await db.scalar(select(func.count()).select_from(BotFsmState)) == 0


async def test_registration_requiring_approval(db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "registration.require_approval")
    setting.value = True
    await db.commit()
    harness = BotHarness(5009)
    await _register(harness, None)
    assert "Arizangiz qabul qilindi" in harness.last_text()
    user = await _member(db, 5009)
    assert user is not None and user.status == UserStatus.PENDING

    await harness.send("/start")
    assert harness.last_text() == texts.ACCOUNT_PENDING


async def test_owner_becomes_super_admin_on_registration(db: AsyncSession) -> None:
    setting = await db.get(SystemSetting, "registration.require_approval")
    setting.value = True
    await db.commit()
    harness = BotHarness(900000001)  # listed in SUPER_ADMIN_TELEGRAM_IDS (tests/conftest.py)
    await _register(harness, None, phone="+998900000001")
    user = await _member(db, 900000001)
    assert user is not None and user.status == UserStatus.ACTIVE
    assert await db.scalar(select(func.count()).select_from(UserRole).where(UserRole.user_id == user.id)) == 1


async def test_old_registration_button_after_completion(db: AsyncSession) -> None:
    harness = BotHarness(5010)
    await _register(harness, None)
    harness.session.clear()
    await harness.press("reg:confirm")
    assert harness.session.alerts() == [texts.REGISTRATION_EXPIRED]
    assert await db.scalar(select(func.count()).select_from(User)) == 1


# ---------------------------------------------------------------------------- registered members


async def test_registered_member_gets_main_menu(db: AsyncSession) -> None:
    await create_user(db, telegram_id=5100, first_name="Malika")
    await db.commit()
    harness = BotHarness(5100)
    await harness.send("/start")
    assert "Assalomu alaykum, Malika" in harness.last_text()
    keyboard = harness.session.sent_messages()[-1].reply_markup
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    labels = {button.text for row in keyboard.keyboard for button in row}
    assert labels == {
        texts.BTN_BOOKS,
        texts.BTN_EVENTS,
        texts.BTN_ATTENDANCE,
        texts.BTN_TESTS,
        texts.BTN_RESULTS,
        texts.BTN_RANKING,
        texts.BTN_PASSPORT,
        texts.BTN_ACHIEVEMENTS,
        texts.BTN_SETTINGS,
        texts.BTN_HELP,
    }  # no «Boshqaruv» for ordinary members


async def test_profile_and_section_buttons(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    await create_user(db, telegram_id=5101, first_name="Malika", group_name="402")
    await db.commit()
    harness = BotHarness(5101)

    await harness.send(texts.BTN_PASSPORT)
    caption = harness.session.last_caption()
    assert "Malika" in caption and "402" in caption and "KH-" in caption

    await harness.send(texts.BTN_EVENTS)
    assert harness.last_text() == texts.EVENTS_NONE
    markup = harness.session.sent_messages()[-1].reply_markup
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].web_app.url == "https://kitobxon.example.org/app/#/events"


async def test_notification_toggle(db: AsyncSession) -> None:
    user = await create_user(db, telegram_id=5102)
    user_id = user.id
    db.add(UserNotificationSettings(user_id=user_id))
    await db.commit()
    harness = BotHarness(5102)
    await harness.send(texts.BTN_SETTINGS)
    await harness.press("ntf:quote_of_day")
    db.expire_all()
    settings = await db.get(UserNotificationSettings, user_id)
    assert settings.quote_of_day is False
    await harness.press("ntf:quote_of_day")
    db.expire_all()
    assert (await db.get(UserNotificationSettings, user_id)).quote_of_day is True


async def test_blocked_member_cannot_use_menu(db: AsyncSession) -> None:
    await create_user(db, telegram_id=5103, status=UserStatus.BLOCKED)
    await db.commit()
    harness = BotHarness(5103)
    await harness.send(texts.BTN_PASSPORT)
    assert harness.last_text() == texts.ACCOUNT_BLOCKED


async def test_unregistered_user_is_told_to_register(db: AsyncSession) -> None:
    harness = BotHarness(5104)
    await harness.send("salom")
    assert harness.last_text() == texts.NOT_REGISTERED


async def test_myid(db: AsyncSession) -> None:
    harness = BotHarness(5105)
    await harness.send("/myid")
    assert "5105" in harness.last_text()


# ---------------------------------------------------------------------------- admin login


async def test_admin_section_opens_panel_inside_telegram(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    admin = await create_user(db, telegram_id=5200)
    await db.commit()
    await grant_role(db, admin, "ADMIN")

    harness = BotHarness(5200)
    await harness.send("/start")
    keyboard = harness.session.sent_messages()[-1].reply_markup
    assert texts.BTN_ADMIN in {button.text for row in keyboard.keyboard for button in row}

    await harness.send(texts.BTN_ADMIN)
    message = harness.session.sent_messages()[-1]
    assert "Boshqaruv" in message.text
    panel = message.reply_markup.inline_keyboard[0][0]
    assert panel.web_app.url == "https://kitobxon.example.org/admin/#/"

    # A one-time link for a computer, on request.
    await harness.press("adm:link")
    button = harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0]
    assert button.url.startswith("https://kitobxon.example.org/admin/#/login?token=")


async def test_owner_gets_admin_rights_from_the_bot(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    """Registered first, listed in SUPER_ADMIN_TELEGRAM_IDS later: the bot grants the role itself."""
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    await create_user(db, telegram_id=900000001)
    await db.commit()
    harness = BotHarness(900000001)
    await harness.send("/admin")
    assert "Boshqaruv" in harness.last_text()
    owner = await _member(db, 900000001)
    assert await db.scalar(select(func.count()).select_from(UserRole).where(UserRole.user_id == owner.id)) == 1


async def test_admin_command_refused_for_members(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    await create_user(db, telegram_id=5201)
    await db.commit()
    harness = BotHarness(5201)
    await harness.send("/admin")
    assert harness.last_text() == texts.ADMIN_ONLY


# ---------------------------------------------------------------------------- webhook


async def test_webhook_requires_secret(client, db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.bot import setup as bot_setup

    harness = BotHarness(5300)
    monkeypatch.setattr(bot_setup, "_runtime", bot_setup.BotRuntime(harness.bot, harness.dispatcher))
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1_700_000_000,
            "chat": {"id": 5300, "type": "private"},
            "from": {"id": 5300, "is_bot": False, "first_name": "Akmal"},
            "text": "/start",
        },
    }
    rejected = await client.post("/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "x"})
    assert rejected.status_code == 401
    assert harness.session.sent_messages() == []

    accepted = await client.post(
        "/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": bot_setup.webhook_secret()}
    )
    assert accepted.status_code == 200
    assert any(isinstance(r, SendMessage) and "Ro'yxatdan o'tish" in r.text for r in harness.session.requests)


# ---------------------------------------------------------------------------- faculties (admin API)


async def test_faculty_management(client, db: AsyncSession) -> None:
    from app.security.permissions import Perm
    from tests.helpers import admin_headers, grant_permissions

    plain_admin = await create_user(db)
    manager = await create_user(db)
    await db.commit()
    await grant_role(db, plain_admin, "ADMIN")
    await grant_role(db, manager, "ADMIN")
    await grant_permissions(db, manager, Perm.SETTINGS_MANAGE)

    denied = await client.post(
        "/api/v1/admin/faculties", json={"name": "Pediatriya"}, headers=admin_headers(plain_admin)
    )
    assert denied.status_code == 403

    created = await client.post("/api/v1/admin/faculties", json={"name": "Pediatriya"}, headers=admin_headers(manager))
    assert created.status_code == 201
    duplicate = await client.post(
        "/api/v1/admin/faculties", json={"name": "Pediatriya"}, headers=admin_headers(manager)
    )
    assert duplicate.status_code == 409

    faculty_id = created.json()["id"]
    hidden = await client.patch(
        f"/api/v1/admin/faculties/{faculty_id}", json={"is_active": False}, headers=admin_headers(manager)
    )
    assert hidden.json()["is_active"] is False

    # Inactive faculties are not offered during registration.
    harness = BotHarness(5400)
    await harness.send("/start")
    assert "1/5" in harness.last_text()
