"""All bot texts (Uzbek, Latin script). Kept in one place so wording can be edited easily.

Style: short sentences, one idea per line, "siz" form, the same names as in the Mini App.
"""

from __future__ import annotations

# ---- Main menu (the same names are used in the Mini App) ----
BTN_BOOKS = "📚 Kitoblar"
BTN_EVENTS = "📅 Tadbirlar"
BTN_ATTENDANCE = "✅ Davomat"
BTN_TESTS = "📝 Testlar"
BTN_RESULTS = "📊 Natijalarim"
BTN_RANKING = "🏆 Reyting"
BTN_PASSPORT = "🪪 Pasportim"
BTN_ACHIEVEMENTS = "🏅 Yutuqlar"
BTN_SETTINGS = "⚙️ Sozlamalar"
BTN_HELP = "💬 Yordam"
BTN_ADMIN = "🛠 Boshqaruv"

# Buttons of the previous menu: members keep the old keyboard until the bot sends a new one.
LEGACY_BUTTONS = {
    "👤 Profilim": BTN_PASSPORT,
    "🔔 Bildirishnomalar": BTN_SETTINGS,
    "ℹ️ Yordam": BTN_HELP,
}

# ---- Inline buttons ----
BTN_SHARE_PHONE = "📱 Raqamni yuborish"
BTN_CONFIRM = "✅ Tasdiqlash"
BTN_RESTART = "🔄 Qaytadan to'ldirish"
BTN_OPEN_APP = "📱 Ilovani ochish"
BTN_MORE = "📱 Batafsil — ilovada"
BTN_SCAN_QR = "📷 QR kodni skanerlash"
BTN_WRITE_ADMIN = "✉️ Adminga yozish"
BTN_EDIT_PROFILE = "✏️ Ma'lumotlarimni o'zgartirish"
BTN_ADMIN_PANEL = "🛠 Admin panelni ochish"
BTN_ADMIN_LINK = "💻 Kompyuter uchun havola"
BTN_ADMIN_LOGIN = "🔐 Admin panelga kirish"
BTN_REPLY = "✍️ Javob yozish"

# ---- Registration ----
WELCOME_NEW = (
    "Assalomu alaykum! 👋\n\n"
    "<b>Kitobxon Hub</b> — kitobxonlar klubimizning rasmiy boti. Bu yerda kitoblar, tadbirlar, "
    "testlar, ballar va reyting bir joyda.\n\n"
    "Ro'yxatdan o'tish 1 daqiqa vaqt oladi — bir nechta qisqa savol beramiz.\n"
    "To'xtatish uchun: /cancel"
)
ASK_FIRST_NAME = "<b>{step}.</b> Ismingiz?\n<i>Masalan: Akmaljon</i>"
ASK_LAST_NAME = "<b>{step}.</b> Familiyangiz?\n<i>Masalan: Bahodirov</i>"
ASK_PHONE = (
    "<b>{step}.</b> Telefon raqamingizni yuboring.\n\n"
    "Pastdagi «📱 Raqamni yuborish» tugmasini bosing. Raqamingizni faqat klub rahbariyati ko'radi."
)
ASK_PHONE_USE_BUTTON = "Raqamni qo'lda yozish shart emas — pastdagi «📱 Raqamni yuborish» tugmasini bosing."
PHONE_NOT_YOURS = "Iltimos, o'zingizning raqamingizni yuboring."
PHONE_ACCEPTED = "✅ Raqam qabul qilindi."
ASK_FACULTY = "<b>{step}.</b> Fakultetingizni tanlang:"
ASK_COURSE = "<b>{step}.</b> Nechanchi kursdasiz?"
ASK_GROUP = "<b>{step}.</b> Guruhingiz?\n<i>Masalan: 301 yoki 301-A</i>"
CONFIRM = (
    "Ma'lumotlaringizni tekshiring:\n\n"
    "👤 <b>{first_name} {last_name}</b>\n"
    "📱 {phone}\n"
    "🏛 {faculty}\n"
    "🎓 {course}-kurs, {group}-guruh\n\n"
    "Hammasi to'g'rimi?"
)
NO_FACULTY = "ko'rsatilmagan"
REGISTERED = (
    "🎉 Tabriklaymiz, {first_name}! Endi siz Kitobxon Hub a'zosisiz.\n\n"
    "Pastdagi menyudan foydalaning:\n"
    "• tadbirda «✅ Davomat» — qatnashganingizni qayd etish uchun;\n"
    "• «📊 Natijalarim» — ballaringiz va o'rningiz;\n"
    "• «🪪 Pasportim» — kitobxon pasportingiz."
)
REGISTERED_PENDING = (
    "✅ Arizangiz qabul qilindi, {first_name}!\n\nKlub rahbariyati ko'rib chiqqach, shu yerda xabar beramiz."
)
REGISTRATION_CANCELLED = "Ro'yxatdan o'tish to'xtatildi. Qayta boshlash uchun /start ni bosing."
REGISTRATION_EXPIRED = "Bu tugma eskirgan. Davom etish uchun /start ni bosing."
REGISTRATION_TEXT_ONLY = "Iltimos, savolga matn bilan javob bering yoki /cancel ni bosing."

