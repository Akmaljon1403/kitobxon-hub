"""Passport v2: the member's own photo, premium card designs, and live results behind the QR code."""

from __future__ import annotations

import io
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import GetFile, SendPhoto
from aiogram.methods.base import TelegramMethod
from aiogram.types import File
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.config import get_settings
from app.models import User
from app.models.enums import ScoreCategory
from app.security.permissions import Perm
from app.services import passport as passport_service
from app.services import premium as premium_service
from app.services.scoring import award_points
from app.services.storage import get_storage
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_base_url", "https://kitobxon.example.org")
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


def _jpeg(size: tuple[int, int] = (900, 1200), orientation: int | None = None) -> bytes:
    image = Image.new("RGB", size, (200, 120, 90))
    buffer = io.BytesIO()
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _upload(client: httpx.AsyncClient, member: User, data: bytes, name: str = "me.jpg") -> httpx.Response:
    return await client.put(
        "/api/v1/me/passport/photo", files={"file": (name, data, "image/jpeg")}, headers=member_headers(member)
    )


# ---------------------------------------------------------------------------- the photo


async def test_member_uploads_and_removes_their_photo(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    await db.commit()

    assert (await _upload(client, member, _jpeg(orientation=6))).status_code == 204
    await db.refresh(member)
    assert member.passport_photo_key and member.passport_photo_key.startswith(f"passport-photos/{member.id}/")
    stored = Image.open(io.BytesIO(await get_storage().get(member.passport_photo_key)))
    assert stored.size == passport_service.PHOTO_SIZE and not stored.getexif()  # cropped, metadata dropped
    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["passport_photo"] is True
    assert (await client.get("/api/v1/me/passport", headers=member_headers(member))).status_code == 200

    first_key = member.passport_photo_key
    assert (await _upload(client, member, _jpeg((400, 400)))).status_code == 204
    await db.refresh(member)
    assert member.passport_photo_key != first_key
    assert not await get_storage().exists(first_key)  # the old file is removed

    bad = await _upload(client, member, b"definitely not a picture", "x.jpg")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "PHOTO_INVALID"

    assert (await client.delete("/api/v1/me/passport/photo", headers=member_headers(member))).status_code == 204
    me = (await client.get("/api/v1/me", headers=member_headers(member))).json()
    assert me["passport_photo"] is False


async def test_admin_removes_an_unsuitable_photo(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    viewer = await create_user(db)
    manager = await create_user(db)
    await db.commit()
    for admin in (viewer, manager):
        await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, viewer, Perm.USER_VIEW)
    await grant_permissions(db, manager, Perm.USER_VIEW, Perm.USER_MANAGE)
    await _upload(client, member, _jpeg())

    path = f"/api/v1/admin/users/{member.id}/passport-photo"
    assert (await client.delete(path, headers=admin_headers(viewer))).status_code == 403
    assert (await client.delete(path, headers=admin_headers(manager))).status_code == 204
    await db.refresh(member)
    assert member.passport_photo_key is None


async def test_lost_photo_falls_back(db: AsyncSession) -> None:
    member = await create_user(db)
    member.passport_photo_key = "passport-photos/missing.jpg"
    await db.commit()
    assert await passport_service.own_photo(member) is None
    assert (await passport_service.render(db, member)).startswith(b"\x89PNG")


# ---------------------------------------------------------------------------- designs


async def test_card_designs_are_for_premium_members(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db)
    admin = await create_user(db)
    await db.commit()

    themes = (await client.get("/api/v1/me/passport/themes", headers=member_headers(member))).json()
    assert [t["code"] for t in themes] == ["classic", "gold", "silver", "midnight", "ruby", "ocean", "lavender"]
    assert next(t for t in themes if t["selected"])["code"] == "classic"
    refused = await client.put("/api/v1/me/passport/theme", json={"theme": "ruby"}, headers=member_headers(member))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "PREMIUM_REQUIRED"
    unknown = await client.put("/api/v1/me/passport/theme", json={"theme": "pink"}, headers=member_headers(member))
    assert unknown.status_code == 400

    subscription = await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=30, note=None)
    assert (await passport_service.collect(db, member)).theme == "gold"  # premium default
    chosen = await client.put("/api/v1/me/passport/theme", json={"theme": "ruby"}, headers=member_headers(member))
    assert chosen.status_code == 204
    themes = (await client.get("/api/v1/me/passport/themes", headers=member_headers(member))).json()
    assert next(t for t in themes if t["selected"])["code"] == "ruby"
    await db.refresh(member)
    assert (await passport_service.collect(db, member)).theme == "ruby"

    await premium_service.revoke_subscription(db, actor_id=admin.id, subscription_id=subscription.id, reason="Test")
    await db.refresh(member)
    data = await passport_service.collect(db, member)
    assert data.theme == "classic" and data.premium is False  # the design waits for the next premium period


# ---------------------------------------------------------------------------- QR page


