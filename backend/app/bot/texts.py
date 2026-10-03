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
RANKING_WEEK = "🏆 <b>Shu hafta yetakchilari</b>\n{top}\n\n{me}"
RANKING_WEEK_ME_NONE = "Siz bu hafta hali ball to'plamadingiz — har bir tadbir va test ball keltiradi."
RANKING_WEEK_EMPTY = "🏆 Bu hafta hali hech kim ball to'plamadi. Birinchi bo'ling!"
RANKING_FULL_TEASER = "\n\n💎 Oylik va umumiy reyting, fakultet va guruhingizdagi o'rningiz — Premium a'zolar uchun."

ACHIEVEMENTS = "🏅 <b>Yutuqlarim</b>: {done} / {total}\n{last}{next}{certificates}"
ACHIEVEMENTS_CERTIFICATES = "\n\n🎓 Sertifikatlar: {count}"
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
BTN_PASSPORT_FILE = "📥 Fayl sifatida (asl sifat)"
BTN_PASSPORT_PHOTO = "📷 Rasmni almashtirish"
BTN_PASSPORT_RESET = "↩️ Telegram rasmiga qaytish"
BTN_PASSPORT_THEME = "🎨 Dizayn (Premium)"
PASSPORT_PHOTO_ASK = (
    "📷 Pasport uchun rasmingizni yuboring.\n\n"
    "Yuzingiz aniq ko'rinsin, rasm tik (vertikal) bo'lgani yaxshi. Bekor qilish: /cancel"
)
PASSPORT_PHOTO_HINT = "Rasm yuboring (galereyadan yoki kamera orqali). Bekor qilish: /cancel"
PASSPORT_PHOTO_SAVED = "✅ Rasm saqlandi! Yangi pasportingiz:"
PASSPORT_PHOTO_RESET = "✅ Endi pasportda Telegram profilingiz rasmi turadi."
PASSPORT_THEMES = "🎨 <b>Pasport dizayni</b>\n\nPremium a'zolar pasportining ko'rinishini tanlaydi:"
PASSPORT_THEME_SAVED = "✅ Dizayn o'zgardi!"
BTN_CERTIFICATES = "🎓 Sertifikatlarim"
FILE_SENT = "Yuborildi ✅"
FILE_FAILED = "Faylni tayyorlab bo'lmadi. Birozdan keyin qayta urinib ko'ring."
CERTIFICATES = (
    "🎓 <b>Sertifikatlaringiz</b> — {count} ta\n\nQaysi birini yuboray? PDF faylni yuklab olib, chop etishingiz mumkin."
)
CERTIFICATES_NONE = (
    "🎓 Hozircha sertifikatingiz yo'q.\n\n"
    "Sertifikat avtomatik beriladi:\n"
    "• testda 1-, 2- yoki 3-o'rinni olganlarga (tadbir testida — davomatdan o'tganlarga);\n"
    "• oy yakunida reytingdagi eng faol uchlikka.\n\n"
    "Omad! 💪"
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


# ---- Feature switches ----
FEATURE_OFF = "🔒 «{title}» hozircha o'chirilgan. Klub rahbariyati uni tez orada yoqishi mumkin."
FEATURE_PREMIUM = (
    "💎 «{title}» — <b>Premium</b> a'zolar uchun imkoniyat.\n\n"
    "Premium obuna bu va boshqa qo'shimcha imkoniyatlarni ochadi hamda klub rivojiga hissa bo'ladi."
)

# ---- Premium and donations (Telegram Stars) ----
BTN_PREMIUM = "💎 Premium"
BTN_DONATE = "❤️ Klubni qo'llab-quvvatlash"
PREMIUM_CLOSED = "💎 Premium obuna hozircha yopiq. Ochilganda albatta xabar beramiz!"
PREMIUM_INFO = (
    "💎 <b>Kitobxon Premium</b>\n\n"
    "{status}\n\n"
    "<b>Premium bilan:</b>\n{perks}\n\n"
    "To'lov Telegram Stars (⭐) orqali — xavfsiz va bir zumda. "
    "Tushgan mablag' klub tadbirlari, kitoblar va sovg'alarga sarflanadi."
)
PREMIUM_STATUS_LIFETIME = "♾ Sizda <b>umrbod Premium</b> bor — barcha imkoniyatlar doim ochiq."
PREMIUM_STATUS_ON = "✅ Siz Premium a'zosiz — <b>{until}</b> gacha. Muddatni uzaytirish mumkin."
PREMIUM_STATUS_OFF = "Siz hozir oddiy a'zosiz."
PREMIUM_PERK = "• {title} — {description}"
PREMIUM_PLAN = "{title} — {stars} ⭐"
PREMIUM_PLAN_DISCOUNT = "{title} — {stars} ⭐ (−{percent}%)"
PREMIUM_DISCOUNT = "🎟 Sizda Premium'ga <b>−{percent}%</b> chegirma bor — {until} gacha."
BTN_TRIAL = "🎁 {days} kun bepul sinab ko'rish"
TRIAL_STARTED = (
    "🎉 <b>Bepul Premium boshlandi!</b>\n\n"
    "{days} kun davomida barcha Premium imkoniyatlari ochiq: oltin pasport, to'liq reyting, sertifikat PDF, "
    "statistika va boshqalar. Sinov {until} gacha — hech qanday to'lov yechilmaydi."
)
DONATE_INFO = (
    "❤️ <b>Klubni qo'llab-quvvatlash</b>\n\n"
    "Har qanday hissa kitoblar sotib olish, tadbirlar va g'oliblarga sovg'alar uchun ishlatiladi. "
    "Miqdorni tanlang:"
)
DONATE_CLOSED = "❤️ Hozircha hissa qabul qilinmayapti. Rahmat!"
PAYMENT_PREMIUM_OK = (
    "🎉 <b>Rahmat! Premium faollashtirildi.</b>\n\n"
    "Amal qilish muddati: <b>{until}</b> gacha.\n"
    "Qo'llab-quvvatlaganingiz uchun klub nomidan katta rahmat! 💎"
)
PAYMENT_DONATION_OK = "❤️ <b>Katta rahmat!</b> {amount} ⭐ hissangiz klub rivojiga sarflanadi."
PAYMENT_STUCK = (
    "To'lov qabul qilindi, lekin uni qayd etishda muammo bo'ldi. Xavotir olmang — "
    "«/paysupport» orqali yozing, admin tekshirib beradi."
)
TERMS = (
    "📄 <b>Foydalanish shartlari</b>\n\n"
    "1. Klubning asosiy imkoniyatlari (kitoblar, tadbirlar, davomat, testlar, reyting) hamma a'zolar uchun bepul.\n"
    "2. Premium — ixtiyoriy obuna: qo'shimcha imkoniyatlarni ochadi va tanlangan muddat (kun) davomida amal qiladi. "
    "Muddat tugagach avtomatik yangilanmaydi.\n"
    "3. To'lov Telegram Stars orqali qabul qilinadi. Tushgan mablag' klub faoliyatiga sarflanadi.\n"
    "4. Texnik nosozlik tufayli Premium ishlamasa yoki xato to'lov bo'lsa — /paysupport orqali yozing, "
    "Stars qaytariladi.\n"
    "5. Qoidalarni buzgan a'zoning Premium obunasi to'xtatilishi mumkin."
)
PAYSUPPORT = (
    "🧾 <b>To'lov bo'yicha yordam</b>\n\n"
    "To'lov, Premium yoki qaytarish (refund) haqida savolingizni «✉️ Adminga yozish» orqali yuboring — "
    "klub rahbariyati tez orada javob beradi."
)

# ---- Event feedback ----
FEEDBACK_THANKS = "Rahmat! Bahoyingiz: {stars} ({rating}/5)."
FEEDBACK_ASK_COMMENT = "Xohlasangiz, tadbir haqida fikringizni yozing — nima yoqdi, nimani yaxshilash kerak?"
BTN_FEEDBACK_COMMENT = "✍️ Fikr yozish"
FEEDBACK_COMMENT_SAVED = "✅ Fikringiz klub rahbariyatiga yetkazildi. Rahmat!"
FEEDBACK_NOT_ALLOWED = "Bu tadbirga baho bera olmaysiz."


# ---- Card payments ----
BTN_PAY_CARD = "💳 Karta orqali (Premium yoki ⭐ Stars)"
CARD_CHOOSE = (
    "💳 <b>Karta orqali to'lov</b>\n\n"
    "Telegram Stars'ingiz bo'lmasa yoki ularni qanday olishni bilmasangiz — klub kartasiga to'lang:\n"
    "• <b>💎 Premium</b> — tasdiqlangach o'zi yoqiladi;\n"
    "• <b>⭐ Stars</b> — tanlagan miqdoringiz Telegram'da sizga sovg'a qilib yuboriladi.\n\nTanlang:"
)
CARD_PLAN = "💎 {title} — {price}"
CARD_STARS = "⭐ {stars} Stars — {price}"
BTN_STARS_SENT = "✅ Stars yuborildi"
CARD_STARS_DELIVERED = "✅ Belgilandi: {name} ga {stars} ⭐ yuborildi. A'zoga xabar ketdi."
CARD_DONATE = "❤️ Hissa (istalgan summa)"
CARD_INSTRUCTIONS = (
    "💳 <b>{what}</b> — <b>{price}</b>\n\n"
    "Karta: <code>{number}</code>\n"
    "{holder}"
    "\n1) Shu summani kartaga o'tkazing (Click, Payme, bank ilovasi).\n"
    "2) To'lov <b>chekini (skrinshot)</b> shu yerga rasm qilib yuboring.\n\n"
    "Admin tekshirgach, Premium avtomatik yoqiladi. Bekor qilish: /cancel"
)
CARD_HOLDER = "Egasi: {holder}\n"
CARD_DONATION_ASK = "❤️ Qancha hissa qo'shmoqchisiz? Summani so'mda yozing (masalan: 20000)."
CARD_DONATION_INVALID = "Summani raqam bilan yozing, kamida 1 000 so'm (masalan: 20000)."
CARD_RECEIPT_HINT = "Chekni rasm (skrinshot) qilib yuboring. Bekor qilish: /cancel"
CARD_RECEIPT_OK = (
    "✅ <b>Chek qabul qilindi!</b>\n\n"
    "Admin tekshirib tasdiqlagach, sizga xabar keladi va Premium avtomatik yoqiladi. Rahmat!"
)
CARD_OFF = "💳 Karta orqali to'lov hozircha yoqilmagan."

# ---- Card payments: the super admin's side ----
CARD_ADMIN_ONLY = "Bu tugma faqat bosh administrator uchun."
CARD_RECEIPT_CAPTION = "🧾 <b>{what}</b> — {price}\nA'zo: {name}\nHolat: {status}"
CARD_APPROVED = "✅ Tasdiqlandi: {name} — {price}. A'zoga xabar yuborildi."
CARD_REJECT_ASK = "❌ Rad etish sababini yozing (a'zo shuni ko'radi), masalan: «Summa to'liq emas»."
CARD_REJECTED = "❌ Rad etildi. A'zoga sabab bilan xabar yuborildi."

# ---- Channel stickers (/stiker, admins) ----
STICKER_ASK = (
    "🎨 <b>Bot va kanal uchun stikerlar</b>\n\n"
    "Menga yoqqan stikerlaringizni birma-bir yuboring (oddiy, animatsion yoki Premium). Bot ularni saqlaydi "
    "va mos joyda ishlatadi: 🎉 kabi quvnoq stikerlar — g'alaba va tabriklardan keyin, 📚 kitobli stikerlar — "
    "kitob postlaridan keyin, 👋 salomlashuvchilar — yangi a'zolarga.\n\nTugatgach — /tayyor"
)
STICKER_SAVED = "✅ Saqlandi ({mood}). Jami stikerlar: {total} ta. Yana yuboring yoki /tayyor"
STICKER_MOODS = {
    "CELEBRATE": "🎉 tabriklar uchun",
    "READING": "📚 kitob mavzusida",
    "WELCOME": "👋 salomlashish uchun",
    "ANY": "har qanday xabar uchun",
}
# ---- Channel posts: the admins look first ----
CHANNEL_POST_NOW = "✅ Post kanalga joylanmoqda."
CHANNEL_POST_CANCELLED = "❌ Post bekor qilindi — kanalga chiqmaydi."
CHANNEL_POST_EDIT_ASK = (
    "✏️ Post uchun yangi matnni yuboring (qalin, kursiv kabi bezaklar saqlanadi).\n"
    "Post 30 daqiqa kutadi; matn kelmasa, avvalgi holida chiqadi. Bekor qilish: /cancel"
)
CHANNEL_POST_EDITED = "✅ Matn yangilandi — post kanalga joylanmoqda."
CHANNEL_POST_EDIT_KEPT = "Matn o'zgarmadi: post 30 daqiqadan keyin avvalgi holida chiqadi."
CHANNEL_POST_TEXT_ONLY = "Iltimos, post matnini oddiy xabar qilib yuboring yoki /cancel"
STICKER_DUPLICATE = "Bu stiker allaqachon saqlangan (jami {total} ta). Boshqasini yuboring yoki /tayyor"
STICKER_ONLY = "Stiker yuboring yoki /tayyor deb yozing."
STICKER_DONE = "👍 Tayyor! Stikerlar ro'yxatini Admin panel → 📢 Kanal sahifasida ko'rasiz va keraksizini o'chirasiz."

# ---- Portfolio ----
BTN_PORTFOLIO = "🗂 Portfolio (PDF)"
PORTFOLIO_PREPARING = "🗂 Portfoliongiz tayyorlanmoqda…"

# ---- Leaving and coming back ----
ACCOUNT_LEFT = "Siz klubdan chiqqansiz. Qaytish uchun /start bosing."
LEFT_BACK_SELF = (
    "👋 <b>Qaytganingizdan xursandmiz, {name}!</b>\n\n"
    "Siz {days} kun oldin klubdan chiqqansiz. Ma'lumotlaringiz — ballar, sertifikatlar, yutuqlar — hali "
    "saqlanib turibdi.\n\n♻️ Tiklasangiz, hammasi joyida qoladi. Yoki yangidan boshlashingiz mumkin."
)
LEFT_BACK_REQUEST = (
    "👋 <b>Qaytganingizdan xursandmiz!</b>\n\n"
    "Siz {days} kun oldin klubdan chiqqansiz. Ma'lumotlaringizni tiklash uchun klub rahbariyatiga so'rov "
    "yuboring — yoki yangidan ro'yxatdan o'ting."
)
LEFT_REQUEST_WAITING = "📨 Tiklash so'rovingiz ko'rib chiqilmoqda — javob kelishi bilan xabar beramiz."
LEFT_REQUEST_SENT = "📨 So'rovingiz klub rahbariyatiga yuborildi. Tasdiqlashlari bilan xabar beramiz."
BTN_RESTORE = "♻️ Ma'lumotlarimni tiklash"
BTN_REQUEST_RESTORE = "📨 Tiklash so'rovini yuborish"
BTN_START_FRESH = "🆕 Yangidan boshlash"
FRESH_CONFIRM = (
    "Eski ma'lumotlaringiz (ballar, sertifikatlar, yutuqlar) <b>butunlay o'chiriladi</b> va yangidan "
    "ro'yxatdan o'tasiz. Davom etasizmi?"
)
BTN_FRESH_YES = "Ha, yangidan boshlayman"
RESTORED = "♻️ Hammasi tiklandi! Xush kelibsiz, {name} 📚"
BTN_LEAVE = "🚪 A'zolikni bekor qilish"
LEAVE_CONFIRM = (
    "🚪 <b>A'zolikni bekor qilasizmi?</b>\n\n"
    "Botdan xabarlar kelmaydi, reytingda ko'rinmaysiz. Ma'lumotlaringiz 30 kun saqlanadi: 14 kun ichida "
    "/start bilan o'zingiz tiklaysiz, keyin — klub rahbariyati orqali. 30 kundan keyin ular butunlay o'chiriladi."
)
BTN_LEAVE_YES = "Ha, chiqaman"
LEFT_DONE = "Siz klubdan chiqdingiz. Qaytmoqchi bo'lsangiz — /start. Kitob o'qishda omad! 📚"
LEAVE_STAFF = "Administratorlar klubdan chiqa olmaydi. Avval bosh administrator huquqlaringizni olib qo'ysin."
RESTORE_APPROVED_ADMIN = "✅ {name} a'zoligi tiklandi, unga xabar yuborildi."
RESTORE_DECLINED_ADMIN = "❌ So'rov rad etildi. Eski ma'lumotlar o'chirildi — u xohlasa yangidan ro'yxatdan o'tadi."
RESTORE_DECLINED_MEMBER = (
    "Tiklash so'rovingiz qabul qilinmadi. Xohlasangiz, /start bosib klubga yangidan qo'shilishingiz mumkin."
)
RESTORE_ADMIN_ONLY = "Bu amal faqat a'zolarni boshqaruvchi adminlar uchun."
RESTORE_DONE_ALREADY = "Bu so'rov allaqachon hal qilingan."
