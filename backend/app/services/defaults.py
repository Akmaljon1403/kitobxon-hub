"""Default reference data inserted on first start. Administrators can edit it afterwards;
re-running the bootstrap never overwrites their changes."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import AchievementCriteria, NotificationType, SystemRole


@dataclass(frozen=True)
class RoleSeed:
    code: str
    name: str
    description: str


SYSTEM_ROLES: tuple[RoleSeed, ...] = (
    RoleSeed(SystemRole.SUPER_ADMIN, "Bosh administrator", "Tizimga to'liq kirish huquqi."),
    RoleSeed(SystemRole.ADMIN, "Administrator", "Huquqlari alohida belgilanadigan administrator."),
    RoleSeed(SystemRole.USER, "A'zo", "Klubning oddiy a'zosi (barcha ro'yxatdan o'tganlar)."),
)


@dataclass(frozen=True)
class AchievementSeed:
    code: str
    title: str
    description: str
    icon: str
    criteria: AchievementCriteria
    threshold: int


DEFAULT_ACHIEVEMENTS: tuple[AchievementSeed, ...] = (
    AchievementSeed(
        "FIRST_BOOK",
        "Birinchi kitob",
        "Birinchi kitobni o'qib tugatdingiz.",
        "📗",
        AchievementCriteria.BOOKS_COMPLETED,
        1,
    ),
    AchievementSeed(
        "FIVE_BOOKS", "Besh kitob", "5 ta kitobni o'qib tugatdingiz.", "📚", AchievementCriteria.BOOKS_COMPLETED, 5
    ),
    AchievementSeed(
        "TEN_BOOKS", "O'n kitob", "10 ta kitobni o'qib tugatdingiz.", "🏛️", AchievementCriteria.BOOKS_COMPLETED, 10
    ),
    AchievementSeed(
        "FIRST_EVENT",
        "Ilk uchrashuv",
        "Birinchi marta klub tadbirida qatnashdingiz.",
        "🤝",
        AchievementCriteria.EVENTS_ATTENDED,
        1,
    ),
    AchievementSeed(
        "TEN_EVENTS", "Faol ishtirokchi", "10 ta tadbirda qatnashdingiz.", "🎖️", AchievementCriteria.EVENTS_ATTENDED, 10
    ),
    AchievementSeed(
        "ACTIVE_STREAK_4_WEEKS",
        "4 hafta faol",
        "Ketma-ket 4 hafta davomida tadbir yoki testda faol qatnashdingiz.",
        "🔥",
        AchievementCriteria.ACTIVITY_STREAK_WEEKS,
        4,
    ),
    AchievementSeed(
        "ACTIVE_STREAK_12_WEEKS",
        "12 hafta faol",
        "Ketma-ket 12 hafta davomida tadbir yoki testda faol qatnashdingiz.",
        "⚡",
        AchievementCriteria.ACTIVITY_STREAK_WEEKS,
        12,
    ),
    AchievementSeed(
        "TOP_3_MONTH",
        "Oy yetakchisi",
        "Oylik reytingda birinchi uchtalikka kirdingiz.",
        "🏆",
        AchievementCriteria.MONTHLY_TOP_RANK,
        3,
    ),
    AchievementSeed(
        "TEST_MASTER",
        "Test ustasi",
        "3 ta testdan maksimal ball oldingiz.",
        "🎯",
        AchievementCriteria.PERFECT_TESTS,
        3,
    ),
)


@dataclass(frozen=True)
class TemplateSeed:
    type: NotificationType
    title: str
    body: str
    is_critical: bool = False


DEFAULT_NOTIFICATION_TEMPLATES: tuple[TemplateSeed, ...] = (
    TemplateSeed(
        NotificationType.EVENT_CREATED,
        "Yangi tadbir",
        "📅 Yangi tadbir: «{event_title}»\n🕒 {starts_at}\n📍 {location}\n\n"
        "Qatnashmoqchi bo'lsangiz, ilovada ro'yxatdan o'ting.",
    ),
    TemplateSeed(
        NotificationType.EVENT_REMINDER,
        "Tadbir eslatmasi",
        "⏰ Eslatma: «{event_title}» tadbiri {starts_at} da boshlanadi.\n📍 {location}",
    ),
    TemplateSeed(NotificationType.EVENT_STARTED, "Tadbir boshlandi", "▶️ «{event_title}» tadbiri boshlandi!"),
    TemplateSeed(
        NotificationType.ATTENDANCE_OPEN,
        "Davomat ochildi",
        "✅ «{event_title}» tadbirida davomat ochildi. Ekrandagi QR kodni ilova orqali skanerlang yoki kodni kiriting.",
    ),
    TemplateSeed(
        NotificationType.TEST_STARTED,
        "Yangi test",
        "📝 Yangi test: «{test_title}»\nTest {ends_at} gacha ochiq. Ishlash vaqti: {duration} daqiqa.",
    ),
    TemplateSeed(
        NotificationType.TEST_ENDING,
        "Test yopilmoqda",
        "⌛ «{test_title}» testi {ends_at} da yopiladi. Hali ishlamagan bo'lsangiz, ulguring!",
    ),
    TemplateSeed(
        NotificationType.TEST_RESULT,
        "Test natijasi",
        "📊 «{test_title}» testidagi natijangiz: {score} / {max_score} ball.",
        is_critical=True,
    ),
    TemplateSeed(
        NotificationType.NEW_BOOK,
        "Yangi kitob",
        "📚 Yangi kitob: «{book_title}» — {book_author}\n🗓 O'qish muddati: {deadline}",
    ),
    TemplateSeed(
        NotificationType.READING_REMINDER,
        "O'qish eslatmasi",
        "📖 «{book_title}» kitobini o'qish muddati {deadline} da tugaydi.",
    ),
    TemplateSeed(
        NotificationType.QUOTE_OF_DAY, "Kun iqtibosi", "💬 Kun iqtibosi\n\n«{quote_text}»\n\n— {quote_author}"
    ),
    TemplateSeed(NotificationType.RANKING_UPDATE, "Reyting", "🏆 Reytingdagi o'rningiz: {rank}-o'rin ({total} ball)."),
    TemplateSeed(
        NotificationType.ACHIEVEMENT_UNLOCKED,
        "Yangi yutuq",
        "🏅 Tabriklaymiz! Siz «{achievement_title}» yutug'ini qo'lga kiritdingiz.",
    ),
    TemplateSeed(
        NotificationType.REWARD,
        "Sovg'a",
        "🎁 Sizga sovg'a berildi: «{reward_title}». Batafsil ma'lumot ilovada.",
        is_critical=True,
    ),
    TemplateSeed(NotificationType.ADMIN_MESSAGE, "Klub xabari", "📢 {message}", is_critical=True),
    TemplateSeed(NotificationType.SYSTEM, "Tizim xabari", "{message}", is_critical=True),
    TemplateSeed(NotificationType.SUPPORT, "Murojaat va javoblar", "{message}", is_critical=True),
    TemplateSeed(
        NotificationType.CERTIFICATE,
        "Sertifikat",
        "🎓 <b>Tabriklaymiz! Sizga sertifikat berildi.</b>\n\n🏅 {title}\n\n"
        "Sertifikat PDF fayl sifatida ilova qilingan — uni yuklab olib, chop etishingiz mumkin.\n{details}",
        is_critical=True,
    ),
    TemplateSeed(NotificationType.PREMIUM, "Premium obuna", "💎 {message}", is_critical=True),
    TemplateSeed(
        NotificationType.ANNOUNCEMENT,
        "Yangi imkoniyat",
        "🎉 <b>Tabriklaymiz, bot yangilandi!</b>\n\nEndi sizda yangi imkoniyat bor:\n{title} — {description}.",
    ),
    TemplateSeed(
        NotificationType.FEEDBACK_REQUEST,
        "Tadbir haqida fikr",
        "💬 «{event_title}» tadbiri sizga yoqdimi? Bir bosishda baho bering — "
        "bu keyingi tadbirlarni yaxshilashga yordam beradi.",
    ),
    TemplateSeed(
        NotificationType.DIGEST,
        "Haftalik xulosa",
        "📊 <b>Haftalik xulosangiz</b>\n\n{message}\n\nYangi haftada omad! 📚",
    ),
)


@dataclass(frozen=True)
class PlanSeed:
    code: str
    title: str
    description: str
    stars: int
    days: int


# Starting prices in Telegram Stars; the super admin changes them in the Admin Panel.
DEFAULT_PREMIUM_PLANS: tuple[PlanSeed, ...] = (
    PlanSeed("month", "1 oy", "30 kunlik Premium", 100, 30),
    PlanSeed("quarter", "3 oy", "90 kunlik Premium — 17% tejaysiz", 250, 90),
    PlanSeed("year", "1 yil", "365 kunlik Premium — eng foydali", 900, 365),
)
