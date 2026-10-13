"""Round L9–L11: «📝 Matnlar» — the owner rewrites any bot message, member notification or channel phrase in
the Admin Panel (several variants, sent in turn), checked before saving, logged, and reset at any time;
built-in variants keep frequent messages from repeating."""

from __future__ import annotations

import itertools

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import text_store, texts
from app.bot.text_variants import VARIANTS
from app.models import AuditLog
from app.models.enums import NotificationType
from app.security.permissions import Perm
from app.services import channel, texts_admin
from app.services.notifications import render
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role

_ids = itertools.count(3_700_000)
URL = "/api/v1/admin/texts"


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _boss(db: AsyncSession):
    boss = await create_user(db, telegram_id=next(_ids), first_name="Akmal", last_name="Bosh")
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    return boss


async def test_the_catalogue_lists_every_kind_of_text(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, plain, "ADMIN")
    assert (await client.get(URL, headers=admin_headers(plain))).status_code == 403
    await grant_permissions(db, plain, Perm.TEXTS_MANAGE)
    listing = (await client.get(URL, headers=admin_headers(plain))).json()
    items = {item["key"]: item for item in listing["items"]}
    assert listing["rotation"] is True

    welcome = items["WELCOME_BACK"]
    assert welcome["group"] == "👋 Salomlashish va hisob holati" and welcome["allowed"] == ["first_name"]
    assert len(welcome["builtin"]) == 4  # five ways to greet in all
    assert not any(key.startswith("BTN_") for key in items)  # the menu buttons stay as they are
    reminder = items["notify.EVENT_REMINDER"]
    assert reminder["kind"] == "notify" and reminder["active"] is True
    assert set(reminder["allowed"]) == {"event_title", "starts_at", "location"}
    nudges = items["channel.nudges_end"]
    assert nudges["kind"] == "channel" and len(nudges["defaults"]) >= 6 and "days" in nudges["allowed"]
    assert boss  # the super admin may of course do the same


async def test_the_owner_rewrites_the_greeting(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids), first_name="Madina")
    await db.commit()
    headers = admin_headers(boss)

    # a wrong placeholder, a broken tag or a stray brace is refused before it reaches members
    unknown = await client.put(f"{URL}/WELCOME_BACK", json={"variants": ["Salom, {ism}!"]}, headers=headers)
    assert unknown.status_code == 400 and "{ism}" in unknown.json()["error"]["message"]
    broken = await client.put(f"{URL}/WELCOME_BACK", json={"variants": ["<b>Salom, {first_name}!"]}, headers=headers)
    assert broken.status_code == 400 and "<b>" in broken.json()["error"]["message"]
    brace = await client.put(f"{URL}/MENU_UPDATED", json={"variants": ["Menyu {yangi}"]}, headers=headers)
    assert brace.status_code == 400
    check = await client.post(
        f"{URL}/WELCOME_BACK/check", json={"text": "Salom, <i>{first_name}</i>!"}, headers=headers
    )
    assert check.json() == {"ok": True, "problems": []}

    saved = await client.put(
        f"{URL}/WELCOME_BACK",
        json={"variants": ["🌟 Xush kelibsiz, {first_name}!", "📚 Salom, {first_name}! Bugun nima o'qiymiz?"]},
        headers=headers,
    )
    assert saved.status_code == 200
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "TEXT_EDIT"))
    assert audit.actor_user_id == boss.id and audit.after["key"] == "WELCOME_BACK"

    harness = BotHarness(member.telegram_id)
    await harness.send("/start")
    assert harness.last_text() in {"🌟 Xush kelibsiz, Madina!", "📚 Salom, Madina! Bugun nima o'qiymiz?"}

    # the two variants are sent in turn, never the same one twice
    text_store.force_rotation = True
    said = [texts.WELCOME_BACK for _ in range(6)]
    assert all(first != second for first, second in itertools.pairwise(said))

    # back to the built-in wording
    await client.delete(f"{URL}/WELCOME_BACK", headers=headers)
    text_store.force_rotation = False
    assert texts.WELCOME_BACK.startswith("Assalomu alaykum, {first_name}!")


async def test_built_in_variants_rotate_and_can_be_switched_off(db: AsyncSession) -> None:
    boss = await _boss(db)
    text_store.force_rotation = True
    seen = {texts.SUPPORT_SENT for _ in range(60)}
    assert len(seen) >= 4 and seen <= {texts_admin._find("SUPPORT_SENT")["default"], *VARIANTS["SUPPORT_SENT"]}
    # every built-in variant keeps the placeholders of its original
    for key, variants in VARIANTS.items():
        item = texts_admin._find(key)
        for variant in variants:
            assert not texts_admin.check(variant, set(item["allowed"]), braces=item["braces"]), (key, variant)

    from app.services.settings import update_setting

    await update_setting(db, key="texts.rotate", value=False, actor_id=boss.id)
    await text_store.refresh(db, force=True)
    text_store.force_rotation = None  # as in production: the owner's switch decides
    assert not text_store._rotating()
    assert {texts.SUPPORT_SENT for _ in range(10)} == {texts_admin._find("SUPPORT_SENT")["default"]}


