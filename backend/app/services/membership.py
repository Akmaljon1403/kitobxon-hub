"""Leaving the club, coming back, and erasing personal data.

* A member who blocks the bot (or whose membership an admin cancels, or who leaves by themselves)
  becomes ``LEFT``: hidden from rankings and lists, no messages, every session ends.
* Within 14 days they can restore everything by themselves (/start → «♻️ Tiklash»); within 30 days
  they can ask the admins to restore it; after 30 days the personal data is erased automatically.
* Erasing keeps the anonymous row for the club's statistics (points, attendance) but removes the
  name, phone, Telegram account, photos, receipts and messages. The person can register again.
* Club administrators never leave automatically (blocking the bot by mistake must not cost the club
  its admins); a super administrator can still cancel or erase any other account.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models import (
    BotFsmState,
    CardPayment,
    Certificate,
    Notification,
    SupportMessage,
    SupportTicket,
    User,
    UserNotificationSettings,
)
from app.models.enums import NotificationStatus, NotificationType, UserStatus
from app.services.audit import record_audit
from app.services.notifications import enqueue_for_members, enqueue_notification, render
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

SELF_RESTORE_DAYS = 14
REQUEST_RESTORE_DAYS = 30
Reason = Literal["BOT_BLOCKED", "CANCELLED", "SELF"]
RestoreOption = Literal["self", "request", "expired"]


def _now() -> datetime:
    return datetime.now(UTC)


def restore_option(user: User, now: datetime | None = None) -> RestoreOption | None:
    """What a returning member can do: restore by themselves, ask the admins, or start anew."""
    if user.status != UserStatus.LEFT or user.left_at is None or user.erased_at is not None:
        return None
    days = ((now or _now()) - user.left_at).total_seconds() / 86400
    if days <= SELF_RESTORE_DAYS:
        return "self"
    if days <= REQUEST_RESTORE_DAYS:
        return "request"
    return "expired"


async def _is_staff(session: AsyncSession, user_id: uuid.UUID) -> bool:
    from app.services.rbac import get_role_codes, is_admin_role_set

    return is_admin_role_set(await get_role_codes(session, user_id))


async def leave(
    session: AsyncSession,
    user: User,
    *,
    reason: Reason,
    actor_id: uuid.UUID | None = None,
    note: str | None = None,
) -> bool:
    """The member leaves the club (the data is kept for 30 days). Returns False if nothing changed.
    The caller commits."""
    if user.erased_at is not None or user.status == UserStatus.LEFT:
        return False
    if reason == "BOT_BLOCKED" and await _is_staff(session, user.id):
        return False
    if user.registered_at is None:
        # Never finished the registration: nothing worth keeping.
        await erase(session, user, actor_id=actor_id, reason="registratsiya tugallanmagan", commit=False)
        return True
    previous = user.status
    user.status = UserStatus.LEFT
    user.left_at = _now()
    user.left_reason = reason
    user.restore_requested_at = None
    user.token_version += 1  # sign out of the Mini App and the Admin Panel everywhere
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.status == NotificationStatus.PENDING)
        .values(status=NotificationStatus.SKIPPED, last_error="member left the club")
    )
    record_audit(
        session,
        actor_id=actor_id or user.id,
        action="MEMBERSHIP_LEFT",
        entity_type="user",
        entity_id=user.id,
        before={"status": str(previous)},
        after={"status": UserStatus.LEFT.value, "reason": reason},
        reason=note,
    )
    if reason == "CANCELLED":
        text = (
            "A'zoligingiz klub rahbariyati tomonidan bekor qilindi."
            + (f"\nSabab: {note}" if note else "")
            + f"\n\n{REQUEST_RESTORE_DAYS} kun ichida /start bosib, tiklash so'rovini yuborishingiz mumkin."
        )
        await _tell(session, user.id, text, f"membership:cancelled:{user.id}:{user.left_at:%Y%m%d%H%M}", force=True)
    return True


async def _tell(session: AsyncSession, user_id: uuid.UUID, message: str, key: str, *, force: bool = False) -> None:
    """``force``: delivered although the member is no longer active (the sender skips such members)."""
    text = await render(session, NotificationType.SYSTEM, message=message) or message
    await enqueue_notification(
        session,
        user_id=user_id,
        type_=NotificationType.SYSTEM,
        text=text,
        dedup_key=key,
        payload={"deliver_to_inactive": True} if force else None,
        priority=1,
    )


async def restore(session: AsyncSession, user: User, *, actor_id: uuid.UUID | None = None) -> User:
    """Back to the club with everything as it was (points, certificates, Premium)."""
    if user.status != UserStatus.LEFT or user.erased_at is not None:
        raise ConflictError("NOT_LEFT", "Bu a'zo klubdan chiqmagan yoki ma'lumotlari o'chirilgan.")
    user.status = UserStatus.ACTIVE
    user.left_at = None
    user.left_reason = None
    user.restore_requested_at = None
    record_audit(
        session,
        actor_id=actor_id or user.id,
        action="MEMBERSHIP_RESTORED",
        entity_type="user",
        entity_id=user.id,
        after={"by": "admin" if actor_id and actor_id != user.id else "self"},
    )
    if actor_id and actor_id != user.id:
        await _tell(
            session,
            user.id,
            "♻️ A'zoligingiz tiklandi! Ballaringiz, sertifikatlaringiz va barcha natijalaringiz joyida. "
            "Qaytganingizdan xursandmiz — /start",
            f"membership:restored:{user.id}:{_now():%Y%m%d%H%M}",
        )
    await _settle_restore(session, user.id, actor_id, "♻️ <b>Tiklandi</b>")
    await session.commit()
    return user


async def _settle_restore(session: AsyncSession, user_id: uuid.UUID, actor_id: uuid.UUID | None, what: str) -> None:
    """Every admin's copy of the restore request shows the decision."""
    from app.services import copies

    who = await copies.admin_name(session, actor_id) if actor_id and actor_id != user_id else "a'zoning o'zi"
    await copies.settle(session, f"restore:{user_id}", f"{what} — {who}, {copies.stamp()}", buttons=[])


