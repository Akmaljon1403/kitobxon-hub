"""Typed registry of runtime-configurable settings.

Score values and other rules are never hard-coded in business logic: services read them
through :func:`get_setting`, administrators change them from the Admin Panel, and every
value is validated against the declared type before it is stored.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationFailedError
from app.models import SystemSetting
from app.services.audit import record_audit

Points = Annotated[int, Field(ge=0, le=1000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
ClockTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    default: Any
    type_: Any
    description: str
    choices: tuple[str, ...] = ()

    @property
    def group(self) -> str:
        return self.key.split(".", 1)[0]

    @property
    def kind(self) -> str:
        """Input type hint for the Admin Panel: bool, int, int_list, time, choice or text."""
        if self.choices:
            return "choice"
        if isinstance(self.default, bool):
            return "bool"
        if isinstance(self.default, int):
            return "int"
        if isinstance(self.default, list):
            return "int_list"
        if self.key.endswith("_time"):
            return "time"
        return "text"

    def validate(self, value: Any) -> Any:
        try:
            return TypeAdapter(self.type_).validate_python(value)
        except ValidationError as exc:
            raise ValidationFailedError(
                "INVALID_SETTING_VALUE",
                f"'{self.key}' sozlamasi uchun qiymat noto'g'ri.",
                details=[{"field": self.key, "reason": err["msg"]} for err in exc.errors()],
            ) from exc


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    # ---- Score rules (spec §28) ----
    SettingDefinition("score.attendance_points", 30, Points, "Tadbirda tasdiqlangan qatnashuv uchun ball"),
    SettingDefinition("score.test_max_points", 20, Annotated[int, Field(ge=1, le=1000)], "Test uchun maksimal ball"),
    SettingDefinition(
        "score.test_rank_bonus",
        [10, 5, 3],
        Annotated[list[Points], Field(min_length=0, max_length=10)],
        "Test bo'yicha 1-, 2-, 3-o'rinlar uchun qo'shimcha ball",
    ),
    SettingDefinition("score.book_completion_points", 10, Points, "Kitobni o'qib tugatgani uchun ball"),
    SettingDefinition(
        "score.book_completion_requires_verification",
        True,
        bool,
        "Kitob uchun ball faqat test yoki admin tasdig'idan keyin beriladi",
    ),
    # ---- Registration ----
    SettingDefinition(
        "registration.require_approval", False, bool, "Yangi a'zolar admin tasdig'idan so'ng faollashadi"
    ),
    SettingDefinition("registration.max_course", 6, Annotated[int, Field(ge=1, le=8)], "Eng yuqori kurs raqami"),
    # ---- Attendance ----
    SettingDefinition(
        "attendance.token_ttl_seconds",
        30,
        Annotated[int, Field(ge=10, le=600)],
        "QR/kodning amal qilish vaqti (soniya)",
    ),
    SettingDefinition(
        "attendance.rotation_seconds", 10, Annotated[int, Field(ge=5, le=300)], "QR/kod qanchada yangilanadi (soniya)"
    ),
    SettingDefinition(
        "attendance.require_registration", False, bool, "Davomat uchun tadbirga oldindan ro'yxatdan o'tish shart"
    ),
    # ---- Notifications ----
    SettingDefinition(
        "notifications.event_reminder_minutes",
        [1440, 60],
        Annotated[list[Annotated[int, Field(ge=5, le=10080)]], Field(max_length=5)],
        "Tadbirdan necha daqiqa oldin eslatma yuboriladi",
    ),
    SettingDefinition(
        "notifications.test_ending_minutes",
        60,
        Annotated[int, Field(ge=0, le=1440)],
        "Test yopilishidan necha daqiqa oldin eslatiladi (0 = eslatilmaydi)",
    ),
    SettingDefinition(
        "notifications.reading_reminder_days",
        2,
        Annotated[int, Field(ge=0, le=30)],
        "Kitob muddati tugashidan necha kun oldin eslatiladi (0 = eslatilmaydi)",
    ),
    SettingDefinition("notifications.quote_of_day_time", "09:00", ClockTime, "Kun iqtibosi yuboriladigan vaqt"),
    # ---- Organisation (used in official reports) ----
    SettingDefinition(
        "org.organization_name",
        "Farg'ona jamoat salomatligi tibbiyot instituti",
        ShortText,
        "Tashkilot (universitet) nomi",
    ),
    SettingDefinition("org.club_name", "Kitobxon Hub", ShortText, "Klub nomi"),
    # ---- Certificates ----
    SettingDefinition(
        "certificates.test_winners",
        True,
        bool,
        "Test g'oliblariga (1-3-o'rin) sertifikat avtomatik beriladi (tadbir testida — faqat davomatdan o'tganlarga)",
    ),
    SettingDefinition(
        "certificates.monthly_top", True, bool, "Oy yakunida reytingdagi 1-3-o'rinlarga sertifikat beriladi"
    ),
    SettingDefinition("certificates.signer_title", "Klub rahbari", ShortText, "Sertifikatdagi imzo egasi lavozimi"),
    SettingDefinition("certificates.signer_name", "", ShortText, "Sertifikatdagi imzo egasining ismi (ixtiyoriy)"),
    # ---- Privacy ----
    SettingDefinition(
        "ranking.public_name_format",
        "SHORT",
        Literal["FULL", "SHORT"],
        "Umumiy reytingda ism ko'rinishi: FULL = to'liq, SHORT = ism va familiyaning bosh harfi",
        choices=("FULL", "SHORT"),
    ),
)

SETTINGS_BY_KEY: dict[str, SettingDefinition] = {definition.key: definition for definition in SETTING_DEFINITIONS}


def get_definition(key: str) -> SettingDefinition:
    try:
        return SETTINGS_BY_KEY[key]
    except KeyError as exc:
        raise NotFoundError("SETTING_NOT_FOUND", "Bunday sozlama mavjud emas.") from exc


async def get_setting(session: AsyncSession, key: str) -> Any:
    """Current value of a setting, falling back to its default (and validating stored data)."""
    definition = get_definition(key)
    stored = await session.scalar(select(SystemSetting.value).where(SystemSetting.key == key))
    if stored is None:
        return definition.default
    try:
        return definition.validate(stored)
    except ValidationFailedError:
        # A malformed stored value must never break scoring; use the safe default.
        return definition.default


async def get_all_settings(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.execute(select(SystemSetting.key, SystemSetting.value))).all()
    stored = dict(rows)
    result: dict[str, Any] = {}
    for definition in SETTING_DEFINITIONS:
        value = stored.get(definition.key, definition.default)
        try:
            result[definition.key] = definition.validate(value)
        except ValidationFailedError:
            result[definition.key] = definition.default
    return result


async def update_setting(session: AsyncSession, *, key: str, value: Any, actor_id: uuid.UUID) -> Any:
    """Validate and store a new value; the change is written to the audit log."""
    definition = get_definition(key)
    validated = definition.validate(value)
    before = await get_setting(session, key)
    statement = insert(SystemSetting).values(
        key=key, value=validated, description=definition.description, updated_by=actor_id
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[SystemSetting.key], set_={"value": validated, "updated_by": actor_id}
        )
    )
    record_audit(
        session,
        actor_id=actor_id,
        action="SETTING_CHANGE",
        entity_type="setting",
        entity_id=key,
        before={"value": before},
        after={"value": validated},
    )
    await session.commit()
    return validated
