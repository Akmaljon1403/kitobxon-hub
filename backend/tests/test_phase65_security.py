"""Round L14: the owners stay in control. Settings that move money or speak in the club's name are theirs only
and every change is reported to them; changes of admin rights are reported too; a computer sign-in is reported
to the admin with one tap to end every session; payment texts cannot be rewritten by others; and members get at
most a few club-wide messages a day, so the bot is not reported as spam."""

from __future__ import annotations

import itertools

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models import Notification, User
from app.models.enums import NotificationStatus, NotificationType
from app.security.permissions import Perm
from app.services import admins as admin_service
from app.services.auth import create_admin_login_link, exchange_admin_login_token
from app.services.notifications import enqueue_notification
from app.workers import sender as sender_module
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

sender_module.SEND_INTERVAL_SECONDS = 0
_ids = itertools.count(3_900_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _people(db: AsyncSession) -> dict[str, User]:
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    helper = await create_user(db, telegram_id=next(_ids), first_name="Dilnoza", last_name="Yordamchi")
    member = await create_user(db, telegram_id=next(_ids), first_name="Nodir")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    await grant_role(db, helper, "ADMIN")
    await grant_permissions(db, helper, Perm.SETTINGS_MANAGE, Perm.TEXTS_MANAGE)
    return {"boss": boss, "helper": helper, "member": member}


async def _alerts(db: AsyncSession, user_id: object) -> list[str]:
    rows = await db.scalars(
        select(Notification.text).where(Notification.user_id == user_id, Notification.text.like("%Xavfsizlik%"))
    )
    return list(rows)


async def test_money_settings_belong_to_the_owners(client: httpx.AsyncClient, db: AsyncSession) -> None:
    people = await _people(db)
    url = "/api/v1/admin/settings/payments.card_number"
    refused = await client.put(url, json={"value": "8600 1111 2222 3333"}, headers=admin_headers(people["helper"]))
    assert refused.status_code == 403 and "bosh admin" in refused.json()["error"]["message"]
    # the panel shows the lock before anyone tries
    listed = await client.get("/api/v1/admin/settings", headers=admin_headers(people["helper"]))
    flags = {row["key"]: row["owner_only"] for row in listed.json()}
    assert flags["payments.card_number"] is True and flags["reading.daily_page_limit"] is False
    # an ordinary setting is still the helper's to change
    fine = await client.put(
        "/api/v1/admin/settings/reading.daily_page_limit", json={"value": 400}, headers=admin_headers(people["helper"])
    )
    assert fine.status_code == 200

    done = await client.put(url, json={"value": "8600 1111 2222 3333"}, headers=admin_headers(people["boss"]))
    assert done.status_code == 200
    alert = (await _alerts(db, people["boss"].id))[0]
    assert "payments.card_number" in alert and "8600 •••• •••• 3333" in alert and "1111" not in alert

    # payment texts are the owners' too; other texts are fine, and the owners hear about them
    card_text = await client.put(
        "/api/v1/admin/texts/CARD_INSTRUCTIONS",
        json={"variants": ["Karta: {number} — {price}"]},
        headers=admin_headers(people["helper"]),
    )
    assert card_text.status_code == 403
    greeting = await client.put(
        "/api/v1/admin/texts/WELCOME_BACK",
        json={"variants": ["Salom, {first_name}!"]},
        headers=admin_headers(people["helper"]),
    )
    assert greeting.status_code == 200
    assert any("WELCOME_BACK" in text for text in await _alerts(db, people["boss"].id))


async def test_changes_of_rights_are_reported(db: AsyncSession) -> None:
    people = await _people(db)
    newcomer = await create_user(db, telegram_id=next(_ids), first_name="Yangi", last_name="Admin")
    await db.commit()
    await admin_service.appoint_admin(
        db, actor_id=people["boss"].id, user_id=newcomer.id, permissions=[Perm.SUPPORT_MANAGE.value]
    )
    await admin_service.set_admin_permissions(
        db, actor_id=people["boss"].id, user_id=newcomer.id, permissions=[Perm.PAYMENT_SUPPORT.value]
    )
    alerts = await _alerts(db, people["boss"].id)
    assert any("Yangi Admin" in text and "admin qilindi" in text for text in alerts)
    assert any("PAYMENT_SUPPORT" in text and "SUPPORT_MANAGE" in text for text in alerts)


async def test_a_computer_sign_in_is_reported(db: AsyncSession) -> None:
    people = await _people(db)
    raw, _ = await create_admin_login_link(db, people["helper"])
    await exchange_admin_login_token(db, raw)
    told = await db.scalar(
        select(Notification).where(Notification.user_id == people["helper"].id, Notification.text.like("%kompyuter%"))
    )
    assert told.payload["buttons"][0]["callback"] == "adm:logoutall"
    helper_id, version = people["helper"].id, people["helper"].token_version
    harness = BotHarness(people["helper"].telegram_id)
    await harness.press("adm:logoutall")
    fresh = await db.scalar(select(User).where(User.id == helper_id).execution_options(populate_existing=True))
    assert fresh.token_version == version + 1


async def test_members_are_not_flooded(db: AsyncSession) -> None:
    people = await _people(db)
    member = people["member"]
    for number in range(8):
        await enqueue_notification(
            db, user_id=member.id, type_=NotificationType.NEW_BOOK, text=f"Yangi kitob {number}", dedup_key=f"b{number}"
        )
    await enqueue_notification(
        db, user_id=member.id, type_=NotificationType.SUPPORT, text="Javob", dedup_key="answer", priority=1
    )
    await db.commit()
    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    report = await send_due_notifications(get_session_factory(), bot)
    assert report.sent == 7 and report.skipped == 2  # six club-wide messages a day, the answer always
    held = await db.scalar(select(Notification).where(Notification.status == NotificationStatus.SKIPPED).limit(1))
    assert held.last_error == "daily limit of mass messages"
