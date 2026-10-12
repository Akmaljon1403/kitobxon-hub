"""All bot texts (Uzbek, Latin script). Kept in one place so wording can be edited easily.

Style: short sentences, one idea per line, "siz" form, the same names as in the Mini App.
"""

from __future__ import annotations

import sys as _sys
import types as _types

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
BTN_BENEFIT = "🎁 Sizning foydangiz"
BTN_ADMIN = "🛠 Boshqaruv"

# Buttons of the previous menu: members keep the old keyboard until the bot sends a new one.
LEGACY_BUTTONS = {
    "👤 Profilim": BTN_PASSPORT,
    "🔔 Bildirishnomalar": BTN_SETTINGS,
    "ℹ️ Yordam": BTN_HELP,
}
LEGACY_INVITE_BUTTONS = {"👥 Do'stni taklif qilish", "👥 Do'stlar"}

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
ONBOARDING_TOUR = (
    "🧭 <b>Qisqa sayohat: bu yerda nimalar bor?</b>\n\n"
    "📚 <b>Kitoblar</b> — klub o'qiyotgan asarlar va muddatlar. «O'qib tugatdim» deb belgilang — ball olasiz.\n"
    "📅 <b>Tadbirlar</b> — davra suhbatlari. «✅ Qatnashaman» bilan joy band qiling, tadbir kuni "
    "«✅ Davomat» bilan kelganingizni qayd eting.\n"
    "📝 <b>Testlar</b> — o'qilgan kitob bo'yicha bilim sinovi. G'oliblarga sertifikat va sovg'alar.\n"
    "🏆 <b>Reyting va yutuqlar</b> — har bir faollik ball, ballar esa nishon va o'rinlarga aylanadi.\n"
    "🪪 <b>Kitobxon pasporti</b> — QR kodli shaxsiy a'zolik kartangiz.\n"
    "🎁 <b>Sovg'alar</b> — promokodlar va sovg'a o'yinlari.\n\n"
    "Savol tug'ilsa — «❓ Yordam». Hammasi chiroyli ko'rinishda ilovada 👇"
)
ONBOARDING_TRIAL = (
    "🎁 <b>Sizga sovg'a — {days} kunlik Premium!</b>\n\n"
    "Klubga qo'shilganingiz sharafiga Premium o'zi yoqildi: <b>{until}</b> gacha bepul, hech narsa "
    "to'lamaysiz. Shu kunlarda sinab ko'ring:\n\n{perks}\n\n"
    "Ilovada bu imkoniyatlar yonida 💎 belgisi turadi — sinovdan keyin qaysilari Premium ekanini "
    "bilasiz. Yoqsa, Premium'ni bank kartasi yoki Telegram Stars orqali davom ettirish mumkin."
)
ONBOARDING_PREMIUM = (
    "💎 <b>Premium haqida bir og'iz</b>\n\n"
    "Klub hamma uchun bepul. Premium esa qo'shimcha qulayliklar beradi:\n\n{perks}\n\n"
    "To'lov bank kartasi yoki Telegram Stars orqali; tushgan mablag' kitoblar va sovg'alarga sarflanadi."
)
BTN_ONBOARDING_APP = "📱 Ilovani ochish"
BTN_ONBOARDING_PREMIUM = "💎 Premium imkoniyatlari"
REGISTERED_PENDING = (
    "✅ Arizangiz qabul qilindi, {first_name}!\n\nKlub rahbariyati ko'rib chiqqach, shu yerda xabar beramiz."
)
REGISTRATION_CANCELLED = "Ro'yxatdan o'tish to'xtatildi. Qayta boshlash uchun /start ni bosing."
REGISTRATION_EXPIRED = "Bu tugma eskirgan. Davom etish uchun /start ni bosing."
REGISTRATION_TEXT_ONLY = "Iltimos, savolga matn bilan javob bering yoki /cancel ni bosing."

