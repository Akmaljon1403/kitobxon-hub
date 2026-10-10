"""Member registration and validation of personal data.

Used by the Telegram bot (registration) and later by the profile API, so the same
rules apply everywhere.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationFailedError
from app.models import Faculty, PremiumSubscription, User, UserNotificationSettings
from app.models.enums import UserStatus
from app.services.audit import record_audit
from app.services.rbac import ensure_bootstrap_super_admin
from app.services.settings import get_setting

# Latin and Cyrillic letters (including Uzbek ʻ ’ ' ‘ forms), spaces and hyphens.
_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁёЎўҚқҒғҲҳʻʼ'’‘`\- ]{2,64}$")
_GROUP_RE = re.compile(r"^[A-Z0-9А-ЯЁЎҚҒҲ][A-Z0-9А-ЯЁЎҚҒҲ\-/ ]{0,15}$")
_PHONE_RE = re.compile(r"^\+\d{9,15}$")

logger = logging.getLogger(__name__)


def normalize_name(raw: str, field: str = "name") -> str:
    value = re.sub(r"\s+", " ", (raw or "").strip())
    value = value.replace("`", "'")
    if not _NAME_RE.match(value):
        raise ValidationFailedError(
            "INVALID_NAME",
            "Iltimos, faqat harflardan iborat bo'lgan to'g'ri qiymat kiriting (2–64 belgi).",
            details=[{"field": field, "reason": "letters only, 2-64 characters"}],
        )
    # Capitalise the first letter without touching the rest ("o'g'iloy" -> "O'g'iloy").
    return value[0].upper() + value[1:]


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"[^\d]", "", raw or "")
    value = f"+{digits}"
    if not _PHONE_RE.match(value):
        raise ValidationFailedError("INVALID_PHONE", "Telefon raqami noto'g'ri.")
    return value


def normalize_group(raw: str) -> str:
    value = re.sub(r"\s+", " ", (raw or "").strip()).upper()
    if not _GROUP_RE.match(value):
        raise ValidationFailedError(
            "INVALID_GROUP",
            "Guruh nomi noto'g'ri. Masalan: 301, 301-A yoki 2-guruh (16 belgigacha).",
        )
    return value


async def validate_course(session: AsyncSession, course: int) -> int:
    max_course = await get_setting(session, "registration.max_course")
    if not 1 <= course <= max_course:
        raise ValidationFailedError("INVALID_COURSE", f"Kurs 1 dan {max_course} gacha bo'lishi kerak.")
    return course


async def list_active_faculties(session: AsyncSession) -> list[Faculty]:
    rows = await session.scalars(
        select(Faculty).where(Faculty.is_active.is_(True)).order_by(Faculty.sort_order, Faculty.name)
    )
    return list(rows)


async def get_active_faculty(session: AsyncSession, faculty_id: uuid.UUID) -> Faculty:
    faculty = await session.get(Faculty, faculty_id)
    if faculty is None or not faculty.is_active:
        raise ValidationFailedError("INVALID_FACULTY", "Fakultet topilmadi. Ro'yxatdan qayta tanlang.")
    return faculty


async def phone_belongs_to_other_user(session: AsyncSession, phone: str, telegram_id: int) -> bool:
    owner = await session.scalar(select(User.telegram_id).where(User.phone == phone))
    return owner is not None and owner != telegram_id


@dataclass(frozen=True)
class RegistrationData:
    telegram_id: int
    telegram_username: str | None
    language_code: str | None
    first_name: str
    last_name: str
    phone: str
    faculty_id: uuid.UUID | None
    course: int
    group_name: str


async def register_member(session: AsyncSession, data: RegistrationData) -> User:
    """Create the member account. Every field is validated again here (never trust the caller)."""
    first_name = normalize_name(data.first_name, "first_name")
    last_name = normalize_name(data.last_name, "last_name")
    phone = normalize_phone(data.phone)
    group_name = normalize_group(data.group_name)
    course = await validate_course(session, data.course)
    if data.faculty_id is not None:
        await get_active_faculty(session, data.faculty_id)

    existing = await session.scalar(select(User).where(User.telegram_id == data.telegram_id))
    if existing is not None:
        raise ConflictError("ALREADY_REGISTERED", "Siz allaqachon ro'yxatdan o'tgansiz.")
    if await phone_belongs_to_other_user(session, phone, data.telegram_id):
        raise ConflictError(
            "PHONE_IN_USE", "Bu telefon raqami boshqa hisobga bog'langan. Klub rahbariyatiga murojaat qiling."
        )

    requires_approval = await get_setting(session, "registration.require_approval")
    is_owner = data.telegram_id in get_settings().super_admin_telegram_ids
    user = User(
        telegram_id=data.telegram_id,
        telegram_username=data.telegram_username,
        language_code=(data.language_code or "uz")[:8],
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        faculty_id=data.faculty_id,
        course=course,
        group_name=group_name,
        status=UserStatus.PENDING if requires_approval and not is_owner else UserStatus.ACTIVE,
        registered_at=datetime.now(UTC),
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:  # a parallel request registered the same account or phone
        await session.rollback()
        raise ConflictError("ALREADY_REGISTERED", "Siz allaqachon ro'yxatdan o'tgansiz.") from exc

    session.add(UserNotificationSettings(user_id=user.id))
    record_audit(
        session,
        actor_id=user.id,
        action="USER_REGISTER",
        entity_type="user",
        entity_id=user.id,
        after={"status": user.status.value, "faculty_id": str(user.faculty_id) if user.faculty_id else None},
    )
    await ensure_bootstrap_super_admin(session, user)
    await session.commit()
    return user


async def after_registration(session: AsyncSession, user_id: uuid.UUID) -> PremiumSubscription | None:
    """Welcome gifts after a member registered: the free Premium trial (switched on by itself), then
    «first N members» giveaways. Never breaks the registration itself. Returns the trial, if given."""
    from app.services import giveaways, premium

    trial = None
    user = await session.get(User, user_id)
    if user is not None and user.status == UserStatus.ACTIVE:
        trial = await premium.welcome_trial(session, user)
    try:
        await giveaways.on_member_joined(session, user_id)
    except Exception:
        await session.rollback()
        logger.exception("Welcome gifts failed for %s", user_id)
    if user is not None:
        await session.refresh(user)  # a failed gift rolled back and expired the member's data
    return trial
