"""Rounds E12–E14: the new study year, members who stopped coming, cleaning up old records, the admin
search box, and licences for copies rented to other organisations."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import licence_tool
from app.bot import texts
from app.core import licence
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import ForbiddenError
from app.models import AuditLog, BotFsmState, Notification, Season
from app.models.enums import NotificationStatus, NotificationType, UserStatus
from app.security.permissions import Perm
from app.services import lifecycle, members
from app.services.notifications import enqueue_notification
from app.services.settings import get_setting, update_setting
from app.workers import jobs
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, make_init_data, member_headers

_ids = itertools.count(1_800_000)
NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------- the new study year


def test_study_year_boundaries() -> None:
    assert lifecycle.study_year_start(date(2026, 9, 1)) == 2026
    assert lifecycle.study_year_start(date(2026, 8, 31)) == 2025
    assert lifecycle.study_year_start(date(2027, 2, 1), "09-15") == 2026
    assert lifecycle._start_date(2027, "02-30") == date(2027, 2, 28)


async def test_new_study_year_moves_courses_and_opens_a_season(db: AsyncSession) -> None:
    second = await create_user(db, course=2)
    last = await create_user(db, course=6)
    paused = await create_user(db, course=3, status=UserStatus.INACTIVE)
    await db.commit()

    # The first run after installing only remembers the year.
    assert await lifecycle.new_study_year(db, NOW) == 0
    assert await get_setting(db, "academic.current_year") == 2026
    await db.refresh(second)
    assert second.course == 2

    await update_setting(db, key="academic.current_year", value=2025, actor_id=None)
    assert await lifecycle.new_study_year(db, NOW) == 1
    for user in (second, last, paused):
        await db.refresh(user)
    assert (second.course, last.course, paused.course) == (3, 6, 3)
    season = await db.scalar(select(Season).where(Season.is_current.is_(True)))
    assert season is not None and season.name == "2026–2027 o'quv yili"
    assert (season.starts_on, season.ends_on) == (date(2026, 9, 1), date(2027, 8, 31))
    note = await db.scalar(select(Notification).where(Notification.user_id == second.id))
    assert note is not None and "3-kurs" in note.text
    assert await get_setting(db, "academic.current_year") == 2026

    # Running again the same year changes nothing.
    assert await lifecycle.new_study_year(db, NOW + timedelta(days=1)) == 0
    await db.refresh(second)
    assert second.course == 3


# ---------------------------------------------------------------------------- members who stopped coming


async def test_inactive_members_are_warned_then_paused_and_come_back(db: AsyncSession) -> None:
    long_ago = NOW - timedelta(days=400)
    away = await create_user(db, telegram_id=next(_ids), last_seen_at=long_ago)
    staff = await create_user(db, telegram_id=next(_ids), last_seen_at=long_ago)
    regular = await create_user(db, telegram_id=next(_ids), last_seen_at=NOW - timedelta(days=3))
    await db.commit()
    await grant_role(db, staff, "ADMIN")

    assert await lifecycle.inactive_members(db, NOW) == 0  # first a friendly reminder
    warnings = list(await db.scalars(select(Notification).where(Notification.dedup_key.like("inactive-warning:%"))))
    assert [note.user_id for note in warnings] == [away.id]
    assert warnings[0].payload["buttons"][0]["callback"] == "mem:alive"

    assert await lifecycle.inactive_members(db, datetime.now(UTC) + timedelta(days=3)) == 0  # still a week to come back
    later = datetime.now(UTC) + timedelta(days=8)
    assert await lifecycle.inactive_members(db, later) == 1
    count = await db.scalar(select(func.count()).where(Notification.dedup_key.like("inactive-warning:%")))
    assert count == 1  # warned once
    for user in (away, staff, regular):
        await db.refresh(user)
    assert away.status == UserStatus.INACTIVE and away.left_reason == lifecycle.INACTIVE_REASON
    assert staff.status == UserStatus.ACTIVE and regular.status == UserStatus.ACTIVE

    # They come back by themselves with /start.
    harness = BotHarness(away.telegram_id)
    await harness.send("/start")
    assert texts.WELCOME_BACK_AFTER_BREAK in [m.text for m in harness.session.sent_messages()]
    await db.refresh(away)
    assert away.status == UserStatus.ACTIVE and away.left_reason is None


async def test_coming_back_through_the_app_and_still_here_button(client: httpx.AsyncClient, db: AsyncSession) -> None:
    away = await create_user(
        db, telegram_id=next(_ids), status=UserStatus.INACTIVE, left_reason=lifecycle.INACTIVE_REASON
    )
    paused_by_admin = await create_user(db, telegram_id=next(_ids), status=UserStatus.INACTIVE)
    member = await create_user(db, telegram_id=next(_ids), last_seen_at=NOW - timedelta(days=300))
    await db.commit()

    signed_in = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(away.telegram_id)})
    assert signed_in.status_code == 200, signed_in.text
    await db.refresh(away)
    assert away.status == UserStatus.ACTIVE

    # Only the automatic pause ends by itself; an admin's decision stays.
    refused = await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data(paused_by_admin.telegram_id)}
    )
    assert refused.status_code == 403
    assert not await lifecycle.wake_up(db, paused_by_admin)

    harness = BotHarness(member.telegram_id)
    await harness.press("mem:alive")
    answers = [request for request in harness.session.requests if type(request).__name__ == "AnswerCallbackQuery"]
    assert answers[-1].text == texts.STILL_HERE
    await db.refresh(member)
    assert member.last_seen_at is not None and member.last_seen_at > NOW - timedelta(days=1)


async def test_switched_off_inactivity(db: AsyncSession) -> None:
    await create_user(db, last_seen_at=NOW - timedelta(days=900))
    await db.commit()
    await update_setting(db, key="membership.inactive_days", value=0, actor_id=None)
    assert await lifecycle.inactive_members(db, NOW) == 0
    assert await db.scalar(select(func.count()).select_from(Notification)) == 0


async def test_old_records_are_cleaned_up(db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()
    for text, status in (("old sent", NotificationStatus.SENT), ("old pending", NotificationStatus.PENDING)):
        await enqueue_notification(db, user_id=member.id, type_=NotificationType.SYSTEM, text=text)
        await db.execute(
            update(Notification)
            .where(Notification.text == text)
            .values(status=status, created_at=datetime.now(UTC) - timedelta(days=200))
        )
    await enqueue_notification(db, user_id=member.id, type_=NotificationType.SYSTEM, text="fresh")
    db.add(BotFsmState(key="old-chat", state="Some:state", data={}))
    db.add(BotFsmState(key="new-chat", state="Some:state", data={}))
    db.add(AuditLog(action="OLD", entity_type="x", created_at=datetime.now(UTC) - timedelta(days=4 * 365)))
    await db.commit()
    await db.execute(
        update(BotFsmState)
        .where(BotFsmState.key == "old-chat")
        .values(updated_at=datetime.now(UTC) - timedelta(days=90))
    )
    await db.commit()

    assert await lifecycle.cleanup(db) == 2
    assert set(await db.scalars(select(Notification.text))) == {"old pending", "fresh"}
    assert set(await db.scalars(select(BotFsmState.key))) == {"new-chat"}
    assert set(await db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "x"))) == {"OLD"}  # kept
    assert await lifecycle.cleanup(db) == 0


# ---------------------------------------------------------------------------- the admin search box


async def test_search_finds_pages_settings_commands_and_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    reader = await create_user(db, first_name="Zuhra", last_name="Qodirova", group_name="305")
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.NOTIFICATION_SEND, Perm.USER_VIEW)
    headers = admin_headers(admin)

    found = (await client.get("/api/v1/admin/search", params={"q": "stiker"}, headers=headers)).json()
    kinds = {(item["kind"], item["title"]) for item in found}
    assert ("page", "📣 Telegram kanal") in kinds
    assert ("command", "/stiker") in kinds
    assert any(item["kind"] == "setting" and item["route"] == "settings?key=notifications.stickers" for item in found)

    people = (await client.get("/api/v1/admin/search", params={"q": "qodirova"}, headers=headers)).json()
    assert people[0]["kind"] == "member" and people[0]["title"] == "Qodirova Zuhra"
    assert "305" in people[0]["subtitle"]
    by_name = (await client.get("/api/v1/admin/search", params={"q": "zuhra qodir"}, headers=headers)).json()
    assert by_name and by_name[0]["title"] == "Qodirova Zuhra"
    assert (await client.get("/api/v1/admin/search", params={"q": "z"}, headers=headers)).json() == []
    assert (await client.get("/api/v1/admin/search", params={"q": "%_"}, headers=headers)).json() == []

    # Without the permission, members and the channel page stay hidden.
    other = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, other, "ADMIN")
    limited = admin_headers(other)
    assert (await client.get("/api/v1/admin/search", params={"q": "qodirova"}, headers=limited)).json() == []
    pages = (await client.get("/api/v1/admin/search", params={"q": "stiker"}, headers=limited)).json()
    assert ("page", "📣 Telegram kanal") not in {(item["kind"], item["title"]) for item in pages}
    assert (
        await client.get("/api/v1/admin/search", params={"q": "stiker"}, headers=member_headers(reader))
    ).status_code == 403


# ---------------------------------------------------------------------------- licences


def _keys() -> tuple[bytes, str]:
    private = Ed25519PrivateKey.generate()
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pem, licence.b64encode(public)


@pytest.fixture
def licensed(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Turns this copy into a rented one with a licence ending on the given day."""
    pem, public = _keys()

    def apply(until: date, members: int | None = None, key: str | None = None) -> str:
        issued = key or licence.sign(pem, organization="Namuna kolleji", until=until, members=members)
        settings = get_settings().model_copy(
            update={"licence_required": True, "licence_key": SecretStr(issued), "licence_public_key": public}
        )
        monkeypatch.setattr("app.core.licence.get_settings", lambda: settings)
        return issued

    return apply