# ---- Required channel subscription ----
SUBSCRIBE_REQUIRED = (
    "📢 <b>Bir qadam qoldi!</b>\n\n"
    "Kitobxon Hub'dan foydalanish uchun klubimiz kanaliga obuna bo'ling: yangi kitoblar, tadbirlar, "
    "test natijalari va sovg'alar haqidagi xabarlar avval o'sha yerda chiqadi.\n\n"
    "1️⃣ Pastdagi kanal tugmasini bosib, «Obuna bo'lish»ni bosing.\n"
    "2️⃣ So'ng shu yerga qaytib, «✅ Obuna bo'ldim» tugmasini bosing."
)
SUBSCRIBE_STILL_MISSING = "Hali obuna ko'rinmayapti: {channels}. Obuna bo'lib, yana bir bor bosing 🙂"
SUBSCRIBE_THANKS = "✅ Rahmat, obuna tasdiqlandi! Davom etamiz 👇"
BTN_SUBSCRIBED = "✅ Obuna bo'ldim"

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
ATTENDANCE_ALREADY = "✅ Siz «{title}» tadbirida qatnashyapsiz. Davomatingiz qayd etilgan."
ATTENDANCE_NONE = "Hozir ochiq davomat yo'q.\n\n{next}Davomat tadbir boshlanishidan biroz oldin o'zi ochiladi."
ATTENDANCE_NEXT = "📅 Keyingi tadbir: «{title}», {when}\n\n"
ATTENDANCE_OK = (
    "✅ Davomatingiz qayd etildi — siz «{title}» tadbirida qatnashyapsiz! 🙌\n"
    "🏆 +{points} ball\n\nTadbir tugagach, taassurotlaringizni so'raymiz."
)
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
BTN_CERTIFICATES = "🎓 Sertifikatlarim (ilovada)"
CERTIFICATES_IN_APP = (
    "🎓 Sertifikatlaringiz endi ilovada: u yerda ko'rasiz, dizaynini tanlaysiz va PDF nusxasini yuklab olasiz 👇"
)
FILE_SENT = "Yuborildi ✅"
FILE_FAILED = "Faylni tayyorlab bo'lmadi. Birozdan keyin qayta urinib ko'ring."
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
SUPPORT_ASK_PAYMENT = (
    "💳 <b>To'lov bo'yicha savol</b>\n\n"
    "Muammoni bitta xabarda yozing: qachon, qancha va nima uchun to'laganingiz. Chek rasmini ham "
    "yuborishingiz mumkin — to'lovlar bilan shug'ullanadigan admin javob beradi.\n\nBekor qilish: /cancel"
)
BTN_WRITE_PAYMENT = "✉️ To'lov bo'yicha yozish"
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
    "<b>Qanday to'laysiz?</b>\n"
    "💳 <b>Bank kartasi</b> (Uzcard, Humo — Click, Payme yoki bank ilovasi orqali) — eng oson yo'l: "
    "summani klub kartasiga o'tkazasiz, chekni yuborasiz, admin tasdiqlagach Premium o'zi yoqiladi.\n"
    "⭐ <b>Telegram Stars</b> — Telegram ichidagi to'lov, bir zumda yoqiladi.\n\n"
    "Tushgan mablag' klub tadbirlari, kitoblar va sovg'alarga sarflanadi."
)
BTN_PAY_STARS = "⭐ Telegram Stars orqali"
BTN_BACK_TO_METHODS = "⬅️ To'lov usullari"
PREMIUM_STARS_CHOOSE = (
    "⭐ <b>Telegram Stars orqali</b>\n\nTarifni tanlang — to'lov Telegram ichida bir zumda o'tadi va "
    "Premium darhol yoqiladi.\n\nStars'ingiz yo'qmi? «⬅️ To'lov usullari» → «💳 Bank kartasi» — "
    "u yerda Stars'ni ham karta orqali olish mumkin."
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
    "🤝 <b>Klubni qo'llab-quvvatlash</b>\n\n"
    "Kitobxonlar klubi talabalar tashabbusi bilan yashaydi: yangi kitoblar, davra suhbatlari va "
    "g'oliblarga sovg'alar. Klub sizga yoqsa va imkoningiz bo'lsa, istalgan miqdorda hissa qo'shishingiz "
    "mumkin. Bu mutlaqo ixtiyoriy — botdagi barcha asosiy imkoniyatlar baribir hamma uchun ochiq. 💛\n\n"
    "Qulay usulni tanlang:"
)
BTN_DONATE_CARD = "💳 Bank kartasiga o'tkazish"
DONATE_CARD = (
    "💳 <b>Klub kartasi</b>\n\n<code>{number}</code>\n{holder}\n"
    "Raqamni bosib nusxa oling va xohlagan summani o'tkazing (Click, Payme yoki bank ilovasi). "
    "Chek yuborish shart emas — bu sizning sovg'angiz. 🙏"
)
BTN_DONATE_DONE = "💛 O'tkazdim"
DONATE_THANKS = (
    "💛 <b>Chin dildan rahmat!</b>\n\n"
    "Hissangiz yangi kitoblarga, qiziqarli tadbirlarga va g'oliblarning quvonchiga aylanadi. "
    "Klubimizni birga rivojlantirayotganingiz uchun minnatdormiz! 📚✨"
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
    "Karta yoki Stars to'lovi, Premium yoki qaytarish (refund) haqida savolingizni pastdagi tugma orqali "
    "yozing — to'lovlar bilan shug'ullanadigan admin tez orada javob beradi."
)