async def test_qr_page_shows_live_results(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await create_user(db, first_name="Lola", last_name="Saidova")
    await award_points(db, user_id=member.id, amount=75, category=ScoreCategory.ATTENDANCE, idempotency_key="v1")
    await db.commit()
    page = await client.get(f"/v/{passport_service.verify_code(member)}")
    assert page.status_code == 200
    assert ("Natijalar" in page.text and "75" in page.text and "1-o&#39;rin" in page.text) or "1-o'rin" in page.text
    assert "Saidova Lola" in page.text


# ---------------------------------------------------------------------------- the bot


class PhotoUpload(FakeTelegramSession):
    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        if isinstance(method, GetFile):
            self.requests.append(method)
            return File(file_id=method.file_id, file_unique_id="u", file_path="photos/me.jpg")
        return await super().make_request(bot, method, timeout)

    async def stream_content(self, *args: Any, **kwargs: Any) -> AsyncGenerator[bytes, None]:
        yield _jpeg()


def _harness(telegram_id: int) -> BotHarness:
    harness = BotHarness(telegram_id)
    harness.session = PhotoUpload()
    harness.bot = Bot(token=BOT_TOKEN, session=harness.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return harness


async def test_bot_changes_the_photo_and_design(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=9101)
    admin = await create_user(db)
    await db.commit()
    member_id, admin_id = member.id, admin.id
    harness = _harness(9101)

    await harness.send(texts.BTN_PASSPORT)
    photo = next(r for r in reversed(harness.session.requests) if isinstance(r, SendPhoto))
    callbacks = [b.callback_data for row in photo.reply_markup.inline_keyboard for b in row if b.callback_data]
    assert "pp:photo" in callbacks and "pp:reset" not in callbacks

    await harness.press("pp:photo")
    assert harness.last_text() == texts.PASSPORT_PHOTO_ASK
    await harness.send("salom")
    assert harness.last_text() == texts.PASSPORT_PHOTO_HINT
    await harness.send_photo("photo-file-id")
    saved = next(r for r in reversed(harness.session.requests) if isinstance(r, SendPhoto))
    assert saved.caption.startswith(texts.PASSPORT_PHOTO_SAVED)
    assert "pp:reset" in [b.callback_data for row in saved.reply_markup.inline_keyboard for b in row]
    db.expire_all()
    assert (await db.get(User, member_id)).passport_photo_key is not None

    await harness.press("pp:reset")
    db.expire_all()
    assert (await db.get(User, member_id)).passport_photo_key is None

    await harness.press("pp:themes")
    assert "Premium" in harness.last_text()
    await premium_service.grant(db, actor_id=admin_id, user_id=member_id, days=30, note=None)
    await harness.press("pp:themes")
    themes = harness.session.sent_messages()[-1].reply_markup.inline_keyboard
    assert [button.callback_data for row in themes for button in row] == [
        f"pp:theme:{code}" for code in passport_service.THEMES
    ]
    assert themes[0][1].text.startswith("✅")  # gold by default (two designs per row)
    await harness.press("pp:theme:midnight")
    db.expire_all()
    assert (await db.get(User, member_id)).passport_theme == "midnight"


# ---------------------------------------------------------------------------- premium perks


async def test_personal_stats_ranking_badge_and_menu_button(client: httpx.AsyncClient, db: AsyncSession) -> None:
    from aiogram.types import ReplyKeyboardMarkup

    from app.models.enums import AttendanceMethod, FeatureMode
    from app.services import features
    from tests.factories import create_event

    member = await create_user(db, telegram_id=9201)
    other = await create_user(db)
    admin = await create_user(db)
    event = await create_event(db)
    from app.models import AttendanceRecord

    db.add(AttendanceRecord(event_id=event.id, user_id=member.id, method=AttendanceMethod.CODE))
    await award_points(db, user_id=member.id, amount=30, category=ScoreCategory.ATTENDANCE, idempotency_key="s1")
    await award_points(db, user_id=other.id, amount=10, category=ScoreCategory.ATTENDANCE, idempotency_key="s2")
    await db.commit()
    await grant_role(db, admin, "SUPER_ADMIN")

    locked = await client.get("/api/v1/me/stats", headers=member_headers(member))
    assert locked.status_code == 403 and locked.json()["error"]["code"] == "PREMIUM_REQUIRED"
    await premium_service.grant(db, actor_id=admin.id, user_id=member.id, days=30, note=None)
    stats = (await client.get("/api/v1/me/stats", headers=member_headers(member))).json()
    assert len(stats["months"]) == 6 and stats["months"][-1]["points"] == 30
    assert stats["total"] == 30 and stats["month_rank"] == 1 and stats["events_attended"] == 1
    assert stats["attendance_rate"] == 100 and stats["breakdown"] == {"ATTENDANCE": 30}

    board = (await client.get("/api/v1/rankings?period=week&scope=all", headers=member_headers(other))).json()
    assert [(row["total"], row["premium"]) for row in board["items"]] == [(30, True), (10, False)]

    status = (await client.get("/api/v1/me/premium", headers=member_headers(member))).json()
    assert any(perk["title"] == "Pasport dizaynlari" for perk in status["perks"])
    assert {f["code"] for f in status["premium_features"]} >= {"weekly_digest", "personal_stats"}

    harness = BotHarness(9201)
    await harness.send("/menu")
    keyboard = harness.session.sent_messages()[-1].reply_markup
    assert isinstance(keyboard, ReplyKeyboardMarkup)
    assert texts.BTN_PREMIUM not in [b.text for row in keyboard.keyboard for b in row]  # store closed
    await features.set_mode(db, actor_id=admin.id, code="premium", new_mode=FeatureMode.ALL, announce=False)
    await harness.send("/menu")
    keyboard = harness.session.sent_messages()[-1].reply_markup
    assert [b.text for b in keyboard.keyboard[-1]] == [texts.BTN_HELP, texts.BTN_PREMIUM]
    await harness.send(texts.BTN_PREMIUM)
    assert "Kitobxon Premium" in harness.last_text() and "Pasport dizaynlari" in harness.last_text()
    await harness.send(texts.BTN_RANKING)
    assert "💎" in harness.last_text()
