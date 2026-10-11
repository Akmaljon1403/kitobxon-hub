"""Round I1: «🎁 Sizning foydangiz» is always open — in the bot menu, as /referal and /taklif, in the
Mini App — and the personal link works even when BOT_USERNAME is not configured."""

from __future__ import annotations

import itertools
from types import SimpleNamespace

import httpx
import pytest
from aiogram.types import ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import keyboards, setup, texts
from app.core.config import get_settings
from app.models.enums import ScoreCategory
from app.services import bot_profile, features, referrals
from app.services.scoring import award_points
from app.services.settings import update_setting
from tests.bot_helpers import BotHarness
from tests.factories import create_user
from tests.helpers import member_headers

_ids = itertools.count(994_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


class _FakeBot:
    def __init__(self, username: str) -> None:
        self.username = username
        self.calls = 0

    async def me(self) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(username=self.username)


async def test_the_link_comes_from_telegram_when_bot_username_is_not_set(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "bot_username", None)
    monkeypatch.setattr(setup, "_detected_username", None)
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    assert await referrals.link(member) is None  # no bot at all: nothing to ask

    bot = _FakeBot("kitobxon_live_bot")
    assert await referrals.link(member, bot) == f"https://t.me/kitobxon_live_bot?start=ref_{member.member_number}"
    assert await setup.resolve_bot_username() == "kitobxon_live_bot"  # remembered for the whole process
    assert setup.bot_username() == "kitobxon_live_bot" and bot.calls == 1

    class _Broken:
        async def me(self) -> None:
            raise RuntimeError("network")

    monkeypatch.setattr(setup, "_detected_username", None)
    assert await setup.resolve_bot_username(_Broken()) is None  # a failure never breaks the page


async def test_the_menu_command_and_app_show_sizning_foydangiz(client: httpx.AsyncClient, db: AsyncSession) -> None:
    inviter = await create_user(db, telegram_id=next(_ids), first_name="Madina")
    friends = []
    for name, points in (("Bekzod", 120), ("Laylo", 45)):
        friend = await create_user(db, telegram_id=next(_ids), first_name=name, last_name="Karimova")
        friend.referred_by = inviter.id
        await award_points(
            db,
            user_id=friend.id,
            amount=points,
            category=ScoreCategory.CAMPAIGN,
            idempotency_key=f"t:{friend.id}",
            reason="test",
        )
        friends.append(friend)
    await db.commit()

    assert "referrals" not in features.FEATURES_BY_CODE  # nothing can switch it off
    assert texts.BTN_BENEFIT in keyboards.MENU_BUTTONS
    assert any(command.command == "referal" for command in bot_profile.MEMBER_COMMANDS)

    harness = BotHarness(inviter.telegram_id)
    await harness.send("/menu")
    menu = harness.session.sent_messages()[-1].reply_markup
    assert isinstance(menu, ReplyKeyboardMarkup)
    assert texts.BTN_BENEFIT in [button.text for row in menu.keyboard for button in row]

    for trigger in (texts.BTN_BENEFIT, "/referal", "/taklif"):
        await harness.send(trigger)
        text = harness.last_text()
        assert "🎁 <b>Sizning foydangiz</b>" in text, trigger
        assert f"ref_{inviter.member_number}" in text
        assert "Taklif qilganlaringiz: <b>2</b>" in text and "Ular to'plagan jami ball: <b>165</b>" in text
        assert "Bekzod K. — ⭐ 120 ball ⏳" in text and "Laylo K. — ⭐ 45 ball ⏳" in text

    await update_setting(db, key="referral.friend_details", value="NAMES", actor_id=inviter.id)
    await harness.send("/referal")
    assert "Bekzod K. ⏳" in harness.last_text() and "120 ball" not in harness.last_text().split("Do'stlaringiz")[1]

    brief = (await client.get("/api/v1/me/referrals/brief", headers=member_headers(inviter))).json()
    assert brief["enabled"] is True and brief["link"].endswith(f"ref_{inviter.member_number}")
    assert (brief["impact"]["invited"], brief["impact"]["friends_points"]) == (2, 165)

    newcomer = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    lonely = BotHarness(newcomer.telegram_id)
    await lonely.send("/referal")
    assert "Hali hech kimni taklif qilmagansiz" in lonely.last_text()


async def test_a_menu_button_escapes_the_receipt_waiting_step(db: AsyncSession) -> None:
    member = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    harness = BotHarness(member.telegram_id)
    from app.bot.states import CardReceipt

    state = harness.dispatcher.fsm.get_context(harness.bot, chat_id=member.telegram_id, user_id=member.telegram_id)
    await state.set_state(CardReceipt.waiting)
    await harness.send(texts.BTN_BENEFIT)
    assert "Sizning foydangiz" in harness.last_text()