# ---- Event feedback ----
FEEDBACK_THANKS = "Rahmat! Bahoyingiz: {stars} ({rating}/5)."
FEEDBACK_ASK_COMMENT = "Xohlasangiz, tadbir haqida fikringizni yozing — nima yoqdi, nimani yaxshilash kerak?"
BTN_FEEDBACK_COMMENT = "✍️ Fikr yozish"
FEEDBACK_COMMENT_SAVED = "✅ Fikringiz klub rahbariyatiga yetkazildi. Rahmat!"
FEEDBACK_NOT_ALLOWED = "Bu tadbirga baho bera olmaysiz."


# ---- Card payments ----
BTN_PAY_CARD = "💳 Bank kartasi orqali (Uzcard / Humo)"
CARD_CHOOSE = (
    "💳 <b>Bank kartasi orqali</b>\n\n"
    "1️⃣ Pastdan tarifni tanlang.\n"
    "2️⃣ Summani klub kartasiga o'tkazing (Click, Payme yoki bank ilovasi).\n"
    "3️⃣ To'lov chekini (skrinshot) shu yerga yuboring — admin tasdiqlagach Premium o'zi yoqiladi.\n\n"
    "⭐ Telegram Stars kerakmi? «⭐ Stars sotib olish» tugmasini bosing."
)
CARD_CHOOSE_STARS_ONLY = (
    "💳 <b>Bank kartasi orqali</b>\n\n"
    "Premium tariflari hozir yopiq, lekin Telegram Stars'ni karta orqali sotib olishingiz mumkin — "
    "«⭐ Stars sotib olish» tugmasini bosing."
)
BTN_BUY_STARS = "⭐ Stars sotib olish"
CARD_STARS_MENU = (
    "⭐ <b>Telegram Stars sotib olish</b>\n\n"
    "{packages}\n\n"
    "Kerakli miqdorni tanlang → summani klub kartasiga o'tkazing → chekni shu yerga yuboring. Admin "
    "tasdiqlagach Stars Telegram'da sizga <b>sovg'a qilib</b> yuboriladi va bot xabar beradi.\n"
    "ℹ️ Buning uchun Telegram profilingizda <b>username</b> bo'lishi kerak."
)
CARD_STARS_LINE = "• <b>{stars} ⭐</b> — {price}"
CARD_PLAN = "💎 {title} — {price}"
CARD_STARS = "⭐ {stars} — {price}"
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
    "⏳ <b>Chekingiz administratorga tekshirish uchun yuborildi.</b>\n\n"
    "Odatda bir kun ichida ko'rib chiqiladi — natijasini shu yerda xabar qilamiz, Premium esa o'zi "
    "yoqiladi. Savol bo'lsa: /paysupport. Rahmat!"
)
CARD_OFF = "💳 Karta orqali to'lov hozircha yoqilmagan."

