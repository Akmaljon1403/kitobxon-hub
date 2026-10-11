"""«Do'stingizni taklif qiling»: a personal link, the reward when the friend comes to an event."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.models import FeatureFlag, Notification, PremiumSubscription, ScoreTransaction, User
from app.models.enums import FeatureMode, PremiumSource
from app.services import attendance, referrals
from app.services.settings import update_setting
from tests.bot_helpers import BotHarness
from tests.factories import create_event, create_user
from tests.helpers import grant_role, member_headers

_ids = itertools.count(990_000)


@pytest.fixture(autouse=True)
def _setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _register(payload: str, first_name: str, phone: str) -> BotHarness:
    harness = BotHarness(next(_ids), first_name=first_name)
    await harness.send(f"/start {payload}")
    await harness.send(first_name)
    await harness.send("Do'stov")
    await harness.share_contact(phone)
    await harness.press("reg:course:1")
    await harness.send("101")
    await harness.press("reg:confirm")
    return harness


async def _user(db: AsyncSession, harness: BotHarness) -> User:
    user = await db.scalar(
        select(User).where(User.telegram_id == harness.user.id).execution_options(populate_existing=True)
    )
    assert user is not None
    return user


async def _visit(db: AsyncSession, admin: User, friend: User) -> None:
    if not getattr(admin, "_boss", False):
        await grant_role(db, admin, "SUPER_ADMIN")  # a super admin's manual check-in counts at once
        admin._boss = True
    event = await create_event(db, title="Kitob kechasi", starts_at=datetime.now(UTC) - timedelta(minutes=10))
    await db.commit()
    await attendance.manual_check_in(db, actor_id=admin.id, event_id=event.id, user_id=friend.id, note="Kelgan")


async def _points(db: AsyncSession, user: User) -> int:
    return int(
        await db.scalar(
            select(func.coalesce(func.sum(ScoreTransaction.amount), 0)).where(
                ScoreTransaction.user_id == user.id, ScoreTransaction.source_type == "REFERRAL"
            )
        )
    )


def test_payload() -> None:
    assert referrals.parse("ref_1024") == 1024
    assert referrals.parse("ref_x") is None and referrals.parse("checkin_abc") is None and referrals.parse(None) is None


async def test_friend_joins_comes_to_an_event_and_the_inviter_is_thanked(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    inviter = await create_user(db, telegram_id=next(_ids), first_name="Aziza")
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()

    info = (await client.get("/api/v1/me/referrals", headers=member_headers(inviter))).json()
    assert info["link"] == f"https://t.me/kitobxon_test_bot?start=ref_{inviter.member_number}"
    assert (info["invited"], info["points"], info["premium_days"], info["monthly_limit"]) == (0, 20, 7, 5)

    friend_bot = await _register(f"ref_{inviter.member_number}", "Bobur", "+998901110001")
    friend = await _user(db, friend_bot)
    assert friend.referred_by == inviter.id and friend.referral_rewarded_at is None
    joined = await db.scalar(select(Notification.text).where(Notification.dedup_key == f"referral:joined:{friend.id}"))
    assert "Bobur" in joined and "+20 ball va 7 kunlik 💎 Premium" in joined

    await _visit(db, admin, friend)
    assert await _points(db, inviter) == 20
    premium = await db.scalar(select(PremiumSubscription).where(PremiumSubscription.user_id == inviter.id))
    assert premium.source == PremiumSource.REFERRAL and (premium.ends_at - premium.starts_at).days == 7
    thanks = await db.scalar(select(Notification).where(Notification.dedup_key == f"referral:rewarded:{friend.id}"))
    assert "birinchi tadbirda qatnashdi" in thanks.text and thanks.payload["mood"] == "CELEBRATE"

    await _visit(db, admin, friend)  # the second event: nothing more
    assert await _points(db, inviter) == 20

    info = (await client.get("/api/v1/me/referrals", headers=member_headers(inviter))).json()
    assert (info["invited"], info["rewarded"]) == (1, 1)

    harness = BotHarness(inviter.telegram_id)
    await harness.send("/taklif")
    reply = harness.last_text()
    assert f"ref_{inviter.member_number}" in reply and "Taklif qilganlaringiz: <b>1</b>" in reply
    button = harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0]
    assert button.text == texts.BTN_SHARE_INVITE and button.url.startswith("https://t.me/share/url?")


async def test_monthly_limit_unknown_links_and_switching_off(db: AsyncSession) -> None:
    inviter = await create_user(db, telegram_id=next(_ids))
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await update_setting(db, key="referral.monthly_limit", value=1, actor_id=admin.id)

    first = await _user(db, await _register(f"ref_{inviter.member_number}", "Dilshod", "+998901110002"))
    second = await _user(db, await _register(f"ref_{inviter.member_number}", "Erkin", "+998901110003"))
    await _visit(db, admin, first)
    await _visit(db, admin, second)
    assert await _points(db, inviter) == 20  # one reward this month
    await db.refresh(second)
    assert second.referral_rewarded_at is None  # waits: rewarded at a later event, next month

    stray = await _user(db, await _register("ref_99999999", "Farrux", "+998901110004"))
    assert stray.referred_by is None

    # Inviting friends is always open: a switch stored by an older version changes nothing.
    db.add(FeatureFlag(code="referrals", mode=FeatureMode.OFF))
    await db.commit()
    still = await _user(db, await _register(f"ref_{inviter.member_number}", "G'ayrat", "+998901110005"))
    assert still.referred_by == inviter.id
    harness = BotHarness(inviter.telegram_id)
    await harness.send("/taklif")
    assert f"ref_{inviter.member_number}" in harness.last_text()
