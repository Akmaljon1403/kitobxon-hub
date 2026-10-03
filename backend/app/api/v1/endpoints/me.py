"""The signed-in member's own data."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession
from app.models import Faculty, UserNotificationSettings
from app.schemas.user import FacultyOut, MeOut, MeUpdateIn, NotificationSettingsIn, NotificationSettingsOut
from app.services import features, premium
from app.services import users as user_service
from app.services.passport import member_number
from app.services.settings import get_setting

router = APIRouter(prefix="/me", tags=["me"])


async def _me(current, db) -> MeOut:
    user = current.user
    faculty = await db.get(Faculty, user.faculty_id) if user.faculty_id else None
    return MeOut(
        id=user.id,
        member_number=member_number(user),
        first_name=user.first_name,
        last_name=user.last_name,
        telegram_username=user.telegram_username,
        photo_url=user.photo_url,
        phone=user.phone,
        faculty=FacultyOut(id=faculty.id, name=faculty.name, short_name=faculty.short_name) if faculty else None,
        course=user.course,
        group_name=user.group_name,
        status=user.status,
        registered_at=user.registered_at,
        is_admin=current.is_admin,
        roles=sorted(current.roles),
        max_course=await get_setting(db, "registration.max_course"),
        features=await features.access(db, user),
        is_premium=await premium.is_premium(db, user.id),
        premium_until=await premium.premium_until(db, user.id),
        passport_photo=user.passport_photo_key is not None,
    )


@router.get("", response_model=MeOut, summary="My profile")
async def get_me(current: CurrentUserDep, db: DbSession) -> MeOut:
    return await _me(current, db)


@router.patch("", response_model=MeOut, summary="Correct my faculty, course or group")
async def update_me(payload: MeUpdateIn, current: CurrentUserDep, db: DbSession) -> MeOut:
    await user_service.update_my_profile(db, current.user, payload.model_dump(exclude_unset=True))
    return await _me(current, db)


def _settings_out(settings: UserNotificationSettings) -> NotificationSettingsOut:
    return NotificationSettingsOut(**{field: getattr(settings, field) for field in user_service.NOTIFICATION_FIELDS})


@router.get("/notification-settings", response_model=NotificationSettingsOut, summary="My reminder preferences")
async def get_notification_settings(current: CurrentUserDep, db: DbSession) -> NotificationSettingsOut:
    return _settings_out(await user_service.get_notification_settings(db, current.user.id))


@router.put("/notification-settings", response_model=NotificationSettingsOut, summary="Change reminder preferences")
async def update_notification_settings(
    payload: NotificationSettingsIn, current: CurrentUserDep, db: DbSession
) -> NotificationSettingsOut:
    settings = await user_service.update_notification_settings(
        db, current.user.id, payload.model_dump(exclude_unset=True)
    )
    return _settings_out(settings)