# ---- Card payments: the super admin's side ----
CARD_ADMIN_ONLY = "Bu tugma faqat bosh administrator uchun."
CARD_RECEIPT_CAPTION = "🧾 <b>{what}</b> — {price}\nA'zo: {name}\nHolat: {status}"
CARD_APPROVED = "✅ Tasdiqlandi: {name} — {price}. A'zoga xabar yuborildi."
CARD_REJECT_ASK = "❌ Rad etish sababini yozing (a'zo shuni ko'radi), masalan: «Summa to'liq emas»."
CARD_REJECT_ASK_PRIVATE = "❌ «{what}» ({name}) to'lovini rad etish sababini shu yerga yozing — a'zo shuni ko'radi."
CARD_REJECT_PICK = "Rad etish sababini tanlang (a'zo shuni ko'radi):"
CARD_REJECT_REASONS = (
    "Chek o'qilmayapti yoki to'liq emas",
    "Summa tarif narxiga mos emas",
    "To'lov kartaga kelib tushmagan",
)
CARD_REJECTED = "❌ Rad etildi. A'zoga sabab bilan xabar yuborildi."
CARD_DM_FIRST = "Avval botga shaxsiy yozing (/start), so'ng qayta bosing."
CARD_LINE_APPROVED = "✅ Tasdiqlandi — {admin}, {time}"
CARD_LINE_REJECTED = "❌ Rad etildi — {admin}, {time}. Sabab: {reason}"
CARD_LINE_UNDONE = "↩️ Qaytarildi — {admin}, {time}: qayta ko'rib chiqing"
CARD_LINE_SENT = "⭐ Stars yuborildi — {admin}, {time}"
SUPPORT_PAYMENT_SUPER_ONLY = "To'lov bo'yicha savollarga faqat bosh admin javob beradi."
SUPPORT_PAYMENT_NO_RIGHT = (
    "To'lov bo'yicha savollarga bosh admin va «💳 To'lov savollari» huquqi berilgan adminlar javob beradi."
)
SUPPORT_TICKET_GONE = "Bu murojaat topilmadi (o'chirilgan bo'lishi mumkin)."
SUPPORT_THREAD_PHOTO = "📷 A'zo yuborgan rasm"
SUPPORT_CLOSED = "🔒 Yopildi — barcha nusxalarda ko'rinadi."
CARD_LINE_STARS_ORDERED = "⭐ Yuborish topshirildi: {senders} (ko'rsatma ularga shaxsiy xabarda)"
STARS_SENDER_ONLY = "Bu tugma bosh admin va «⭐ Stars yuborish» huquqi berilgan adminlar uchun."
BTN_UNDO = "↩️ Qaytarish"
BTN_VIEW_RECEIPT = "🧾 Chekni ko'rish"
BTN_REJECT_OTHER = "✍️ Boshqa sabab"
BTN_BACK = "⬅️ Orqaga"

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
STICKER_ONLY = "Stiker (yoki premium emojili xabar) yuboring yoki /tayyor deb yozing."
EMOJI_ASK = (
    "✨ <b>Premium emojilar</b>\n\n"
    "Bot xabarlaridagi oddiy emojilar o'rniga klubning premium emojilari chiqadi (masalan «Salom ✋» dagi ✋). "
    "Menga premium emojilarni yuboring:\n"
    "• shunchaki premium emoji — u o'zining oddiy ko'rinishi o'rniga ishlatiladi;\n"
    "• yoki juftlik: <code>✋ =</code> [premium emoji] — aynan shu oddiy emoji o'rniga.\n"
    "Bir xabarda bir nechtasini yuborish mumkin. Stiker yuborsangiz — u stikerlar ro'yxatiga qo'shiladi. "
    "Tugatish: /tayyor\n\n"
    "Saqlangan: <b>{count}</b> ta{items}\n\n{status}"
)
EMOJI_SAVED = "✅ Saqlandi: {emoji} ({count} ta). Jami: {total} ta. Yana yuboring yoki /tayyor."
EMOJI_SAMPLE = "🧪 Namuna — a'zolar bot xabarlarida shunday ko'radi:\n{sample}"
EMOJI_STATUS_WORKING = (
    "✅ <b>Holat:</b> Telegram premium emojini qabul qilyapti — a'zolar xabarlarda premium emojini ko'radi."
)
EMOJI_STATUS_UNKNOWN = "ℹ️ <b>Holat:</b> hali tekshirilmagan — «🧪 Tekshirish» tugmasini bosing."
EMOJI_STATUS_GROUP = (
    "ℹ️ <b>Holat:</b> kanal yoki guruhda Telegram premium emojini rad etdi — u yerda oddiy emojilar. "
    "Kanallarda premium emoji faqat Fragment username bilan ishlaydi; shaxsiy xabarlar uchun «🧪 Tekshirish»ni bosing."
)
EMOJI_STATUS_REFUSED = (
    "⚠️ <b>Holat: Telegram premium emojini rad etdi</b> — shuning uchun xabarlar oddiy emoji bilan ketyapti.\n\n"
    "<b>Sabab:</b> Telegram qoidasiga ko'ra bot premium emojini faqat <b>bot egasida</b> (botni @BotFather'da yaratgan "
    "akkauntda) Telegram Premium bo'lsa ishlata oladi. Emojilarni kiritgan adminning Premium'i hisobga olinmaydi.\n\n"
    "<b>Yechim</b> (bittasi yetarli):\n"
    "1) bot egasining akkauntiga Telegram Premium olish — eng oson yo'l;\n"
    "2) @BotFather → botingiz → Bot Settings → Transfer Ownership: botni Premium'i bor ishonchli adminga o'tkazish "
    "(u botning to'liq egasi bo'ladi — ehtiyot bo'ling);\n"
    "3) Fragment'da botga qo'shimcha username sotib olish (qimmat, lekin kanallarda ham ishlaydi).\n\n"
    "Emojilar saqlanib turadi: ruxsat paydo bo'lishi bilan bot ularni o'zi ishlata boshlaydi (har soatda qayta "
    "urinadi yoki «🧪 Tekshirish»ni bosing)."
)
EMOJI_NONE_FOUND = (
    "Bu xabarda premium emoji topilmadi. Premium emojini oddiy xabar qilib yuboring (Telegram Premium kerak), "
    "stiker yuboring yoki /tayyor."
)
EMOJI_DONE = "✨ Tayyor! Holatini istalgan vaqtda /emoji orqali ko'rasiz."
EMOJI_CLEARED = "🗑 Barcha premium emojilar o'chirildi — xabarlarda oddiy emojilar."
BTN_EMOJI_TEST = "🧪 Tekshirish"
DECOR_NO_RIGHT = (
    "Stiker va premium emojilarni qo'shish uchun «A'zolarga xabar yuborish» yoki «Tizim sozlamalari» huquqi kerak. "
    "Bosh admin buni Admin panel → 👥 Adminlar bo'limida beradi."
)
DECOR_OFFER_STICKER = "🎨 Bu stikerni bot va kanal stikerlari ro'yxatiga qo'shaymi?"
DECOR_OFFER_EMOJI = "✨ Bu xabarda {count} ta premium emoji bor. Bot xabarlarida ishlatish uchun saqlaymi?"
BTN_DECOR_SAVE = "✅ Ha, saqlash"
BTN_DECOR_SKIP = "Yo'q"
DECOR_SKIPPED = "Mayli, saqlanmadi."
DECOR_STICKER_ADDED = "✅ Stiker saqlandi ({mood}). Jami stikerlar: {total} ta."
DECOR_STICKER_KNOWN = "Bu stiker allaqachon saqlangan (jami {total} ta)."
DECOR_EMOJI_ADDED = "✅ Premium emoji saqlandi: {emoji}. Jami: {total} ta."
DECOR_EXPIRED = "Bu taklif eskirgan — stikerni yoki emojini qaytadan yuboring."
STICKER_FROM_EMOJI = "🎨 Bu stiker — stikerlar ro'yxatiga qo'shildi ({mood}). Jami stikerlar: {total} ta."
EMOJI_FROM_STICKER_MODE = "✨ Xabardagi premium emojilar ham saqlandi: {emoji}. Jami premium emojilar: {total} ta."
BTN_EMOJI_CLEAR = "🗑 Hammasini o'chirish"
STICKER_DONE = "👍 Tayyor! Stikerlar ro'yxatini Admin panel → 📢 Kanal sahifasida ko'rasiz va keraksizini o'chirasiz."