# ---- Registered members ----
WELCOME_BACK = "Assalomu alaykum, {first_name}! 👋\nPastdagi menyudan kerakli bo'limni tanlang."
MENU_UPDATED = "Menyu yangilandi ✨ Pastdagi tugmalardan foydalaning."
NOT_REGISTERED = "Avval ro'yxatdan o'ting: /start"
ACCOUNT_PENDING = "Arizangiz hali ko'rib chiqilmoqda. Tasdiqlangach, shu yerda xabar beramiz."
ACCOUNT_BLOCKED = "Hisobingiz bloklangan. Savollar bo'lsa, klub rahbariyatiga murojaat qiling."
ACCOUNT_INACTIVE = "Hisobingiz faol emas. Klub rahbariyatiga murojaat qiling."
APP_NOT_CONFIGURED = "Ilova manzili hali sozlanmagan. Birozdan so'ng qayta urinib ko'ring."

# ---- Section summaries (short; details are in the Mini App) ----
BOOKS_CURRENT = "📚 <b>Hozir o'qiyapmiz</b>\n«{title}» — {author}\n{deadline}{status}"
BOOKS_DEADLINE = "⏳ Muddat: {date} ({left})\n"
BOOKS_STATUS_DONE = "✅ Siz o'qib tugatgansiz"
BOOKS_STATUS_VERIFIED = "✅ Siz o'qib tugatgansiz, ball berilgan"
BOOKS_STATUS_READING = "📖 Siz o'qiyapsiz"
BOOKS_STATUS_NOT_STARTED = "Boshlaganingizda ilovada «O'qishni boshladim»ni bosing."
BOOKS_MORE = "\n\nYana {count} ta kitob — ilovada."
BOOKS_NONE = "📚 Hozircha faol kitob yo'q. Yangi kitob qo'shilganda xabar beramiz."

EVENTS_NEXT = "📅 <b>Yaqin tadbir</b>\n«{title}»\n🕒 {when}\n{where}{registration}"
EVENTS_WHERE = "📍 {location}\n"
EVENTS_REGISTERED = "✅ Siz qatnashishga yozilgansiz"
EVENTS_NOT_REGISTERED = "Qatnashsangiz, ilovada «Qatnashaman»ni bosing."
EVENTS_MORE = "\n\nJami {count} ta tadbir rejalashtirilgan."
EVENTS_NONE = "📅 Hozircha rejalashtirilgan tadbir yo'q."