async def test_notifications_and_channel_phrases(client: httpx.AsyncClient, db: AsyncSession) -> None:
    boss = await _boss(db)
    headers = admin_headers(boss)
    await client.put(
        f"{URL}/notify.EVENT_REMINDER",
        json={"variants": ["⏰ {event_title} — {starts_at}! Kutamiz."], "rotate": False},
        headers=headers,
    )
    text = await render(
        db, NotificationType.EVENT_REMINDER, event_title="Davra suhbati", starts_at="15:00", location="—"
    )
    assert text == "⏰ Davra suhbati — 15:00! Kutamiz."

    off = await client.put(f"{URL}/notify.RANKING_UPDATE/active", json={"active": False}, headers=headers)
    assert off.status_code == 200
    assert await render(db, NotificationType.RANKING_UPDATE, rank=3, total=100) is None

    await client.put(
        f"{URL}/channel.invites",
        json={"variants": ["📚 Bizda {members} kitobxon! Qo'shiling 👇"]},
        headers=headers,
    )
    assert channel.phrases("channel.invites") == ("📚 Bizda {members} kitobxon! Qo'shiling 👇",)
    wrong = await client.put(f"{URL}/channel.invites", json={"variants": ["{kitob} bor"]}, headers=headers)
    assert wrong.status_code == 400


async def test_preview_export_and_import(
    client: httpx.AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    boss = await _boss(db)
    headers = admin_headers(boss)
    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.runtime_bot", lambda: bot)
    shown = await client.post(
        f"{URL}/ATTENDANCE_OK/preview", json={"text": "✅ «{title}» — +{points} ball!"}, headers=headers
    )
    assert shown.status_code == 200
    assert "«O'tkan kunlar» — +30 ball!" in telegram.last_text() and "Namuna" in telegram.last_text()

    await client.put(f"{URL}/CANCELLED", json={"variants": ["Bekor qilindi 👌"]}, headers=headers)
    backup = (await client.get(f"{URL}/export/all", headers=headers)).json()
    assert backup["texts"]["CANCELLED"]["variants"] == ["Bekor qilindi 👌"]
    await client.delete(f"{URL}/CANCELLED", headers=headers)
    bad = await client.post(
        f"{URL}/import/all", json={"texts": {"WELCOME_BACK": {"variants": ["{nope}"]}}}, headers=headers
    )
    assert bad.status_code == 400
    restored = await client.post(f"{URL}/import/all", json=backup, headers=headers)
    assert restored.json() == {"imported": 1}
    text_store.force_rotation = False
    assert texts.CANCELLED == "Bekor qilindi 👌"


async def test_the_control_centre_shows_every_queue(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from app.services import support

    boss = await _boss(db)
    member = await create_user(db, telegram_id=next(_ids))
    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, plain, "ADMIN")
    await support.member_message(db, user=member, text="Savolim bor")
    await db.commit()
    await client.put(f"{URL}/CANCELLED", json={"variants": ["Bekor qilindi."]}, headers=admin_headers(boss))

    assert (await client.get("/api/v1/admin/control", headers=admin_headers(plain))).status_code == 403
    view = (await client.get("/api/v1/admin/control", headers=admin_headers(boss))).json()
    queues = {queue["code"]: queue for queue in view["queues"]}
    assert queues["support"]["count"] == 1 and queues["support"]["route"] == "support"
    assert view["waiting_total"] >= 1
    assert view["recent"][0]["what"] == "bot matnini o'zgartirdi" and view["recent"][0]["who"] == "Akmal Bosh"


def test_every_action_label_names_a_real_action() -> None:
    """The control centre's words for the audit log must name actions the code really records."""
    import pathlib
    import re

    from app.services.control import ACTIONS

    files = [path for path in pathlib.Path("app").rglob("*.py") if path.name != "control.py"]
    source = "\n".join(path.read_text() for path in files)
    recorded = set(re.findall(r'"([A-Z][A-Z_]+)"', source))
    recorded |= {f"CONTRIBUTION_{word}" for word in ("APPROVE", "FEATURE", "HIDE")}  # f"CONTRIBUTION_{...}"
    assert not set(ACTIONS) - recorded