# ---- Portfolio ----
BTN_PORTFOLIO = "🗂 Portfolio (PDF)"
BTN_INVITE = "🎁 Sizning foydangiz"
BTN_SHARE_INVITE = "📤 Do'stlarga yuborish"
INVITE = (
    "🎁 <b>Sizning foydangiz</b>\n\n"
    "🔗 Shaxsiy taklif havolangiz:\n{link}\n\n"
    "Do'stingiz shu havola orqali ro'yxatdan o'tib, birinchi tadbirga kelsa — sizga {reward}.{limit}"
)
INVITE_SUMMARY = (
    "\n\n📊 <b>Qisqacha</b>\n"
    "👥 Taklif qilganlaringiz: <b>{invited}</b> · tadbirga kelgan: <b>{came}</b>\n"
    "⭐ Ular to'plagan jami ball: <b>{points}</b>\n"
    "📚 Ular o'qigan kitoblar: <b>{books}</b>\n"
    "🎁 Sizga taklif uchun: <b>+{earned} ball</b>{premium}"
)
INVITE_PREMIUM_EARNED = " va <b>{days} kun 💎 Premium</b>"
INVITE_NONE_YET = "\n\n🌱 Hali hech kimni taklif qilmagansiz — havolani do'stlaringizga yuboring!"
INVITE_FRIENDS = "\n\n👥 <b>Do'stlaringiz</b>\n{rows}"
INVITE_FRIEND_POINTS = "{number}. {name} — ⭐ {points} ball{mark}"
INVITE_FRIEND_NAME = "{number}. {name}{mark}"
INVITE_FRIEND_CAME = " ✅"
INVITE_FRIEND_WAITING = " ⏳"
INVITE_FRIENDS_MORE = "\n… va yana {count} ta — barchasi ilovada"
INVITE_FRIENDS_LEGEND = "\n<i>✅ tadbirga keldi · ⏳ hali kelmadi</i>"
INVITE_PLACE = "\n\n🏅 Eng faol taklif qiluvchilar orasida: <b>{place}-o'rin</b>"
BTN_INVITE_DETAILS = "🎁 Batafsil: do'stlarim va tanlovlar"
INVITE_LIMIT = " (oyiga {limit} tagacha)"
INVITE_SHARE_TEXT = "Kitobxonlar klubiga qo'shil! Tadbirlar, testlar, sertifikatlar va sovg'alar 📚"
INVITE_UNAVAILABLE = "Taklif havolasi hozircha tayyor emas. Birozdan keyin urinib ko'ring."
PORTFOLIO_PREPARING = "🗂 Portfoliongiz tayyorlanmoqda…"

