"""All bot texts (Uzbek, Latin script). Kept in one place so wording can be edited easily."""

from __future__ import annotations

# ---- Main menu (the same terms are used in the Mini App) ----
BTN_BOOKS = "📚 Kitoblar"
BTN_PROFILE = "👤 Profilim"
BTN_RANKING = "🏆 Reyting"
BTN_EVENTS = "📅 Tadbirlar"
BTN_TESTS = "📝 Testlar"
BTN_RESULTS = "📊 Natijalarim"
BTN_ACHIEVEMENTS = "🏅 Yutuqlar"
BTN_NOTIFICATIONS = "🔔 Bildirishnomalar"
BTN_HELP = "ℹ️ Yordam"

BTN_SHARE_PHONE = "📱 Raqamni yuborish"
BTN_CONFIRM = "✅ Tasdiqlash"
BTN_RESTART = "🔄 Qaytadan to'ldirish"
BTN_OPEN_APP = "📱 Ilovani ochish"
BTN_ADMIN_LOGIN = "🔐 Admin panelga kirish"

# ---- Registration ----
WELCOME_NEW = (
    "Assalomu alaykum! <b>Kitobxon Hub</b>ga xush kelibsiz 📚\n\n"
    "Bu — kitobxonlar klubimizning rasmiy boti. Ro'yxatdan o'tish uchun bir nechta savolga javob bering. "
    "Bu 1–2 daqiqa vaqt oladi.\n\n"
    "Istalgan paytda /cancel buyrug'i bilan to'xtatishingiz mumkin."
)
ASK_FIRST_NAME = "<b>{step}.</b> Ismingizni yozing:\n<i>Masalan: Akmaljon</i>"
ASK_LAST_NAME = "<b>{step}.</b> Familiyangizni yozing:\n<i>Masalan: Bahodirov</i>"
ASK_PHONE = (
    "<b>{step}.</b> Telefon raqamingizni yuboring.\n\n"
    "Pastdagi «📱 Raqamni yuborish» tugmasini bosing. Raqamingiz faqat klub rahbariyatiga ko'rinadi."
)
ASK_PHONE_USE_BUTTON = "Iltimos, raqamni qo'lda yozmang — pastdagi «📱 Raqamni yuborish» tugmasini bosing."
PHONE_NOT_YOURS = "Iltimos, boshqa odamning emas, o'zingizning raqamingizni yuboring."
ASK_FACULTY = "<b>{step}.</b> Fakultetingizni tanlang:"
ASK_COURSE = "<b>{step}.</b> Nechanchi kursda o'qiysiz?"
ASK_GROUP = "<b>{step}.</b> Guruhingizni yozing:\n<i>Masalan: 301 yoki 301-A</i>"
CONFIRM = (
    "Ma'lumotlaringizni tekshiring:\n\n"
    "👤 <b>{first_name} {last_name}</b>\n"
    "📱 {phone}\n"
    "🏛 {faculty}\n"
    "🎓 {course}-kurs, {group} guruh\n\n"
    "Hammasi to'g'rimi?"
)
NO_FACULTY = "ko'rsatilmagan"
REGISTERED = (
    "🎉 Tabriklaymiz, {first_name}! Siz Kitobxon Hub a'zosi bo'ldingiz.\n\n"
    "Pastdagi menyudan foydalaning yoki «📱 Ilovani ochish» tugmasini bosing."
)
REGISTERED_PENDING = (
    "✅ Arizangiz qabul qilindi, {first_name}!\n\n"
    "Klub rahbariyati arizani ko'rib chiqqach, sizga shu yerda xabar beramiz."
)
REGISTRATION_CANCELLED = "Ro'yxatdan o'tish to'xtatildi. Qayta boshlash uchun /start buyrug'ini yuboring."
REGISTRATION_EXPIRED = "Bu tugma eskirgan. Ro'yxatdan o'tishni davom ettirish uchun /start buyrug'ini yuboring."

# ---- Registered members ----
WELCOME_BACK = "Assalomu alaykum, {first_name}! 📚\nKerakli bo'limni menyudan tanlang."
NOT_REGISTERED = "Avval ro'yxatdan o'ting: /start"
ACCOUNT_PENDING = "Arizangiz hali ko'rib chiqilmoqda. Tasdiqlangach, sizga xabar beramiz."
ACCOUNT_BLOCKED = "Hisobingiz bloklangan. Savollar bo'lsa, klub rahbariyatiga murojaat qiling."
ACCOUNT_INACTIVE = "Hisobingiz faol emas. Klub rahbariyatiga murojaat qiling."