def test_licence_signature_and_dates() -> None:
    pem, public = _keys()
    key = licence.sign(pem, organization="Namuna kolleji", until=date(2027, 12, 31), members=500)
    parsed = licence.parse(key, public)
    assert (parsed.organization, parsed.expires, parsed.max_members) == ("Namuna kolleji", date(2027, 12, 31), 500)
    body, signature = key.split(".")
    forged = licence.b64encode(licence._b64decode(body).replace(b"2027", b"2099")) + "." + signature
    with pytest.raises(ValueError):
        licence.parse(forged, public)
    with pytest.raises(ValueError):
        licence.parse(key, _keys()[1])  # someone else's key
    with pytest.raises(ValueError):
        licence.parse("garbage", public)
    assert licence.grace_end(parsed) == date(2028, 1, 7)


def test_licence_status(licensed: Any) -> None:
    assert not licence.status().required  # the club's own server needs no licence
    licensed(date.today() + timedelta(days=20))
    current = licence.status()
    assert current.valid and current.days_left == 20 and not current.blocks_members and current.problem is None
    licensed(date.today() - timedelta(days=3))
    current = licence.status()
    assert not current.blocks_members and current.problem and "4 kundan keyin" in current.problem
    licensed(date.today() - timedelta(days=10))
    assert licence.status().blocks_members
    licensed(date.today(), key="not.genuine")
    current = licence.status()
    assert not current.valid and current.blocks_members


