"""Leaving the club and coming back: blocking the bot, restoring within 14/30 days, cancelling and erasing."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import ChatMemberBanned, ChatMemberMember, ChatMemberUpdated, Update
from aiogram.types import User as TgUser
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.core.database import get_session_factory
from app.models import AuditLog, Notification, ScoreTransaction, User
from app.models.enums import NotificationStatus, NotificationType, ScoreCategory, UserStatus
from app.security.permissions import Perm
from app.services import membership, ranking
from app.services.notifications import enqueue_notification
from app.services.scoring import award_points
from app.workers import sender as sender_module
from app.workers.sender import send_due_notifications
from tests.bot_helpers import BOT_TOKEN, BotHarness, FakeTelegramSession
from tests.factories import create_user
from tests.helpers import admin_headers, grant_permissions, grant_role, member_headers

sender_module.SEND_INTERVAL_SECONDS = 0
_ids = itertools.count(970_000)


@pytest.fixture(autouse=True)
def _no_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.bot.setup.get_bot_runtime", lambda: None)


async def _member(db: AsyncSession, **fields: Any) -> User:
    user = await create_user(db, telegram_id=next(_ids), first_name="Aziza", last_name="Karimova", **fields)
    await award_points(db, user_id=user.id, amount=25, category=ScoreCategory.TEST, idempotency_key=f"m{user.id}")
    await db.commit()
    return user


async def _manager(db: AsyncSession) -> User:
    admin = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, admin, "ADMIN")
    await grant_permissions(db, admin, Perm.USER_VIEW, Perm.USER_MANAGE)
    return admin


async def _left_days_ago(db: AsyncSession, user: User, days: float) -> None:
    await db.execute(update(User).where(User.id == user.id).values(left_at=datetime.now(UTC) - timedelta(days=days)))
    await db.commit()
    await db.refresh(user)


def _blocked(harness: BotHarness) -> Update:
    me = TgUser(id=1, is_bot=True, first_name="Kitobxon")
    return Update(
        update_id=next(_ids),
        my_chat_member=ChatMemberUpdated(
            chat=harness.chat,
            from_user=harness.user,
            date=datetime.now(UTC),
            old_chat_member=ChatMemberMember(user=me),
            new_chat_member=ChatMemberBanned(user=me, until_date=datetime.fromtimestamp(0, UTC)),
        ),
    )


async def test_blocking_the_bot_and_coming_back_within_two_weeks(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await _member(db)
    old_headers = member_headers(member)
    await enqueue_notification(db, user_id=member.id, type_=NotificationType.SYSTEM, text="Salom", dedup_key="x")
    await db.commit()
    harness = BotHarness(member.telegram_id)

    await harness.dispatcher.feed_update(harness.bot, _blocked(harness))
    await db.refresh(member)
    assert member.status == UserStatus.LEFT and member.left_reason == "BOT_BLOCKED"
    assert (
        await db.scalar(select(Notification.status).where(Notification.dedup_key == "x")) == NotificationStatus.SKIPPED
    )
    # Every session ends, and the Mini App explains why.
    assert (await client.get("/api/v1/me", headers=old_headers)).status_code == 401
    # Hidden from the ranking.
    board = await ranking.ranking(db, period="all", scope="all", viewer=None)
    assert all(row.name != "Karimova Aziza" for row in board.items)

    await harness.send("/start")
    assert "♻️" in harness.last_text()
    markup = harness.session.sent_messages()[-1].reply_markup
    assert [b.callback_data for row in markup.inline_keyboard for b in row] == ["mem:restore", "mem:fresh"]
    await harness.press("mem:restore")
    assert "Hammasi tiklandi" in harness.last_text()
    await db.refresh(member)
    assert member.status == UserStatus.ACTIVE and member.left_at is None
    points = await db.scalar(select(func.sum(ScoreTransaction.amount)).where(ScoreTransaction.user_id == member.id))
    assert points == 25  # nothing was lost


async def test_restore_request_between_two_weeks_and_a_month(db: AsyncSession) -> None:
    member = await _member(db)
    admin = await _manager(db)
    await membership.leave(db, member, reason="BOT_BLOCKED")
    await db.commit()
    await _left_days_ago(db, member, 20)
    assert membership.restore_option(member) == "request"

    harness = BotHarness(member.telegram_id)
    await harness.send("/start")
    assert "📨" in harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0].text
    await harness.press("mem:restore")  # too late to restore alone: the request is offered again
    assert harness.session.sent_messages()[-1].reply_markup.inline_keyboard[0][0].callback_data == "mem:request"
    await harness.press("mem:request")
    assert harness.last_text() == texts.LEFT_REQUEST_SENT
    await harness.send("/start")
    assert harness.last_text() == texts.LEFT_REQUEST_WAITING

    request = await db.scalar(select(Notification).where(Notification.user_id == admin.id))
    assert "tiklash so'rovi" in request.text.lower() and "Karimova Aziza" in request.text
    callbacks = [button["callback"] for button in request.payload["buttons"][0]["row"]]
    assert callbacks == [f"mem:ok:{member.id.hex}", f"mem:no:{member.id.hex}"]

    plain = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    reader = BotHarness(plain.telegram_id)
    await reader.press(f"mem:ok:{member.id.hex}")
    assert reader.session.alerts()[-1] == texts.RESTORE_ADMIN_ONLY

    boss = BotHarness(admin.telegram_id)
    await boss.press(f"mem:ok:{member.id.hex}")
    await db.refresh(member)
    assert member.status == UserStatus.ACTIVE and member.restore_requested_at is None
    told = await db.scalar(
        select(Notification.text).where(
            Notification.user_id == member.id, Notification.dedup_key.like("membership:restored:%")
        )
    )
    assert "tiklandi" in told
    await boss.press(f"mem:ok:{member.id.hex}")  # a second admin presses the same button
    assert boss.session.alerts()[-1] == texts.RESTORE_DONE_ALREADY


async def test_declined_request_and_starting_anew(db: AsyncSession) -> None:
    member = await _member(db, phone="+998901112233")
    admin = await _manager(db)
    telegram_id = member.telegram_id
    await membership.leave(db, member, reason="SELF")
    await db.commit()
    await _left_days_ago(db, member, 16)
    await membership.request_restore(db, member)

    boss = BotHarness(admin.telegram_id)
    await boss.press(f"mem:no:{member.id.hex}")
    assert boss.last_text() == texts.RESTORE_DECLINED_ADMIN
    assert any(
        m.chat_id == telegram_id and m.text == texts.RESTORE_DECLINED_MEMBER for m in boss.session.sent_messages()
    )
    await db.refresh(member)
    assert member.erased_at is not None and member.telegram_id < 0 and member.phone is None

    # The Telegram account is free again: /start begins a new registration.
    harness = BotHarness(telegram_id)
    await harness.send("/start")
    assert texts.WELCOME_NEW in harness.all_text()

    # Starting anew by oneself (within 14 days) erases the old account straight away.
    other = await _member(db)
    await membership.leave(db, other, reason="SELF")
    await db.commit()
    again = BotHarness(other.telegram_id)
    await again.press("mem:fresh")
    assert again.last_text() == texts.FRESH_CONFIRM
    await again.press("mem:fresh:yes")
    assert texts.WELCOME_NEW in again.all_text()
    await db.refresh(other)
    assert other.erased_at is not None and other.first_name == "O'chirilgan"


async def test_leaving_by_oneself_and_staff_never_leave_automatically(db: AsyncSession) -> None:
    member = await _member(db)
    harness = BotHarness(member.telegram_id)
    await harness.press("mem:leave")
    assert harness.last_text() == texts.LEAVE_CONFIRM
    await harness.press("mem:leave:yes")
    assert harness.last_text() == texts.LEFT_DONE
    await db.refresh(member)
    assert member.status == UserStatus.LEFT and member.left_reason == "SELF"

    admin = await _manager(db)
    staff = BotHarness(admin.telegram_id)
    await staff.press("mem:leave:yes")
    assert staff.last_text() == texts.LEAVE_STAFF
    await staff.dispatcher.feed_update(staff.bot, _blocked(staff))
    await db.refresh(admin)
    assert admin.status == UserStatus.ACTIVE


async def test_sender_notices_a_blocked_bot(db: AsyncSession) -> None:
    member = await _member(db)
    await enqueue_notification(db, user_id=member.id, type_=NotificationType.SYSTEM, text="Yangi kitob")
    await enqueue_notification(
        db,
        user_id=member.id,
        type_=NotificationType.SYSTEM,
        text="Ertaga",
        dedup_key="later",
        scheduled_at=datetime.now(UTC) + timedelta(hours=5),
    )
    await db.commit()

    class Blocked(FakeTelegramSession):
        async def make_request(self, bot: Bot, method: Any, timeout: int | None = None) -> Any:  # noqa: ASYNC109
            raise TelegramForbiddenError(method, "Forbidden: bot was blocked by the user")

    bot = Bot(token=BOT_TOKEN, session=Blocked(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    report = await send_due_notifications(get_session_factory(), bot)
    assert report.blocked == [member.telegram_id]
    await db.refresh(member)
    assert member.status == UserStatus.LEFT and member.left_reason == "BOT_BLOCKED"
    later = await db.scalar(
        select(Notification.status).where(Notification.dedup_key == "later").execution_options(populate_existing=True)
    )
    assert later == NotificationStatus.SKIPPED


async def test_data_is_erased_after_a_month(db: AsyncSession) -> None:
    recent, old = await _member(db), await _member(db)
    for user in (recent, old):
        await membership.leave(db, user, reason="BOT_BLOCKED")
    await db.commit()
    await _left_days_ago(db, recent, 29)
    await _left_days_ago(db, old, 31)
    assert membership.restore_option(old) == "expired"

    harness = BotHarness(old.telegram_id)
    await harness.send("/start")
    assert harness.last_text() == texts.FRESH_CONFIRM

    assert await membership.erase_expired(db) == 1
    await db.commit()
    await db.refresh(old)
    await db.refresh(recent)
    assert old.erased_at is not None and old.first_name == "O'chirilgan" and old.telegram_username is None
    assert recent.erased_at is None
    # The anonymous row keeps the club's statistics.
    assert await db.scalar(select(func.sum(ScoreTransaction.amount)).where(ScoreTransaction.user_id == old.id)) == 25
    assert await membership.erase_expired(db) == 0


async def test_admin_cancel_restore_and_erase(client: httpx.AsyncClient, db: AsyncSession) -> None:
    member = await _member(db)
    admin = await _manager(db)
    headers = admin_headers(admin)
    base = f"/api/v1/admin/users/{member.id}"

    short = await client.post(f"{base}/cancel-membership", json={"reason": "yo"}, headers=headers)
    assert short.status_code == 422
    cancelled = await client.post(f"{base}/cancel-membership", json={"reason": "Qoidalarni buzdi"}, headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "LEFT"
    assert cancelled.json()["left_reason"] == "CANCELLED"
    told = await db.scalar(select(Notification).where(Notification.dedup_key.like("membership:cancelled:%")))
    assert "Qoidalarni buzdi" in told.text and told.payload["deliver_to_inactive"] is True
    twice = await client.post(f"{base}/cancel-membership", json={"reason": "Qoidalarni buzdi"}, headers=headers)
    assert twice.status_code == 409

    listed = (await client.get("/api/v1/admin/users?status=LEFT", headers=headers)).json()
    assert [row["id"] for row in listed["items"]] == [str(member.id)]
    restored = await client.post(f"{base}/restore", headers=headers)
    assert restored.status_code == 200 and restored.json()["status"] == "ACTIVE"

    other_admin = await _manager(db)
    protected = await client.post(
        f"/api/v1/admin/users/{other_admin.id}/cancel-membership", json={"reason": "Sinov uchun"}, headers=headers
    )
    assert protected.status_code == 403

    # Erasing is for the super administrator only, with a typed confirmation.
    erase_body = {"reason": "A'zoning o'z iltimosi", "confirm": "O'CHIRISH"}
    assert (await client.post(f"{base}/erase", json=erase_body, headers=headers)).status_code == 403
    boss = await create_user(db, telegram_id=next(_ids))
    await db.commit()
    await grant_role(db, boss, "SUPER_ADMIN")
    boss_headers = admin_headers(boss)
    wrong = await client.post(f"{base}/erase", json={**erase_body, "confirm": "ha"}, headers=boss_headers)
    assert wrong.status_code == 400
    assert (await client.post(f"{base}/erase", json=erase_body, headers=boss_headers)).status_code == 204
    await db.refresh(member)
    assert member.erased_at is not None and member.phone is None
    assert (await client.get(base, headers=boss_headers)).status_code == 404
    audit = await db.scalar(select(AuditLog).where(AuditLog.action == "USER_ERASE"))
    assert audit.reason == "A'zoning o'z iltimosi"
    itself = await client.post(f"/api/v1/admin/users/{boss.id}/erase", json=erase_body, headers=boss_headers)
    assert itself.status_code == 403