async def request_restore(session: AsyncSession, user: User) -> None:
    """14–30 days after leaving: the admins decide (USER_MANAGE)."""
    from app.services.rbac import admins_with_permission

    if restore_option(user) != "request":
        raise ConflictError("RESTORE_NOT_AVAILABLE", "Tiklash so'rovini yuborish muddati o'tgan.")
    if user.restore_requested_at is not None:
        return
    user.restore_requested_at = _now()
    days = (_now() - user.left_at).days if user.left_at else 0
    text = (
        f"♻️ <b>A'zolikni tiklash so'rovi</b>\n\n{user.last_name} {user.first_name}"
        + (f" (@{user.telegram_username})" if user.telegram_username else "")
        + f"\n{days} kun oldin klubdan chiqqan. Ma'lumotlari (ballar, sertifikatlar) tiklansinmi?"
    )
    from app.security.permissions import Perm

    await enqueue_for_members(
        session,
        type_=NotificationType.SYSTEM,
        text=text,
        dedup_prefix=f"restore-request:{user.id}:{user.restore_requested_at:%Y%m%d}",
        members=admins_with_permission(Perm.USER_MANAGE),
        sync=f"restore:{user.id}",
        payload={
            "base": text,
            "buttons": [
                {
                    "row": [
                        {"text": "✅ Tiklash", "callback": f"mem:ok:{user.id.hex}"},
                        {"text": "❌ Rad etish", "callback": f"mem:no:{user.id.hex}"},
                    ]
                }
            ],
        },
        priority=2,
    )
    record_audit(session, actor_id=user.id, action="MEMBERSHIP_RESTORE_REQUEST", entity_type="user", entity_id=user.id)
    await session.commit()


async def decline_restore(session: AsyncSession, user: User, *, actor_id: uuid.UUID) -> None:
    """The admins said no: the old data is erased; the person may register anew."""
    if user.status != UserStatus.LEFT or user.erased_at is not None:
        raise ConflictError("NOT_LEFT", "Bu a'zo klubdan chiqmagan yoki ma'lumotlari o'chirilgan.")
    telegram_id = user.telegram_id
    await _settle_restore(session, user.id, actor_id, "❌ <b>Rad etildi</b> (ma'lumotlari o'chirildi)")
    await erase(session, user, actor_id=actor_id, reason="tiklash so'rovi rad etildi", commit=False)
    await session.commit()
    logger.info("Restore declined; the account was erased (telegram id kept private: %s)", bool(telegram_id))