# ---- Leaving and coming back ----
ACCOUNT_LEFT = "Siz klubdan chiqqansiz. Qaytish uchun /start bosing."
LEFT_RESTRICTED = (
    "🚪 <b>A'zoligingiz bekor qilingan</b>\n\n"
    "Shu sababli bot hozir buyruqlarni qabul qilmaydi. Ikki yo'l bor:\n"
    "• «🔄 Qayta tiklash» — klubga qaytasiz (muddat o'tmagan bo'lsa, ballaringiz bilan);\n"
    "• «🧹 Chatni tozalash» — bot yuborgan xabarlar o'chiriladi. Chatni butunlay o'chirish uchun: "
    "chat tepasidagi ⋮ → «Chatni o'chirish»."
)
LEFT_WIPED = (
    "🧹 Tozalandi. Chatni butunlay olib tashlash uchun: tepadagi ⋮ → «Chatni o'chirish». "
    "Qaytmoqchi bo'lsangiz — /start. Sizni yana kutamiz! 📚"
)
BTN_LEFT_RESTORE = "🔄 Qayta tiklash"
BTN_LEFT_WIPE = "🧹 Chatni tozalash"
GRADUATED = (
    "🎓 Tabriklaymiz, bitiruvchi! Siz klubda qolasiz — tadbirlar, kitoblar va do'stlar sizni kutadi. "
    "Yangi kitobxonlarni ham olib keling 📚"
)
STILL_STUDYING = (
    "📚 Yaxshi, yangi o'quv yilida omad! Kurs yoki guruhingiz o'zgargan bo'lsa, ilovada profilingizni to'g'rilang."
)
STILL_HERE = "Ajoyib! 👋 Siz bilan davom etamiz — yangi kitob va tadbirlardan xabardor bo'lib turing."
WELCOME_BACK_AFTER_BREAK = "🎉 Qaytganingiz bilan! Hisobingiz yana faol — ballaringiz va yutuqlaringiz joyida."
STOPPED = "⏹ To'xtatildi. Oldingi amal bekor qilindi — pastdagi menyudan davom eting."
BTN_FAQ = "❓ Savol-javoblar"
BTN_FAQ_APP = "📱 Barchasi ilovada"
BTN_FAQ_BACK = "⬅️ Mavzular"
FAQ_TOPICS = "❓ <b>Savol-javoblar</b>\n\nMavzuni tanlang — eng ko'p so'raladigan savollarga javob tayyor:"
LIMITED_ACCOUNT_HINT = "\n\nSavolingiz bo'lsa — «✉️ Adminga yozish»."
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

# ---- Events and books opened from the channel ----
EVENT_NOT_FOUND = "Bu tadbir topilmadi yoki o'chirilgan."
BOOK_NOT_FOUND = "Bu kitob topilmadi yoki o'chirilgan."
EVENT_ATTENDING = "✅ Siz bu tadbirda qatnashyapsiz — davomatingiz qayd etilgan."
EVENT_ATTENDED = "✅ Siz bu tadbirda qatnashgansiz. Rahmat!"
EVENT_REGISTRATION_CLOSED = "Bu tadbirga ro'yxatdan o'tish yopilgan."
EVENT_PICK_SHIFT = "Qaysi smenada kelasiz? Tanlang 👇"
EVENT_YOUR_SHIFT = "✅ Siz ro'yxatdasiz: <b>{shift}</b>. Boshqa smenaga o'tish uchun uni tanlang."
EVENT_REGISTERED = "✅ Siz ro'yxatdasiz — tadbir oldidan eslatma yuboramiz."
EVENT_WHY_REGISTER = (
    "✋ Kelmoqchimisiz? «✅ Qatnashaman»ni bosing: joylarni shunga qarab tayyorlaymiz, "
    "sizga tadbir oldidan va davomat ochilganda eslatma yuboramiz."
)
EVENT_REGISTERED_ALERT = "✅ Ro'yxatga oldik! Tadbir oldidan eslatamiz."
EVENT_UNREGISTERED = "Ro'yxatdan chiqdingiz."
BTN_ATTEND = "✅ Qatnashaman"
BTN_UNREGISTER = "❌ Kela olmayman"
BOOK_START_HINT = "«📖 O'qishni boshladim» tugmasini bosing — o'qish eslatmalari va maslahatlar keladi."
BTN_START_READING = "📖 O'qishni boshladim"
BOOK_STARTED = "📖 Zo'r! Kitob «O'qiyapman» ro'yxatingizga qo'shildi. Tugatganingizda ilovada belgilang ✅"
SUPER_ADMIN_ONLY = "Bu amal faqat bosh administrator uchun."
ATTENDANCE_APPROVED = "✅ Tasdiqlandi — a'zoga ball berildi."
ATTENDANCE_REJECTED = "❌ So'rov rad etildi."