ATTENDANCE_OPEN = (
    "✅ <b>Davomat ochiq</b>: «{title}»\n\n"
    "Ekrandagi <b>6 belgili kodni</b> shu yerga yozing yoki «📷 QR kodni skanerlash»ni bosing."
)
ATTENDANCE_ALREADY = "✅ Siz «{title}» tadbirida qayd etilgansiz."
ATTENDANCE_NONE = "Hozir ochiq davomat yo'q.\n\n{next}Davomat tadbir boshlanishidan biroz oldin o'zi ochiladi."
ATTENDANCE_NEXT = "📅 Keyingi tadbir: «{title}», {when}\n\n"
ATTENDANCE_OK = "✅ Davomatingiz qayd etildi!\n\n📅 «{title}»\n🏆 +{points} ball"
ATTENDANCE_REGISTER_FIRST = "Davomat uchun avval ro'yxatdan o'ting. Keyin ekrandagi QR kodni qayta skanerlang."
ATTENDANCE_CODE_HINT = "Kod 6 ta harf va raqamdan iborat, masalan: <code>K7M2QX</code>. Qayta yozing yoki /cancel."

TESTS_OPEN = (
    "📝 <b>Ochiq test</b>: «{title}»\n🎯 {max_score} ballgacha · ⏱ {minutes} daqiqa\n⌛ Yopiladi: {ends}\n{status}"
)
TESTS_DONE = "✅ Siz yechgansiz: {score} ball"
TESTS_NOT_DONE = "Siz hali yechmagansiz."
TESTS_MORE = "\n\nYana {count} ta ochiq test — ilovada."
TESTS_UPCOMING = "📝 Hozir ochiq test yo'q.\nKeyingisi: «{title}», {starts}."
TESTS_NONE = "📝 Hozircha test yo'q."

RESULTS = (
    "📊 <b>Natijalarim</b>\n\n"
    "🏆 Jami: <b>{total} ball</b>{rank_all}\n"
    "📅 Shu oy: <b>{month} ball</b>{rank_month}\n\n"
    "✅ Davomat: {attendance} · 📝 Testlar: {tests} · 📚 Kitoblar: {books}"
)
RESULTS_RANK = " — <b>{rank}-o'rin</b>"
RESULTS_EMPTY = (
    "📊 Hozircha ballaringiz yo'q.\n\n"
    "Tadbirga keling, test yeching, kitobni o'qib tugating — ballar shu yerda ko'rinadi."
)

RANKING = "🏆 <b>Shu oy yetakchilari</b>\n{top}\n\n{me}"
RANKING_ROW = "{medal} {name} — {total}"
RANKING_ME = "Siz: <b>{rank}-o'rin</b>, {total} ball"
RANKING_ME_NONE = "Siz bu oy hali ball to'plamadingiz."
RANKING_EMPTY = "🏆 Bu oy hali hech kim ball to'plamadi. Birinchi bo'ling!"

ACHIEVEMENTS = "🏅 <b>Yutuqlarim</b>: {done} / {total}\n{last}{next}"
ACHIEVEMENTS_LAST = "\nOxirgisi: {icon} {title}"
ACHIEVEMENTS_NEXT = "\nKeyingisi: {icon} {title} — {progress}/{threshold}"
ACHIEVEMENTS_NONE = "🏅 Hozircha yutuqlar sozlanmagan."

PASSPORT = (
    "🪪 <b>Kitobxon pasporti</b> · {number}\n\n"
    "👤 {first_name} {last_name}\n"
    "🏛 {faculty}\n"
    "🎓 {course}-kurs, {group}-guruh\n"
    "📅 A'zo bo'lgan: {registered}\n"
    "🏆 {total} ball"
)

SETTINGS = (
    "⚙️ <b>Sozlamalar</b>\n\n"
    "Qaysi eslatmalarni olishni tanlang. Muhim xabarlar (test natijasi, javoblar, sovg'alar) har doim keladi."
)
NOTIFICATION_LABELS = {
    "event_reminders": "📅 Tadbir eslatmalari",
    "test_reminders": "📝 Test eslatmalari",
    "reading_reminders": "📖 O'qish muddati",
    "quote_of_day": "💬 Kun iqtibosi",
    "ranking_updates": "🏆 Reyting yangiliklari",
    "achievement_alerts": "🏅 Yutuqlar",
}

