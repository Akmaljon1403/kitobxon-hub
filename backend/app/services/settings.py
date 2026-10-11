"""Typed registry of runtime-configurable settings.

Score values and other rules are never hard-coded in business logic: services read them
through :func:`get_setting`, administrators change them from the Admin Panel, and every
value is validated against the declared type before it is stored.
"""

from __future__ import annotations

import copy
import logging
import time
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

logger = logging.getLogger(__name__)

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


BOT_SHORT_DESCRIPTION = (
    "📚 Kitobxonlar klubi: kitoblar, tadbirlar, testlar, reyting va sertifikatlar — hammasi bitta botda."
)
BOT_DESCRIPTION = (
    "📚 Kitobxon Hub — Farg'ona jamoat salomatligi tibbiyot instituti kitobxonlar klubining rasmiy boti.\n\n"
    "✨ Bu yerda siz:\n"
    "• klub kitoblarini o'qiysiz va muddatlarni kuzatasiz;\n"
    "• tadbirlarda QR kod bilan davomat qilasiz;\n"
    "• kitoblar bo'yicha testlar yechasiz;\n"
    "• ball, reyting, yutuq va sertifikatlar olasiz;\n"
    "• o'z Kitobxon pasportingizga ega bo'lasiz.\n\n"
    "👇 Boshlash uchun «Start» tugmasini bosing."
)


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
    SettingDefinition(
        "admin.morning_digest",
        True,
        bool,
        "Har kuni soat 08:00 da bosh administratorlarga qisqa hisobot: yangi a'zolar, tekshirilmagan cheklar, "
        "javobsiz murojaatlar, tasdiq kutayotgan davomat va bugungi tadbirlar",
    ),
    SettingDefinition(
        "notifications.quiet_hours",
        "22:00-08:00",
        Annotated[str, StringConstraints(pattern=r"^$|^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")],
        "Tungi tinchlik (SS:DD-SS:DD): shu vaqtda ommaviy xabarlar (e'lonlar, yangi kitob va tadbirlar, "
        "yutuqlar, haftalik xulosa) yuborilmaydi — ertalab boradi. Shaxsiy va shoshilinch xabarlar (davomat, "
        "to'lov, test natijasi) har doim boradi. Bo'sh — o'chiq",
    ),
    SettingDefinition(
        "notifications.stickers",
        False,
        bool,
        "Tabrik xabarlaridan keyin alohida stiker ham yuborilsin (odatda o'chiq: premium emojilar xabar ichida "
        "— botda /emoji). 🎉 animatsiya baribir qoladi",
    ),
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
    SettingDefinition(
        "certificates.seal", True, bool, "Sertifikatda imzo ustida klub pechati (app/brand/seal.png bo'lsa)"
    ),
    SettingDefinition(
        "certificates.logo", True, bool, "Sertifikat tepasida klub belgisi (app/brand/logo-mark.png bo'lsa)"
    ),
    SettingDefinition(
        "certificates.free_downloads",
        1,
        Annotated[int, Field(ge=0, le=20)],
        "Premiumsiz a'zo har bir sertifikatini necha marta bepul yuklab oladi (Premium — cheklovsiz)",
    ),
    SettingDefinition(
        "certificates.design_changes",
        3,
        Annotated[int, Field(ge=0, le=50)],
        "Premium a'zo bitta sertifikat dizaynini necha marta almashtira oladi",
    ),
    # ---- Card payments (Premium paid to the club's card, confirmed by the super admin) ----
    SettingDefinition(
        "payments.card_number", "", ShortText, "Klub kartasi raqami (Uzcard/Humo), masalan 8600 1234 5678 9012"
    ),
    SettingDefinition("payments.card_holder", "", ShortText, "Karta egasining ismi (to'lovchi tekshirishi uchun)"),
    SettingDefinition(
        "payments.chat_id",
        "",
        ShortText,
        "To'lovlar kanali yoki guruhi: cheklar (✅/❌ tugmalari bilan), to'lov savollari, Stars to'lovlari va "
        "haftalik moliyaviy xulosa faqat shu yerga keladi. Qo'lda yozish shart emas: botni kanalga "
        "administrator qilsangiz, bot sizdan «💳 To'lovlar kanali» tugmasini bosishni so'raydi. "
        "@username yoki -100… raqami (bo'sh — cheklar bosh administratorlarga botda)",
    ),
    SettingDefinition(
        "payments.stars_packages",
        [50, 100, 250, 500],
        Annotated[list[Annotated[int, Field(ge=1, le=100_000)]], Field(max_length=8)],
        "Karta orqali sotiladigan Stars to'plamlari (bo'sh — sotilmaydi)",
    ),
    SettingDefinition(
        "payments.star_price_uzs",
        250,
        Annotated[int, Field(ge=0, le=10_000)],
        "1 ta Stars narxi so'mda (Telegram'da sotib olish narxiga qarab; 0 — sotilmaydi)",
    ),
    # ---- Premium ----
    SettingDefinition(
        "premium.trial_days",
        7,
        Annotated[int, Field(ge=0, le=30)],
        "Har bir a'zoga bir marta bepul Premium sinov (kun; 0 — sinov yo'q)",
    ),
    # ---- Friend invitations ----
    SettingDefinition(
        "referral.points",
        20,
        Annotated[int, Field(ge=0, le=500)],
        "Do'stini taklif qilgan a'zoga ball (do'sti birinchi tadbirda qatnashganda)",
    ),
    SettingDefinition(
        "referral.premium_days",
        7,
        Annotated[int, Field(ge=0, le=60)],
        "Do'stini taklif qilgan a'zoga Premium kunlar (0 — Premium berilmaydi)",
    ),
    SettingDefinition(
        "referral.monthly_limit",
        5,
        Annotated[int, Field(ge=0, le=100)],
        "Bir a'zo bir oyda nechta taklif uchun mukofot oladi (0 — cheklovsiz)",
    ),
    SettingDefinition(
        "referral.friend_details",
        "FULL",
        Literal["FULL", "NAMES", "COUNT"],
        "«Sizning foydangiz»da a'zo taklif qilgan do'stlari haqida nimani ko'radi: FULL — ismi, ballari, "
        "o'qigan kitoblari va tadbirlari; NAMES — faqat ismi va tadbirga kelgani; COUNT — faqat sonlar",
        choices=("FULL", "NAMES", "COUNT"),
    ),
    SettingDefinition(
        "referral.leaderboard_size",
        10,
        Annotated[int, Field(ge=0, le=50)],
        "«Eng faol taklif qiluvchilar» ro'yxatida nechta a'zo ko'rinadi (0 — ro'yxat a'zolarga ko'rinmaydi)",
    ),
    SettingDefinition(
        "referral.leaderboard_rule",
        "ATTENDED",
        Literal["ATTENDED", "REGISTERED"],
        "Umumiy taklif reytingida qaysi do'stlar sanaladi: ATTENDED — kamida bitta tadbirga kelganlar "
        "(soxta hisoblardan himoya); REGISTERED — ro'yxatdan o'tganlarning hammasi",
        choices=("ATTENDED", "REGISTERED"),
    ),
    # ---- Study years ----
    SettingDefinition(
        "academic.promote_groups",
        True,
        bool,
        "Yangi o'quv yilida guruh raqami ham kurs bilan birga oshadi, agar uning birinchi raqami kursga teng "
        "bo'lsa (2-kursdagi «201» → «301»). Boshqacha nomlangan guruhlar o'zgarmaydi",
    ),
    SettingDefinition(
        "academic.ask_graduates",
        True,
        bool,
        "Yangi o'quv yilida oxirgi kursdagi a'zolardan «Bitirdingizmi?» deb so'raladi; «Ha» deganlar "
        "bitiruvchi (alumni) bo'ladi — klubda qoladi, lekin kurs bo'yicha hisobotlarga kirmaydi",
    ),
    SettingDefinition(
        "academic.summary_day",
        "06-20",
        Annotated[str, StringConstraints(pattern=r"^$|^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")],
        "«Yil yakuni»: shu kuni (OO-KK) har bir a'zoga o'quv yili davomidagi natijalari (kitoblar, tadbirlar, "
        "testlar, ballar, o'rni, do'stlari) yuboriladi. Bo'sh — yuborilmaydi",
    ),
    SettingDefinition(
        "academic.year_start",
        "09-01",
        Annotated[str, StringConstraints(pattern=r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")],
        "O'quv yili boshlanadigan kun (OO-KK): shu kuni kurslar bittaga oshadi va yangi mavsum boshlanadi",
    ),
    SettingDefinition(
        "academic.promote_courses",
        True,
        bool,
        "Yangi o'quv yilida faol a'zolarning kursi avtomatik bittaga oshirilsin (oxirgi kursdan oshmaydi)",
    ),
    SettingDefinition(
        "academic.auto_season",
        True,
        bool,
        "Har o'quv yili uchun alohida mavsum (reyting va hisobotlar yillar bo'yicha aralashmaydi)",
    ),
    SettingDefinition(
        "academic.current_year",
        0,
        Annotated[int, Field(ge=0, le=2200)],
        "Joriy o'quv yili boshlangan yil (avtomatik yoziladi; 0 — hali aniqlanmagan)",
    ),
    SettingDefinition(
        "membership.inactive_days",
        365,
        Annotated[int, Field(ge=0, le=3650)],
        "Shuncha kun botga ham, ilovaga ham kirmagan a'zo eslatmadan 7 kun keyin «faol emas» bo'ladi "
        "(ma'lumotlari saqlanadi, qaytsa o'zi tiklanadi; 0 — o'chiq)",
    ),
    # ---- Required subscription ----
    SettingDefinition(
        "subscription.required",
        True,
        bool,
        "Botdan va ilovadan foydalanish uchun kanal(lar)ga obuna majburiy (adminlardan so'ralmaydi; bot o'sha "
        "kanallarda administrator bo'lishi kerak, aks holda tekshiruv o'tkazib yuboriladi)",
    ),
    SettingDefinition(
        "subscription.channels",
        "",
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)],
        "Obuna bo'lish shart bo'lgan kanallar, vergul bilan: @kanal, https://t.me/kanal yoki yopiq kanal uchun "
        "-100…=https://t.me/+taklif (bo'sh — faqat klub kanali)",
    ),
    # ---- Telegram channel (the bot posts there as an administrator) ----
    SettingDefinition(
        "channel.enabled", False, bool, "Bot klub kanaliga post joylaydi (avval botni kanalga admin qiling)"
    ),
    SettingDefinition(
        "channel.chat_id", "@FJSTIMutolaaxona", ShortText, "Kanal manzili: @username yoki -100... raqami"
    ),
    SettingDefinition("channel.post_events", True, bool, "Yangi tadbirlar va «ertaga ... o'qib kelamiz» eslatmalari"),
    SettingDefinition("channel.post_books", True, bool, "Yangi kitoblar va «asarni tugatay deb qoldingizmi?» postlari"),
    SettingDefinition("channel.post_quotes", True, bool, "Kun iqtibosi kanalga ham joylanadi"),
    SettingDefinition("channel.post_results", True, bool, "Test g'oliblari, sovg'a o'yinlari va oy peshqadamlari"),
    SettingDefinition("channel.post_invites", True, bool, "Har dushanba botga taklif posti"),
    SettingDefinition(
        "channel.post_reports",
        True,
        bool,
        "Tadbir hisoboti tasdiqlanganda rasmlari bilan «... davra suhbati bo'lib o'tdi» posti",
    ),
    SettingDefinition(
        "channel.more_photos_url",
        "",
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=255, pattern=r"^(|https://\S+)$")],
        "Hisobot postidagi «📸 Boshqa rasmlar» tugmasi havolasi (masalan, rasmlar kanali: https://t.me/...)",
    ),
    SettingDefinition("channel.stickers", True, bool, "Avtomatik postlardan keyin saqlangan stikerlardan biri"),
    SettingDefinition(
        "channel.review_minutes",
        5,
        Annotated[int, Field(ge=0, le=60)],
        "Avtomatik post kanalga chiqishidan oldin adminlarga ko'rsatiladi; shu daqiqalarda hech kim javob "
        "bermasa, o'zi joylanadi (0 — tekshiruvsiz)",
    ),
    # ---- The bot's Telegram profile (applied by the bot itself; see services/bot_profile.py) ----
    SettingDefinition(
        "bot.name",
        "",
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)],
        "Botning Telegram'dagi nomi (64 belgigacha). Bo'sh — @BotFather'dagi nom o'zgarmaydi",
    ),
    SettingDefinition(
        "bot.short_description",
        BOT_SHORT_DESCRIPTION,
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)],
        "Bot profilidagi va ulashilgan havoladagi qisqa matn (120 belgigacha)",
    ),
    SettingDefinition(
        "bot.description",
        BOT_DESCRIPTION,
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=512)],
        "Botning bo'sh chatida «Start» ustida ko'rinadigan matn (512 belgigacha)",
    ),
    SettingDefinition(
        "bot.menu_button",
        "📱 Ilova",
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)],
        "Chat pastidagi ilovani ochadigan tugma matni",
    ),
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