async def erase(
    session: AsyncSession, user: User, *, actor_id: uuid.UUID | None, reason: str, commit: bool = True
) -> None:
    """Remove the personal data for good. The anonymous row stays for the club's statistics."""
    if user.erased_at is not None:
        return
    storage = get_storage()
    keys = [user.passport_photo_key] if user.passport_photo_key else []
    receipts = list(await session.scalars(select(CardPayment).where(CardPayment.user_id == user.id)))
    keys += [payment.receipt_key for payment in receipts if payment.receipt_key]
    certificates = list(await session.scalars(select(Certificate).where(Certificate.user_id == user.id)))
    keys += [certificate.file_key for certificate in certificates if certificate.file_key]
    for key in keys:
        try:
            await storage.delete(key)
        except Exception:  # a missing file is fine: it is gone either way
            logger.info("Erase: could not delete a stored file")
    for payment in receipts:
        payment.receipt_key = "erased"
    for certificate in certificates:
        certificate.file_key = None  # drawn again (with the anonymous name) if ever checked

    telegram_id = user.telegram_id
    await session.execute(delete(BotFsmState).where(BotFsmState.key.op("~")(f":{telegram_id}(:|$)")))
    await session.execute(delete(UserNotificationSettings).where(UserNotificationSettings.user_id == user.id))
    await session.execute(delete(Notification).where(Notification.user_id == user.id))
    # What the member wrote in their own words goes too (the reading diary stays as anonymous numbers).
    from app.models import BookReflection, Contribution, Mission, SavedQuote

    await session.execute(delete(Contribution).where(Contribution.user_id == user.id))
    await session.execute(delete(SavedQuote).where(SavedQuote.user_id == user.id))
    await session.execute(delete(BookReflection).where(BookReflection.user_id == user.id))
    await session.execute(delete(Mission).where(Mission.owner_id == user.id))  # their own missions
    tickets = select(SupportTicket.id).where(SupportTicket.user_id == user.id)
    await session.execute(
        update(SupportMessage)
        .where(SupportMessage.ticket_id.in_(tickets), SupportMessage.from_admin.is_(False))
        .values(text="[o'chirilgan]", photo_file_id=None)
    )
    now = _now()
    user.first_name = "O'chirilgan"
    user.last_name = "a'zo"
    user.telegram_username = None
    user.phone = None
    user.photo_url = None
    user.passport_photo_key = None
    user.passport_theme = None
    user.group_name = None
    user.referred_by = None
    user.restore_requested_at = None
    user.telegram_id = -user.member_number  # frees the Telegram account for a new registration
    user.status = UserStatus.LEFT
    user.left_at = user.left_at or now
    user.erased_at = now
    user.deleted_at = now
    user.token_version += 1
    record_audit(
        session,
        actor_id=actor_id,
        action="USER_ERASE",
        entity_type="user",
        entity_id=user.id,
        after={"member_number": user.member_number},
        reason=reason,
    )
    if commit:
        await session.commit()


async def admin_erase(session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> None:
    from app.services.rbac import get_role_codes

    if user_id == actor_id:
        raise ForbiddenError("SELF_ERASE", "O'z ma'lumotlaringizni bu yerdan o'chira olmaysiz.")
    user = await session.get(User, user_id)
    if user is None or user.erased_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    if "SUPER_ADMIN" in await get_role_codes(session, user_id):
        raise ForbiddenError("ADMIN_PROTECTED", "Bosh administratorning ma'lumotlarini o'chirib bo'lmaydi.")
    if len(reason.strip()) < 5:
        raise BadRequestError("REASON_REQUIRED", "Sababini yozing.")
    await erase(session, user, actor_id=actor_id, reason=reason.strip())


async def admin_cancel(session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, reason: str) -> User:
    if user_id == actor_id:
        raise ForbiddenError("SELF_STATUS_CHANGE", "O'z a'zoligingizni bekor qila olmaysiz.")
    user = await session.get(User, user_id)
    if user is None or user.erased_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "A'zo topilmadi.")
    from app.services.rbac import ADMIN_ROLES, get_role_codes

    if await get_role_codes(session, user_id) & ADMIN_ROLES:
        raise ForbiddenError("ADMIN_PROTECTED", "Avval administrator huquqlarini olib qo'ying.")
    if not await leave(session, user, reason="CANCELLED", actor_id=actor_id, note=reason.strip() or None):
        raise ConflictError("ALREADY_LEFT", "Bu a'zo allaqachon klubdan chiqqan.")
    await session.commit()
    return user


async def on_bot_blocked(session: AsyncSession, telegram_id: int) -> bool:
    """Telegram told us the member blocked the bot. The caller commits."""
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id, User.deleted_at.is_(None)))
    if user is None:
        return False
    return await leave(session, user, reason="BOT_BLOCKED")


async def erase_expired(session: AsyncSession, now: datetime | None = None) -> int:
    """Scheduler job: members who left more than 30 days ago lose their personal data."""
    limit = (now or _now()) - timedelta(days=REQUEST_RESTORE_DAYS)
    expired = list(
        await session.scalars(
            select(User).where(User.status == UserStatus.LEFT, User.erased_at.is_(None), User.left_at < limit)
        )
    )
    for user in expired:
        await erase(session, user, actor_id=None, reason=f"{REQUEST_RESTORE_DAYS} kundan beri qaytmadi", commit=False)
    return len(expired)