# ---- Channels and groups the bot is added to ----
CHAT_ROLE_ASK = (
    "🔔 Bot «<b>{title}</b>» ga administrator qilib qo'shildi.\n\n"
    "Bu kanal (guruh) nima uchun?\n"
    "💳 <b>To'lovlar kanali</b> — cheklar (✅/❌ tugmalari bilan), to'lov bo'yicha savollar, Stars to'lovlari va "
    "haftalik moliyaviy xulosa shu yerga keladi; sizning shaxsiy chatingiz toza qoladi.\n"
    "📣 <b>Klub kanali</b> — bot yangi kitob, tadbir va natijalar haqida post joylaydi."
)
BTN_CHAT_PAYMENTS = "💳 To'lovlar kanali"
BTN_CHAT_CLUB = "📣 Klub kanali"
BTN_CHAT_NONE = "Hech biri"
CHAT_ROLE_NONE = "Mayli, hech narsa o'zgarmadi."
CHAT_ROLE_UNREACHABLE = "Kanalni ko'ra olmadim. Bot hali ham u yerda administratormi?"
CHAT_ROLE_PAYMENTS_DONE = (
    "✅ «<b>{title}</b>» endi <b>to'lovlar kanali</b>. Cheklar, to'lov savollari va Stars to'lovlari faqat shu yerga "
    "keladi. Kanalga sinov xabari yuborildi."
)
CHAT_ROLE_CLUB_DONE = "✅ «<b>{title}</b>» endi <b>klub kanali</b>: bot postlari shu yerga joylanadi."
CHAT_PAYMENTS_LOST = (
    "⚠️ Bot «<b>{title}</b>» to'lovlar kanalidan chiqarildi yoki adminlikdan olindi. Cheklar endi sizga botda keladi. "
    "Davom ettirish uchun botni kanalga qayta administrator qiling."
)

# ---- My reading: /oqidim, /javonim, /kartam ----
BTN_SHELF_APP = "📚 Javonim"
BTN_MISSIONS_APP = "🎯 Missiyalar"
BTN_QUOTES_APP = "💬 Iqtiboslarim"
READ_NO_BOOK = (
    "📚 Hozir «O'qiyapman» javoningizda kitob yo'q.\n\n"
    "Ilovada <b>📚 Javonim</b> → kitob qo'shing (klub kitobi yoki o'zingizniki) va «O'qiyapman» deb belgilang. "
    "So'ng shu yerda yozasiz: <code>/oqidim 25</code> — bugun 25 bet o'qidim."
)
READ_HOW = (
    "📖 <b>Mutolaa kundaligi</b>\n\nHozir o'qiyapsiz: <b>{title}</b>\n"
    "Bugun: {today} bet · 🔥 seriya: {streak} kun\n\n"
    "Yozish: <code>/oqidim 25</code> — bugun 25 bet o'qidim.\n"
    "Izoh bilan: <code>/oqidim 25 Juda qiziq bob edi</code>"
)
READ_PROGRESS = "{read}/{total} bet ({percent}%)"
READ_PROGRESS_PAGES = "{read} bet"
READ_LOGGED = (
    "✅ Kundalikka yozildi: <b>{title}</b> — +{pages} bet\n"
    "📖 {progress}\n"
    "Bugun jami: {today} bet · 🔥 seriya: {streak} kun"
)
READ_MAYBE_DONE = (
    "\n\n📗 Kitobni tugatdingizmi? Ilovada «O'qib bo'ldim» deb belgilang va «Kitobdan keyin 3 savol»ga "
    "javob yozing — ball beriladi."
)
SHELF_SUMMARY = (
    "📚 <b>Javonim</b>\n\n"
    "<b>O'qiyapman:</b>\n{reading}\n\n"
    "O'qimoqchiman: {want} · O'qib bo'ldim: {finished} · Keyinroq: {later}\n"
    "📖 Bu hafta: {week} bet · 🔥 seriya: {streak} kun (eng uzuni {best})\n"
    "🏁 Bu yil o'qilgan kitoblar: {year}\n\n"
    "Bugun o'qiganingizni yozing: <code>/oqidim 25</code>"
)
SHELF_LINE = "• {title} — {progress}"
SHELF_NOTHING = "• hozircha yo'q"
CARD_CAPTION = (
    "🪪 <b>Kitobxonlik kartangiz</b> — o'qigan kitoblar, betlar, seriya va yutuqlaringiz.\n"
    "Do'stlaringizga ulashing: rasmni bosib turing → «Ulashish»."
)