async def test_an_ended_licence_pauses_members_but_not_admins(
    client: httpx.AsyncClient, db: AsyncSession, licensed: Any
) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    licensed(date.today() - timedelta(days=30))

    refused = await client.get("/api/v1/me", headers=member_headers(member))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "LICENCE_EXPIRED"
    view = await client.get("/api/v1/admin/system/licence", headers=admin_headers(admin))
    assert view.status_code == 200
    assert view.json()["organization"] == "Namuna kolleji" and view.json()["members_paused"] is True

    harness = BotHarness(member.telegram_id)
    await harness.send("salom")
    assert harness.last_text() == licence.MEMBER_MESSAGE
    await harness.press("menu:home")
    answers = [r for r in harness.session.requests if type(r).__name__ == "AnswerCallbackQuery"]
    assert answers[-1].text == licence.MEMBER_MESSAGE[:200] and answers[-1].show_alert
    admin_bot = BotHarness(admin.telegram_id)
    await admin_bot.send("/start")
    assert admin_bot.last_text() != licence.MEMBER_MESSAGE

    # Messages go only to administrators; scheduled jobs only tidy up.
    for user in (member, admin):
        await enqueue_notification(db, user_id=user.id, type_=NotificationType.SYSTEM, text="E'lon")
    await db.commit()
    telegram = FakeTelegramSession()
    bot = Bot(token=BOT_TOKEN, session=telegram, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    report = await send_due_notifications(get_session_factory(), bot)
    assert (report.sent, report.skipped) == (1, 1)
    skipped = await db.scalar(select(Notification).where(Notification.user_id == member.id))
    assert skipped is not None and skipped.last_error == "licence expired"
    results = await jobs.run_scheduled_jobs(get_session_factory())
    assert set(results) <= jobs.HOUSEKEEPING


async def test_licence_member_limit(db: AsyncSession, licensed: Any) -> None:
    await create_user(db)
    await create_user(db)
    await db.commit()
    data = members.RegistrationData(
        telegram_id=next(_ids),
        telegram_username=None,
        language_code="uz",
        first_name="Yangi",
        last_name="A'zo",
        phone="+998901112233",
        faculty_id=None,
        course=1,
        group_name="101",
    )
    licensed(date.today() + timedelta(days=90), members=2)
    with pytest.raises(ForbiddenError) as error:
        await members.register_member(db, data)
    assert error.value.code == "LICENCE_MEMBER_LIMIT"
    await db.rollback()
    licensed(date.today() + timedelta(days=90), members=3)
    user = await members.register_member(db, data)
    assert user.first_name == "Yangi"


def test_owner_licence_tool(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    key_file = tmp_path / "owner-key.pem"
    assert licence_tool.main(["keygen", str(key_file)]) == 0
    public = capsys.readouterr().out.split("LICENCE_PUBLIC_KEY=")[1].strip()
    assert licence_tool.main(["keygen", str(key_file)]) == 1  # never overwrites the owner's key
    capsys.readouterr()
    assert licence_tool.main(["issue", str(key_file), "Namuna kolleji", "2027-06-30", "--members", "800"]) == 0
    issued = capsys.readouterr().out.split("LICENCE_KEY=")[1].strip()
    parsed = licence.parse(issued, public)
    assert (parsed.organization, parsed.expires, parsed.max_members) == ("Namuna kolleji", date(2027, 6, 30), 800)