PROFILE = (
    "👤 <b>{first_name} {last_name}</b>\n"
    "🏛 {faculty}\n"
    "🎓 {course}-kurs, {group} guruh\n"
    "📅 A'zo bo'lgan sana: {registered}\n\n"
    "Ballar, reyting va yutuqlar ilovada ko'rsatiladi."
)

SECTION_HINTS = {
    BTN_BOOKS: "📚 Klubning kitoblari, o'qish muddatlari va iqtiboslar ilovada.",
    BTN_RANKING: "🏆 Haftalik, oylik va umumiy reyting ilovada.",
    BTN_EVENTS: "📅 Yaqinlashayotgan tadbirlar va ularga ro'yxatdan o'tish ilovada.",
    BTN_TESTS: "📝 Ochiq testlar ilovada. Testni boshlashdan oldin internet aloqangizni tekshiring.",
    BTN_RESULTS: "📊 Ballaringiz tarixi va test natijalaringiz ilovada.",
    BTN_ACHIEVEMENTS: "🏅 Qo'lga kiritgan yutuqlaringiz ilovada.",
}
APP_NOT_CONFIGURED = "Ilova manzili hali sozlanmagan. Iltimos, keyinroq urinib ko'ring."

HELP = (
    "ℹ️ <b>Kitobxon Hub — yordam</b>\n\n"
    "📚 <b>Kitoblar</b> — klub o'qiyotgan kitoblar va muddatlar\n"
    "📅 <b>Tadbirlar</b> — uchrashuvlar; tadbirda QR kod orqali davomat qilinadi\n"
    "📝 <b>Testlar</b> — kitoblar bo'yicha bilim testlari\n"
    "🏆 <b>Reyting</b> — davomat, testlar va kitoblar uchun ballar\n"
    "🔔 <b>Bildirishnomalar</b> — eslatmalarni yoqish/o'chirish\n\n"
    "<b>Buyruqlar</b>\n"
    "/start — bosh menyu\n"
    "/help — yordam\n"
    "/myid — Telegram ID raqamingiz\n"
    "/cancel — joriy amalni bekor qilish"
)

NOTIFICATIONS = (
    "🔔 <b>Bildirishnomalar</b>\n\n"
    "Qaysi eslatmalarni olishni tanlang. Muhim xabarlar (test natijasi, sovg'alar, klub e'lonlari) "
    "har doim yuboriladi."
)
NOTIFICATION_LABELS = {
    "event_reminders": "📅 Tadbir eslatmalari",
    "test_reminders": "📝 Test eslatmalari",
    "reading_reminders": "📖 O'qish muddati eslatmalari",
    "quote_of_day": "💬 Kun iqtibosi",
    "ranking_updates": "🏆 Reyting yangiliklari",
    "achievement_alerts": "🏅 Yutuqlar haqida",
}

MY_ID = "Sizning Telegram ID raqamingiz: <code>{telegram_id}</code>"
ADMIN_LINK = (
    "🔐 Admin panelga kirish havolasi tayyor.\n\n"
    "Havola faqat bir marta ishlaydi va {minutes} daqiqa ichida eskiradi. Uni hech kimga yubormang."
)
ADMIN_ONLY = "Bu buyruq faqat klub administratorlari uchun."
ADMIN_URL_NOT_CONFIGURED = "Admin panel manzili (PUBLIC_BASE_URL) hali sozlanmagan."
NOTHING_TO_CANCEL = "Bekor qilinadigan amal yo'q."
UNKNOWN_MESSAGE = "Tushunmadim 🤔 Menyudagi tugmalardan foydalaning yoki /help buyrug'ini yuboring."
UNEXPECTED_ERROR = "Kechirasiz, kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
TOO_MANY_REQUESTS = "Juda tez xabar yuboryapsiz. Biroz kuting."

# ---- Bot profile (shown by Telegram before the user presses Start) ----
BOT_SHORT_DESCRIPTION = "Kitobxonlar klubi: kitoblar, tadbirlar, testlar va reyting 📚"
BOT_DESCRIPTION = (
    "📚 Kitobxon Hub — Farg'ona jamoat salomatligi tibbiyot instituti kitobxonlar klubining rasmiy boti.\n\n"
    "• Klub kitoblari va o'qish muddatlari\n"
    "• Tadbirlar va QR kod orqali davomat\n"
    "• Kitoblar bo'yicha testlar\n"
    "• Ballar, reyting va yutuqlar\n\n"
    "Boshlash uchun «Start» tugmasini bosing."
)