# ---- «💬 A'zolar fikrlari» (/fikr) ----
BTN_COMMUNITY_FEED = "📖 Lentani o'qish"
BTN_COMMUNITY_APP = "📱 Ilovada yozish (kitob yoki tadbir tanlab)"
COMMUNITY_START = (
    "💬 <b>A'zolar fikrlari</b>\n\n"
    "Kitobdan yoqqan iqtibosingiz, o'z fikringiz yoki klub haqidagi e'tirofingizni yozing. Eng yaxshilari "
    "chiroyli kartochka bo'lib klub kanalida va boshqa kitobxonlarga yuboriladi, sizga esa ball beriladi.\n\n"
    "Nima yozasiz?"
)
COMMUNITY_ASK_TEXT = {
    "QUOTE": "📖 Iqtibosni yozing (kitobdagidek, {min}–{max} belgi). Bekor qilish: /cancel",
    "THOUGHT": "💡 Fikringizni yozing ({min}–{max} belgi). Bekor qilish: /cancel",
    "CLUB": "🌟 Klub haqida e'tirofingizni yozing — klub sizga nima berdi? ({min}–{max} belgi). Bekor qilish: /cancel",
}
COMMUNITY_ASK_SOURCE = (
    "✍️ Kim aytgan yoki qaysi kitobdan? Masalan: <i>Abdulla Qodiriy — O'tkan kunlar</i>.\nBilmasangiz — "
    "«O'tkazib yuborish»."
)
BTN_SKIP = "O'tkazib yuborish"
COMMUNITY_TEXT_ONLY = "Iltimos, matn yozing yoki /cancel"
COMMUNITY_SENT_PENDING = (
    "✅ Rahmat! Yuborildi. Admin ko'rib chiqqach «💬 A'zolar fikrlari» lentasida chiqadi va sizga xabar beramiz.{box}"
)
COMMUNITY_SENT_LIVE = "✅ Rahmat! «💬 A'zolar fikrlari» lentasiga qo'shildi.{box}"
COMMUNITY_SENT_BOX = "\n💬 Nusxasi «Iqtiboslar sandig'i»ngizda ham saqlandi."
BTN_COMMUNITY_CARD = "🖼 Kartochkasini olish"
COMMUNITY_CARD_CAPTION = "💬 Kartochka tayyor — do'stlaringizga ulashing (rasmni bosib turing → «Ulashish»)."
COMMUNITY_EVENT_OFFER = (
    "💬 Fikringizni boshqa kitobxonlar ham o'qisinmi? «A'zolar fikrlari» lentasiga yuboraymi? "
    "(eng yaxshilari klub kanalida chiqadi)"
)
BTN_COMMUNITY_EVENT_YES = "✅ Ha, yuboring"
BTN_COMMUNITY_EVENT_NO = "Yo'q, rahmat"
COMMUNITY_EVENT_NO = "Mayli, fikringiz faqat klub rahbariyatida qoladi."
COMMUNITY_NO_RIGHT = "Bu tugma «A'zolar fikrlari» huquqi bor adminlar uchun."
COMMUNITY_DONE = {
    "approve": "✅ Lentaga qo'shildi — {admin}",
    "feature": "⭐ Tanlanganlarga qo'shildi — {admin}",
    "hide": "🙈 Yashirildi — {admin}",
}

# ---- Answers in the payments channel («Reply») ----
PAYCHAT_SENT = "✅ A'zoga yuborildi: {name}"
PAYCHAT_TEXT_ONLY = "⚠️ Faqat matn yuboriladi — javobni so'z bilan yozing."
PAYCHAT_FAILED = "⚠️ Yuborilmadi: {reason}"
PAYCHAT_SUPER_ONLY = (
    "⚠️ To'lov masalalarida a'zoga bosh admin va «💳 To'lov savollari» huquqi berilgan adminlar javob beradi."
)
PAYCHAT_ABOUT_CARD = "to'lovingiz bo'yicha: {what}, {amount}"
PAYCHAT_ABOUT_USER = "to'lovingiz bo'yicha"
SUPPORT_REPLY_CHANNEL_HINT = (
    "✍️ Endi shu yerning o'zida savolga «Reply» qilib javobingizni yozing — u a'zoga «Klub rahbariyati» "
    "nomidan boradi. Boshqa adminlar savolni siz olganingizni ko'radi."
)

# ---- «What is this channel's id?» (an admin forwards a channel post) ----
CHAT_ID_INFO = (
    "🆔 <b>{title}</b>\n\n"
    "ID raqami: <code>{chat_id}</code>\n"
    "{username}"
    "\nSozlamalarda kanal manzili sifatida shu raqamni (yoki @username'ni) yozasiz. «-100» — Telegram kanal va "
    "guruhlar ID'sining boshidagi belgilanishi, raqamning bir qismi: uni o'chirmang.\n\n"
    "Eng osoni: botni shu kanalga administrator qiling — bot o'zi «Bu kanal nima uchun?» deb so'raydi va "
    "hammasini o'zi yozib qo'yadi."
)
CHAT_ID_USERNAME = "Ochiq manzil: @{username}\n"
CHAT_ID_HIDDEN = (
    "🆔 Bu forward'da kanal ma'lumoti yashirilgan. Kanaldan postni boshqa forward qiling yoki botni kanalga "
    "administrator qiling — bot o'zi so'raydi."
)


# ---- Live wording -------------------------------------------------------------------------------------
# The owner can rewrite any text above in the Admin Panel («📝 Matnlar»), and many have several variants so
# members do not read the same sentence every time (``text_store``). Button captions stay as they are: the
# bot recognises the menu by them.
FIXED_PREFIXES = ("BTN_",)


class _LiveTexts(_types.ModuleType):
    def __getattribute__(self, name: str) -> object:
        value = _types.ModuleType.__getattribute__(self, name)
        if type(value) is str and name[:1].isupper() and not name.startswith(FIXED_PREFIXES):
            from app.bot import text_store

            return text_store.pick(name, value)
        return value


_sys.modules[__name__].__class__ = _LiveTexts
