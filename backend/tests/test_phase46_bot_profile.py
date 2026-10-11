"""Round G2: the bot's Telegram profile (name, descriptions, command menus, rights, avatar) is kept in
settings and applied by the bot itself — no @BotFather steps for the owners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import (
    DeleteMyCommands,
    GetMe,
    GetMyDescription,
    GetMyName,
    GetMyShortDescription,
    GetUserProfilePhotos,
    SetChatMenuButton,
    SetMyCommands,
    SetMyDefaultAdministratorRights,
    SetMyDescription,
    SetMyName,
    SetMyProfilePhoto,
    SetMyShortDescription,
)
from aiogram.methods.base import TelegramMethod
from aiogram.types import (
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotDescription,
    BotName,
    BotShortDescription,
    UserProfilePhotos,
)
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.security.permissions import Perm
from app.services import bot_profile
from app.services.settings import BOT_DESCRIPTION, BOT_SHORT_DESCRIPTION, update_setting
from tests.bot_helpers import BOT_TOKEN, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role


class ProfileSession(FakeTelegramSession):
    """Telegram that remembers the profile it was given."""

    def __init__(self) -> None:
        super().__init__()
        self.profile = {"name": "Kitobxon", "short_description": "", "description": ""}
        self.photos = 0

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:  # noqa: ASYNC109
        self.requests.append(method)
        match method:
            case GetMe():
                return TgUser(id=bot.id, is_bot=True, first_name=self.profile["name"], username="kitobxon_test_bot")
            case GetMyName():
                return BotName(name=self.profile["name"])
            case GetMyShortDescription():
                return BotShortDescription(short_description=self.profile["short_description"])
            case GetMyDescription():
                return BotDescription(description=self.profile["description"])
            case GetUserProfilePhotos():
                return UserProfilePhotos(total_count=self.photos, photos=[])
            case SetMyName():
                self.profile["name"] = method.name or ""
            case SetMyShortDescription():
                self.profile["short_description"] = method.short_description or ""
            case SetMyDescription():
                self.profile["description"] = method.description or ""
            case SetMyProfilePhoto():
                self.photos += 1
        return True

    def of(self, kind: type) -> list[Any]:
        return [r for r in self.requests if isinstance(r, kind)]


@pytest.fixture
def telegram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ProfileSession:
    session = ProfileSession()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    monkeypatch.setattr("app.services.delivery.optional_bot", lambda: bot)
    avatar = tmp_path / "avatar.jpg"
    avatar.write_bytes(b"\xff\xd8\xff fake jpeg")
    monkeypatch.setattr(bot_profile, "AVATAR", avatar)
    session.bot = bot  # type: ignore[attr-defined]
    return session


async def test_start_up_applies_the_whole_profile_once(db: AsyncSession, telegram: ProfileSession) -> None:
    sender = await create_user(db)
    helper = await create_user(db)
    member = await create_user(db)
    await db.commit()
    await grant_role(db, sender, "ADMIN")
    await grant_permissions(db, sender, Perm.NOTIFICATION_SEND)
    await grant_role(db, helper, "ADMIN")
    bot: Bot = telegram.bot  # type: ignore[attr-defined]

    result = await bot_profile.apply_all(bot, db, "https://kitobxon.example/app/")
    assert result["texts"] == ["short_description", "description"]  # the name stays as in @BotFather
    assert result["commands"] == 2 and result["avatar"] is True
    assert telegram.profile["description"] == BOT_DESCRIPTION
    assert telegram.profile["short_description"] == BOT_SHORT_DESCRIPTION
    assert len(BOT_DESCRIPTION) <= 512 and len(BOT_SHORT_DESCRIPTION) <= 120

    menus = {
        (type(r.scope).__name__, getattr(r.scope, "chat_id", None)): [c.command for c in r.commands]
        for r in telegram.of(SetMyCommands)
    }
    members = menus[(BotCommandScopeAllPrivateChats.__name__, None)]
    assert "start" in members and "admin" not in members
    assert menus[(BotCommandScopeChat.__name__, sender.telegram_id)][-3:] == ["admin", "stiker", "emoji"]
    assert menus[(BotCommandScopeChat.__name__, helper.telegram_id)][-1] == "admin"
    assert (BotCommandScopeChat.__name__, member.telegram_id) not in menus
    assert {r.for_channels for r in telegram.of(SetMyDefaultAdministratorRights)} == {True, False}
    channel_rights = next(r for r in telegram.of(SetMyDefaultAdministratorRights) if r.for_channels)
    assert channel_rights.rights.can_post_messages is True
    assert telegram.of(SetChatMenuButton)[-1].menu_button.text == "📱 Ilova"

    # A restart with nothing changed sends no profile texts and keeps the avatar.
    telegram.clear()
    again = await bot_profile.apply_all(bot, db, None)
    assert again["texts"] == [] and again["avatar"] == "kept"
    assert not telegram.of(SetMyDescription) and not telegram.of(SetMyProfilePhoto)


async def test_changing_a_setting_reaches_telegram(db: AsyncSession, telegram: ProfileSession) -> None:
    owner = await create_user(db)
    await db.commit()
    await update_setting(db, key="bot.name", value="Kitobxon Hub | FJSTI", actor_id=owner.id)
    await update_setting(db, key="bot.description", value="Salom!\nBu klub boti.", actor_id=owner.id)
    assert telegram.profile["name"] == "Kitobxon Hub | FJSTI"
    assert telegram.profile["description"] == "Salom!\nBu klub boti."


async def test_admin_menu_follows_role_changes(
    client: httpx.AsyncClient, db: AsyncSession, telegram: ProfileSession
) -> None:
    owner = await create_user(db)
    reader = await create_user(db)
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    headers = admin_headers(owner)
    reader_id, reader_tg = reader.id, reader.telegram_id

    response = await client.post(
        "/api/v1/admin/admins",
        json={"user_id": str(reader_id), "permissions": [Perm.NOTIFICATION_SEND.value]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    menu = telegram.of(SetMyCommands)[-1]
    assert menu.scope.chat_id == reader_tg and "emoji" in [c.command for c in menu.commands]

    response = await client.post(
        f"/api/v1/admin/admins/{reader_id}/dismiss", json={"reason": "O'qishni tugatdi"}, headers=headers
    )
    assert response.status_code == 204
    assert telegram.of(DeleteMyCommands)[-1].scope.chat_id == reader_tg


async def test_the_bot_profile_in_the_admin_panel(
    client: httpx.AsyncClient, db: AsyncSession, telegram: ProfileSession
) -> None:
    owner = await create_user(db)
    reader = await create_user(db)
    await db.commit()
    await grant_role(db, owner, "SUPER_ADMIN")
    headers = admin_headers(owner)

    view = (await client.get("/api/v1/admin/bot-profile", headers=headers)).json()
    assert view["username"] == "kitobxon_test_bot" and view["has_avatar"] is False
    assert view["wanted"]["description"] == BOT_DESCRIPTION and view["telegram"]["description"] == ""

    applied = (await client.post("/api/v1/admin/bot-profile/apply", headers=headers)).json()
    assert applied["telegram"]["description"] == BOT_DESCRIPTION

    avatar = (await client.post("/api/v1/admin/bot-profile/avatar", headers=headers)).json()
    assert avatar["ok"] is True and avatar["has_avatar"] is True

    assert (await client.get("/api/v1/admin/bot-profile", headers=admin_headers(reader))).status_code in (401, 403)
    too_long = await client.put(
        "/api/v1/admin/settings/bot.short_description", json={"value": "x" * 121}, headers=headers
    )
    assert too_long.status_code == 422