# ---- Help and messages to the club ----
HELP = (
    "💬 <b>Yordam</b>\n\n"
    "<b>Davomat qanday qilinadi?</b>\n"
    "Tadbirda «✅ Davomat»ni bosing va ekrandagi kodni yozing yoki QR kodni skanerlang.\n\n"
    "<b>Ballar nima uchun beriladi?</b>\n"
    "Tadbirga kelish, test yechish va kitobni o'qib tugatish uchun. Batafsil — «📊 Natijalarim»da.\n\n"
    "<b>Ma'lumotlarim noto'g'ri bo'lsa?</b>\n"
    "«⚙️ Sozlamalar» → «✏️ Ma'lumotlarimni o'zgartirish».\n\n"
    "Savol, taklif yoki muammo bo'lsa — «✉️ Adminga yozish». Javob shu yerga keladi."
)
SUPPORT_ASK = (
    "✉️ <b>Klub rahbariyatiga xabar</b>\n\n"
    "Savol, taklif yoki muammoingizni bitta xabarda yozing. Rasm ham yuborishingiz mumkin.\n\n"
    "Bekor qilish: /cancel"
)
SUPPORT_SENT = "✅ Xabaringiz yuborildi. Javob shu yerga keladi."
SUPPORT_ONLY_TEXT = "Iltimos, matn yoki rasm yuboring. Bekor qilish: /cancel"
SUPPORT_REPLY_ASK = (
    "✍️ Javobingizni yozing.\nA'zo uni «Klub rahbariyati» nomidan oladi — ismingiz ko'rinmaydi.\n\nBekor qilish: /cancel"
)
SUPPORT_REPLY_SENT = "✅ Javob yuborildi."
SUPPORT_NO_PERMISSION = "Murojaatlarga javob berish uchun ruxsatingiz yo'q."

# ---- Administrators ----
ADMIN_HOME = (
    "🛠 <b>Boshqaruv</b>\n\n"
    "👥 A'zolar: {members}{new_today}\n"
    "📨 Javob kutayotgan murojaatlar: {tickets}\n"
    "✅ Hozir ochiq davomat: {open_attendance}\n\n"
    "Admin panel shu yerning o'zida, Telegram ichida ochiladi. Kompyuterda ishlash uchun bir martalik havola oling."
)
ADMIN_NEW_TODAY = " (bugun +{count})"
ADMIN_LINK = (
    "💻 <b>Kompyuterda kirish havolasi</b>\n\n"
    "Havola bir marta ishlaydi va {minutes} daqiqada eskiradi. Uni hech kimga yubormang."
)
ADMIN_ONLY = "Bu bo'lim faqat klub administratorlari uchun."
ADMIN_URL_NOT_CONFIGURED = "Admin panel manzili (PUBLIC_BASE_URL) hali sozlanmagan."

# ---- Misc ----
MY_ID = "Sizning Telegram ID raqamingiz: <code>{telegram_id}</code>"
CANCELLED = "Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qilinadigan amal yo'q."
UNKNOWN_MESSAGE = "Tushunmadim 🤔 Pastdagi menyudan foydalaning yoki /help ni bosing."
UNEXPECTED_ERROR = "Kechirasiz, kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
TOO_MANY_REQUESTS = "Juda tez yozyapsiz. Biroz kuting."
BLOCKED_TEXT = "Hisobingiz faol emas."

# ---- Bot profile (shown by Telegram before the user presses Start) ----
BOT_SHORT_DESCRIPTION = "Kitobxonlar klubi: kitoblar, tadbirlar, davomat, testlar va reyting 📚"
BOT_DESCRIPTION = (
    "📚 Kitobxon Hub — kitobxonlar klubining rasmiy boti.\n\n"
    "• Klub kitoblari va o'qish muddatlari\n"
    "• Tadbirlar va QR kod orqali davomat\n"
    "• Kitoblar bo'yicha testlar\n"
    "• Ballar, reyting, yutuqlar va sertifikatlar\n"
    "• Kitobxon pasporti\n\n"
    "Boshlash uchun «Start»ni bosing."
)
