"""Member administration and self-service profile changes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.models import Faculty, User, UserNotificationSettings
from app.models.enums import NotificationType, SystemRole, UserStatus
from app.services.audit import record_audit
from app.services.members import get_active_faculty, normalize_group, normalize_name, validate_course
from app.services.notifications import enqueue_notification
from app.services.rbac import ADMIN_ROLES, get_role_codes

NOTIFICATION_FIELDS = (
    "event_reminders",
    "test_reminders",
    "reading_reminders",
    "quote_of_day",
    "ranking_updates",
    "achievement_alerts",
)


@dataclass(frozen=True)
class UserFilters:
    search: str | None = None
    status: UserStatus | None = None
    faculty_id: uuid.UUID | None = None
    course: int | None = None
    group_name: str | None = None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_filters(query: Select, filters: UserFilters, *, allow_phone_search: bool) -> Select:
    query = query.where(User.deleted_at.is_(None))
    if filters.search:
        term = f"%{_escape_like(filters.search.strip())}%"
        conditions = [
            func.concat(User.first_name, " ", User.last_name).ilike(term),
            func.concat(User.last_name, " ", User.first_name).ilike(term),
            User.telegram_username.ilike(term),
            User.group_name.ilike(term),
        ]
        if allow_phone_search:
            conditions.append(User.phone.ilike(term))
        query = query.where(or_(*conditions))
    if filters.status:
        query = query.where(User.status == filters.status)
    if filters.faculty_id:
        query = query.where(User.faculty_id == filters.faculty_id)
    if filters.course:
        query = query.where(User.course == filters.course)
    if filters.group_name:
        query = query.where(User.group_name == filters.group_name.strip().upper())
    return query


async def list_users(
    session: AsyncSession, *, filters: UserFilters, limit: int, offset: int, allow_phone_search: bool
) -> tuple[list[tuple[User, str | None]], int]:
    base = _apply_filters(select(User.id), filters, allow_phone_search=allow_phone_search)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    query = _apply_filters(
        select(User, Faculty.name).outerjoin(Faculty, Faculty.id == User.faculty_id),
        filters,
        allow_phone_search=allow_phone_search,
    )
    rows = await session.execute(
        query.order_by(User.registered_at.desc().nulls_last(), User.id).limit(limit).offset(offset)
    )
    return [(user, faculty_name) for user, faculty_name in rows], int(total or 0)


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("USER_NOT_FOUND", "Foydalanuvchi topilmadi.")
    return user


async def faculty_name(session: AsyncSession, faculty_id: uuid.UUID | None) -> str | None:
    if faculty_id is None:
        return None
    return await session.scalar(select(Faculty.name).where(Faculty.id == faculty_id))


def _profile_snapshot(user: User) -> dict[str, Any]:
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "faculty_id": str(user.faculty_id) if user.faculty_id else None,
        "course": user.course,
        "group_name": user.group_name,
    }


async def _apply_profile_changes(session: AsyncSession, user: User, changes: dict[str, Any]) -> None:
    if "first_name" in changes:
        user.first_name = normalize_name(changes["first_name"], "first_name")
    if "last_name" in changes:
        user.last_name = normalize_name(changes["last_name"], "last_name")
    if "faculty_id" in changes:
        faculty_id = changes["faculty_id"]
        if faculty_id is not None:
            await get_active_faculty(session, faculty_id)
        user.faculty_id = faculty_id
    if "course" in changes:
        user.course = await validate_course(session, changes["course"])
    if "group_name" in changes:
        user.group_name = normalize_group(changes["group_name"])


async def update_my_profile(session: AsyncSession, user: User, changes: dict[str, Any]) -> User:
    """Members may correct their faculty, course and group themselves (names are changed by admins)."""
    allowed = {key: value for key, value in changes.items() if key in {"faculty_id", "course", "group_name"}}
    if "faculty_id" in allowed and allowed["faculty_id"] is None:
        raise BadRequestError("FACULTY_REQUIRED", "Fakultetni tanlang.")
    await _apply_profile_changes(session, user, allowed)
    await session.commit()
    return user


async def admin_update_user(
    session: AsyncSession, *, actor_id: uuid.UUID, user_id: uuid.UUID, changes: dict[str, Any]
) -> User:
    user = await get_user(session, user_id)
    before = _profile_snapshot(user)
    await _apply_profile_changes(session, user, changes)
    after = _profile_snapshot(user)
    if before != after:
        record_audit(
            session,
            actor_id=actor_id,
            action="USER_UPDATE",
            entity_type="user",
            entity_id=user.id,
            before=before,
            after=after,
        )
    await session.commit()
    return user


_STATUS_ACTIONS = {
    UserStatus.ACTIVE: "USER_ACTIVATE",
    UserStatus.BLOCKED: "USER_BLOCK",
    UserStatus.INACTIVE: "USER_DEACTIVATE",
}


async def change_user_status(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    actor_roles: set[str],
    user_id: uuid.UUID,
    status: UserStatus,
    reason: str,
) -> User:
    if status == UserStatus.PENDING:
        raise BadRequestError("INVALID_STATUS", "A'zoni qayta «kutilmoqda» holatiga o'tkazib bo'lmaydi.")
    if status == UserStatus.LEFT:
        raise BadRequestError(
            "INVALID_STATUS", "A'zolikni bekor qilish uchun «A'zolikni bekor qilish» tugmasidan foydalaning."
        )
    if user_id == actor_id:
        raise ForbiddenError("SELF_STATUS_CHANGE", "O'z hisobingiz holatini o'zgartira olmaysiz.")
    user = await get_user(session, user_id)
    target_roles = await get_role_codes(session, user_id)
    if target_roles & ADMIN_ROLES and SystemRole.SUPER_ADMIN.value not in actor_roles:
        raise ForbiddenError("ADMIN_PROTECTED", "Administrator holatini faqat bosh administrator o'zgartira oladi.")
    if user.status == status:
        return user

    previous = user.status
    user.status = status
    if previous == UserStatus.LEFT:  # coming back through the status switch: forget the leaving
        user.left_at = user.left_reason = user.restore_requested_at = None
    if status != UserStatus.ACTIVE:
        user.token_version += 1  # end every session of the member immediately
    record_audit(
        session,
        actor_id=actor_id,
        action=_STATUS_ACTIONS[status],
        entity_type="user",
        entity_id=user.id,
        before={"status": previous.value},
        after={"status": status.value},
        reason=reason,
    )
    await session.commit()
    if previous == UserStatus.PENDING and status == UserStatus.ACTIVE:
        from app.services.premium import welcome_trial
        from app.utils.timezone import format_date

        text = "✅ Arizangiz tasdiqlandi! Endi Kitobxon Hub'dan to'liq foydalanishingiz mumkin."
        trial = await welcome_trial(session, user)
        await session.refresh(user)
        if trial is not None:
            text += (
                f"\n\n🎁 Sovg'a: {(trial.ends_at - trial.starts_at).days} kunlik Premium yoqildi — "
                f"{format_date(trial.ends_at)} gacha bepul. Imkoniyatlarni ilovada ko'ring."
            )
        await enqueue_notification(
            session,
            user_id=user.id,
            type_=NotificationType.SYSTEM,
            text=text + "\n\n/start",
            dedup_key=f"user_approved:{user.id}",
            priority=1,
        )
        await session.commit()
    return user


async def get_notification_settings(session: AsyncSession, user_id: uuid.UUID) -> UserNotificationSettings:
    settings = await session.get(UserNotificationSettings, user_id)
    if settings is None:
        settings = UserNotificationSettings(user_id=user_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_notification_settings(
    session: AsyncSession, user_id: uuid.UUID, changes: dict[str, bool]
) -> UserNotificationSettings:
    settings = await get_notification_settings(session, user_id)
    for field, value in changes.items():
        if field in NOTIFICATION_FIELDS and value is not None:
            setattr(settings, field, bool(value))
    await session.commit()
    await session.refresh(settings)
    return settings