# Every request reads a few settings; they change rarely. One process keeps the stored values for
# a few seconds (a change made here is seen at once; other processes catch up within seconds).
SETTINGS_SECONDS = 10.0
_stored_cache: tuple[float, dict[str, Any]] | None = None


def forget_cache() -> None:
    global _stored_cache
    _stored_cache = None


def _cache_seconds() -> float:
    from app.core.config import get_settings

    return 0.0 if get_settings().environment == "test" else SETTINGS_SECONDS


async def _stored_value(session: AsyncSession, key: str) -> Any:
    global _stored_cache
    seconds = _cache_seconds()
    if not seconds:
        return await session.scalar(select(SystemSetting.value).where(SystemSetting.key == key))
    now = time.monotonic()
    if _stored_cache is None or now - _stored_cache[0] >= seconds:
        rows = (await session.execute(select(SystemSetting.key, SystemSetting.value))).all()
        _stored_cache = (now, {row[0]: row[1] for row in rows})
    return copy.deepcopy(_stored_cache[1].get(key))


async def get_setting(session: AsyncSession, key: str) -> Any:
    """Current value of a setting, falling back to its default (and validating stored data)."""
    definition = get_definition(key)
    stored = await _stored_value(session, key)
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
    forget_cache()
    if key.startswith("subscription.") or key == "channel.chat_id":
        from app.services import subscription

        subscription.forget()  # the channel list changed: everybody is checked again
    if key.startswith("bot."):
        await _apply_bot_profile(session)
    return validated


async def _apply_bot_profile(session: AsyncSession) -> None:
    """A changed name, description or menu button reaches Telegram at once (best effort)."""
    from app.core.config import get_settings
    from app.services import bot_profile
    from app.services.delivery import optional_bot

    bot = optional_bot()
    if bot is None:
        return
    try:
        await bot_profile.apply_texts(bot, session)
        await bot_profile.apply_menu_button(bot, session, get_settings().webapp_url)
    except Exception:
        logger.warning("The bot profile could not be updated in Telegram; it is applied again on restart")
