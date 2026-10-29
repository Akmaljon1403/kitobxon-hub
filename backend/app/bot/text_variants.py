"""Built-in variants of the messages members see again and again, so the bot does not repeat itself.

The key is a bot text (``texts.WELCOME_BACK``) or a member notification template (``notify.EVENT_REMINDER``).
Together with the wording in the code each one has five ways to say the same thing; ``text_store`` sends
them in turn (never the same one twice in a row). The owner can switch rotation off, rewrite any of them or
add their own in the Admin Panel («📝 Matnlar»).

Rules for a variant: the same ``{placeholders}`` as the original (no new ones), Telegram HTML only
(<b>, <i>, <u>, <s>, <code>, <a>, <blockquote>), the same meaning — only the words change.
"""

from __future__ import annotations

VARIANTS: dict[str, tuple[str, ...]] = {
    # ---- the bot's everyday answers ----
    "WELCOME_BACK": (
        "Xush kelibsiz, {first_name}! 📚\nBugun qaysi bo'limga kiramiz? Pastdagi menyudan tanlang.",
        "Yana ko'rishganimizdan xursandmiz, {first_name}! ☕\nKitoblar, tadbirlar va natijalar — pastdagi menyuda.",
        "Salom, {first_name}! 👋\nKlub hayoti davom etmoqda — kerakli bo'limni pastdan tanlang.",
        "Assalomu alaykum, {first_name}! 🌿\nSahifalar sizni kutyapti. Menyudan kerakli bo'limni oching.",
    ),
    "MENU_UPDATED": (
        "✨ Menyu yangilandi — barcha bo'limlar pastdagi tugmalarda.",
        "Tayyor! Menyu yangi ko'rinishda ✨ Pastdagi tugmalardan foydalaning.",
        "🔄 Menyu yangilandi. Kerakli bo'limni pastdan tanlang.",
        "Menyu qayta joylandi ✅ Endi hamma bo'lim qo'lingiz ostida.",
    ),
    "SUPPORT_SENT": (
        "✅ Xabaringiz klub rahbariyatiga yetib bordi. Javobni shu yerda olasiz.",
        "📨 Qabul qilindi! Tez orada javob beramiz — shu chatni kuzatib boring.",
        "✅ Yuborildi. Savolingiz e'tiborsiz qolmaydi — javob shu yerga keladi.",
        "🙏 Rahmat, xabaringiz qabul qilindi. Javob tayyor bo'lishi bilan shu yerda yozamiz.",
    ),
    "SUPPORT_REPLY_SENT": (
        "✅ Javobingiz a'zoga yuborildi.",
        "📨 Yetkazildi — a'zo javobni «Klub rahbariyati» nomidan oldi.",
        "✅ Tayyor, javob yo'lda.",
        "👌 Javob yuborildi. Boshqa adminlar ham ko'radi.",
    ),
    "ATTENDANCE_OK": (
        "🙌 Xush kelibsiz! «{title}» tadbirida qatnashganingiz qayd etildi.\n🏆 +{points} ball\n\n"
        "Tadbirdan so'ng fikringizni so'raymiz.",
        "✅ Siz ro'yxatdasiz — «{title}»! 📖\n🏆 +{points} ball hisobingizga qo'shildi.\n\nMaroqli suhbat tilaymiz!",
        "🎯 Davomat qabul qilindi: «{title}».\n🏆 +{points} ball\n\nTadbir tugagach, taassurotlaringizni kutamiz.",
        "📚 Kelganingizdan xursandmiz! «{title}» — davomatingiz yozildi.\n🏆 +{points} ball",
    ),
    "ATTENDANCE_ALREADY": (
        "✅ «{title}» — siz allaqachon ro'yxatdasiz. Qayta belgilash shart emas.",
        "👌 Davomatingiz avvalroq qayd etilgan: «{title}».",
        "✅ Siz «{title}» tadbiridasiz — davomat joyida.",
        "Hammasi joyida: «{title}» tadbiridagi davomatingiz yozib qo'yilgan ✅",
    ),
    "UNKNOWN_MESSAGE": (
        "Bu buyruqni tanimadim 🤔 Pastdagi menyudan tanlang yoki /help ni bosing.",
        "Hmm, nima demoqchi ekaningizni tushunmadim 🙂 Menyu pastda, yordam — /help.",
        "Bunday buyruq yo'q 🤔 Kerakli bo'limni menyudan tanlang yoki /help ni bosing.",
        "Kechirasiz, tushunmadim. Menyudagi tugmalardan foydalaning yoki /help ni yozing 📚",
    ),
    "SUBSCRIBE_THANKS": (
        "✅ Obuna tasdiqlandi — rahmat! Endi davom etamiz 👇",
        "🎉 Ajoyib, siz kanalimizdasiz! Davom etamiz 👇",
        "✅ Rahmat! Kanal yangiliklari endi siz bilan. Keyingi qadam 👇",
        "👍 Obuna ko'rindi. Klubga xush kelibsiz — davom etamiz 👇",
    ),
    "SUBSCRIBE_STILL_MISSING": (
        "Obuna hali ko'rinmayapti: {channels}. Obuna bo'lib, tugmani yana bosing 🙂",
        "🤔 Hozircha obuna yo'q: {channels}. Kanalga a'zo bo'lgach, qayta bosing.",
        "Bir qadam qoldi: {channels} kanaliga obuna bo'ling va «✅ Obuna bo'ldim»ni yana bosing.",
        "Obunani tekshirib ko'rdik — {channels} hali yo'q. Obuna bo'lib, qayta urinib ko'ring 🙂",
    ),
    "RESULTS_EMPTY": (
        "📊 Hali ball yo'q — lekin hammasi oldinda!\n\n"
        "Tadbirga keling, test yeching yoki kitobni o'qib tugating — birinchi ballar shu yerda paydo bo'ladi.",
        "📊 Natijalar hozircha bo'sh.\n\nBirinchi ball — eng yoqimlisi: yaqin tadbirga yoki ochiq testga qarang!",
        "📊 Ballaringiz hali yo'q.\n\nHar bir tadbir, test va o'qilgan kitob — ball. "
        "Boshlash uchun eng yaxshi kun — bugun!",
        "📊 Bu yer hozircha toza sahifa ✨\n\nTadbir, test va kitoblar orqali ball to'plang — natijalar shu yerda.",
    ),
    "RANKING_EMPTY": (
        "🏆 Bu oy reyting hali bo'sh — birinchi ballni siz oling!",
        "🏆 Oyning yetakchisi hali yo'q. Navbat sizda!",
        "🏆 Bu oy hech kim ball olmadi. Birinchi bo'lish imkoniyati sizda!",
        "🏆 Reyting jadvali kutmoqda — birinchi qatorni egallang!",
    ),
    "RANKING_ME_NONE": (
        "Bu oy hali ballingiz yo'q — bitta tadbir yoki test buni o'zgartiradi.",
        "Siz bu oy hali reytingda yo'qsiz. Yaqin tadbirga keling!",
        "Bu oy ball to'plashni boshlang — har bir faollik hisoblanadi.",
        "Shu oy hali ball yo'q. Ochiq testga qarang — birinchi qadam oson!",
    ),
    "BOOKS_NONE": (
        "📚 Hozircha faol kitob yo'q. Yangisi tanlanishi bilan xabar beramiz.",
        "📚 Klub navbatdagi asarni tanlamoqda — tez orada e'lon qilamiz.",
        "📚 Faol kitob hozircha yo'q. Bu orada javoningizdagi kitoblarni o'qing!",
        "📚 Yangi kitob hali e'lon qilinmagan. Kuzatib boring — birinchi bo'lib bilasiz.",
    ),
    "EVENTS_NONE": (
        "📅 Hozircha rejalashtirilgan tadbir yo'q. Yangisi e'lon qilinishi bilan xabar beramiz.",
        "📅 Yaqin kunlarda tadbir yo'q — keyingisini tez orada e'lon qilamiz.",
        "📅 Tadbirlar ro'yxati hozircha bo'sh. Kanalimizni kuzatib boring!",
        "📅 Hozir tadbir yo'q. Bu orada kitobni o'qib turamiz 📖",
    ),
    "TESTS_NONE": (
        "📝 Hozircha test yo'q. Yangisi ochilsa, xabar beramiz.",
        "📝 Ochiq test hali yo'q — kitobni o'qishda davom eting!",
        "📝 Testlar ro'yxati bo'sh. Keyingisi e'lon qilinganda shu yerda ko'rinadi.",
        "📝 Hozir test yo'q. Tayyorgarlik uchun ajoyib vaqt 📚",
    ),
    "PASSPORT_PHOTO_SAVED": (
        "✅ Rasm almashtirildi! Mana yangi pasportingiz:",
        "📸 Ajoyib chiqdi! Yangilangan pasportingiz:",
        "✅ Saqlandi. Pasportingiz endi shunday ko'rinadi:",
        "🪪 Rasm joyida! Yangi pasportingiz tayyor:",
    ),
    "FILE_SENT": ("Tayyor ✅", "Yuborildi 📎", "Mana ✅", "Fayl yo'lda 📤"),
    "CARD_RECEIPT_OK": (
        "⏳ <b>Chek qabul qilindi va tekshiruvga yuborildi.</b>\n\n"
        "Odatda bir kun ichida ko'riladi — natijasini shu yerda yozamiz, Premium esa o'zi yoqiladi. "
        "Savol bo'lsa: /paysupport. Rahmat!",
        "🧾 <b>Rahmat, chekingiz administratorda!</b>\n\n"
        "Tekshirilgach shu yerda xabar beramiz va Premium avtomatik yoqiladi. Savollar: /paysupport.",
        "⏳ <b>Chek yetib keldi.</b>\n\n"
        "Admin uni tez orada ko'rib chiqadi (odatda bir kun ichida). Natija shu chatga keladi. "
        "Savol bo'lsa — /paysupport.",
        "✅ <b>Chekingiz tekshiruvda.</b>\n\n"
        "Tasdiqlangach Premium o'zi yoqiladi va shu yerda yozamiz. Kutayotganingiz uchun rahmat! /paysupport",
    ),
    "FEEDBACK_THANKS": (
        "Rahmat! Bahoyingiz qabul qilindi: {stars} ({rating}/5).",
        "🙏 Fikringiz biz uchun muhim! Baho: {stars} ({rating}/5).",
        "Qabul qilindi ✅ {stars} ({rating}/5). Keyingi tadbirlar yanada yaxshi bo'ladi!",
        "Rahmat! {stars} ({rating}/5) — bahoyingiz klub rahbariyatiga yetkazildi.",
    ),
    "FEEDBACK_COMMENT_SAVED": (
        "✅ Fikringiz klub rahbariyatiga yetkazildi. Katta rahmat!",
        "🙏 Rahmat! Taassurotlaringizni albatta inobatga olamiz.",
        "✅ Yozganlaringiz yetib bordi — keyingi tadbirlarda hisobga olamiz.",
        "📨 Fikringiz uchun rahmat! Bunday mulohazalar klubni yaxshilaydi.",
    ),
    "READ_LOGGED": (
        "📖 Yozib qo'ydim: <b>{title}</b> — +{pages} bet\n{progress}\nBugun: {today} bet · 🔥 {streak} kun ketma-ket",
        "✅ +{pages} bet — <b>{title}</b>\n📖 {progress}\nBugungi jami: {today} bet · 🔥 seriya: {streak} kun",
        "🔥 Zo'r! <b>{title}</b>: +{pages} bet\n📖 {progress}\nBugun {today} bet · seriya {streak} kun",
        "📚 Kundalikda: <b>{title}</b> — +{pages} bet\n📖 {progress}\nBugun: {today} bet · 🔥 {streak} kun",
    ),
    "COMMUNITY_SENT_PENDING": (
        "✅ Rahmat! Matningiz adminga yuborildi — tasdiqlangach «💬 A'zolar fikrlari»da chiqadi.",
        "🙏 Qabul qilindi! Admin ko'rib chiqqach lentada chiqadi va sizga xabar beramiz.",
        "✅ Yuborildi! Ko'rib chiqilgach «💬 A'zolar fikrlari» lentasida hamma o'qiydi.",
        "📨 Rahmat! Fikringiz navbatda — tasdiqlanishi bilan lentada paydo bo'ladi.",
    ),
    "COMMUNITY_SENT_LIVE": (
        "✅ Rahmat! Fikringiz «💬 A'zolar fikrlari» lentasida.",
        "🎉 Lentaga chiqdi! Endi boshqa kitobxonlar ham o'qiydi.",
        "✅ Qo'shildi — «💬 A'zolar fikrlari»da hammaga ko'rinadi.",
        "📖 Lentada! Fikringiz uchun rahmat.",
    ),
    "REGISTERED_PENDING": (
        "✅ Arizangiz qabul qilindi, {first_name}! Ko'rib chiqilgach shu yerda xabar beramiz.",
        "📨 Rahmat, {first_name}! Arizangiz klub rahbariyatida — tez orada javob beramiz.",
        "✅ {first_name}, arizangiz yetib bordi. Tasdiqlanishi bilan shu yerda yozamiz.",
        "🙏 Qabul qilindi, {first_name}! Klub rahbariyati arizangizni ko'rib chiqmoqda.",
    ),
    "CANCELLED": ("Bekor qilindi ✅", "To'xtatildi.", "Mayli, bekor qildim.", "Bekor qilindi — menyu pastda."),
    "NOTHING_TO_CANCEL": (
        "Hozir bekor qilinadigan amal yo'q.",
        "Bekor qilishga hech narsa yo'q 🙂",
        "Hech qanday amal kutilmayapti.",
        "Bekor qilinadigan narsa topilmadi.",
    ),
    "TOO_MANY_REQUESTS": (
        "Biroz sekinroq 🙂 Bir necha soniyadan keyin yozing.",
        "Juda tez! Bir oz kuting va qayta urinib ko'ring.",
        "⏳ Bir lahza — so'ng davom etamiz.",
        "Shoshmang 🙂 Bir necha soniya kuting.",
    ),
    # ---- notifications to members (templates; values come from the club's data) ----
    "notify.EVENT_CREATED": (
        "📅 <b>Yangi tadbir: «{event_title}»</b>\n🕒 {starts_at}\n📍 {location}\n\n"
        "Fikrlar almashinadigan, yangi do'stlar orttiriladigan uchrashuv. Joyingizni ilovada band qiling 👇",
        "🎉 <b>Uchrashuv e'lon qilindi: «{event_title}»</b>\n🕒 {starts_at}\n📍 {location}\n\n"
        "Kitob haqida gaplashamiz — siz ham keling! Ilovada «Qatnashaman»ni bosing 👇",
        "📚 <b>«{event_title}» — sizni kutamiz!</b>\n🕒 {starts_at}\n📍 {location}\n\n"
        "Qatnashsangiz, ilovada joyingizni band qiling. Davomat uchun ball beriladi 🏆",
        "✨ <b>Navbatdagi tadbir: «{event_title}»</b>\n🕒 {starts_at}\n📍 {location}\n\n"
        "Kitobni o'qib keling — eng qiziq savollar suhbatda tug'iladi. Ro'yxatdan o'tish ilovada 👇",
    ),
    "notify.EVENT_REMINDER": (
        "⏰ <b>Unutmang:</b> «{event_title}» — {starts_at}.\n📍 {location}\n\nKitobingizni olishni unutmang 📖",
        "🔔 <b>Yaqinda boshlanadi:</b> «{event_title}», {starts_at}.\n📍 {location}\n\nSizni kutamiz!",
        "⏰ «{event_title}» {starts_at} da.\n📍 {location}\n\nDavomat tadbirda ochiladi — ball sizni kutyapti 🏆",
        "📅 <b>Eslatma:</b> {starts_at} — «{event_title}».\n📍 {location}\n\n"
        "Savollaringizni tayyorlab keling — suhbat qiziq bo'ladi ☕",
    ),
    "notify.EVENT_STARTED": (
        "▶️ «{event_title}» boshlandi! Kelayotgan bo'lsangiz — shoshiling 📖",
        "🎬 Tadbir boshlandi: «{event_title}». Davomatni unutmang ✅",
        "▶️ «{event_title}» hozir boshlandi — sizni kutyapmiz!",
        "📚 «{event_title}» davom etmoqda. Kechikkan bo'lsangiz ham keling!",
    ),
    "notify.ATTENDANCE_OPEN": (
        "✅ «{event_title}»: davomat ochildi. Ekrandagi QR kodni skanerlang yoki kodni yozing.",
        "📲 Davomat ochiq — «{event_title}». Botda «✅ Davomat»ni bosing va kodni kiriting.",
        "✅ «{event_title}» tadbiri davomati boshlandi. Qatnashganingizni qayd eting — ball beriladi 🏆",
        "🔓 Davomat ochildi: «{event_title}». QR kod ekranda — bir bosishda belgilaning.",
    ),
    "notify.TEST_STARTED": (
        "📝 <b>Test ochildi: «{test_title}»</b>\n⌛ {ends_at} gacha · ⏱ {duration} daqiqa\n\n"
        "Bilimingizni sinab ko'ring — har bir to'g'ri javob ball 🎯",
        "🧠 <b>Yangi sinov: «{test_title}»</b>\nOchiq: {ends_at} gacha, vaqt — {duration} daqiqa.\n\n"
        "O'qiganlaringizni tekshirib ko'ring!",
        "📝 <b>«{test_title}» — test boshlandi!</b>\n⏱ {duration} daqiqa · ⌛ {ends_at} gacha\n\n"
        "Eng yaxshi natijalarga sovg'alar bor 🎁",
        "🎯 <b>Test vaqti: «{test_title}»</b>\n{ends_at} gacha ochiq, {duration} daqiqa.\n\nOmad!",
    ),
    "notify.TEST_ENDING": (
        "⌛ «{test_title}» {ends_at} da yopiladi. Hali ulgurasiz!",
        "⏳ Oxirgi imkoniyat: «{test_title}» testi {ends_at} gacha.",
        "🏃 «{test_title}» tez orada yopiladi — {ends_at}. Yechib qo'ying!",
        "⌛ Test yopilishiga oz qoldi: «{test_title}», {ends_at}.",
    ),
    "notify.TEST_RESULT": (
        "📊 «{test_title}»: natijangiz — {score} / {max_score} ball.",
        "🎯 «{test_title}» testida {score} / {max_score} ball to'pladingiz.",
        "📊 Natija tayyor: «{test_title}» — {score} / {max_score}.",
        "✅ «{test_title}» yakunlandi. Sizning balingiz: {score} / {max_score}.",
    ),
    "notify.NEW_BOOK": (
        "📚 <b>Navbatdagi kitob: «{book_title}»</b> — {book_author}\n🗓 Muddat: {deadline}\n\n"
        "Birga o'qiymiz, birga muhokama qilamiz! 📖",
        "✨ <b>Yangi asar tanlandi: «{book_title}»</b> — {book_author}\n🗓 O'qish muddati: {deadline}\n\n"
        "Javoningizga qo'shing va bugunoq boshlang!",
        "📖 <b>«{book_title}»</b> — {book_author}\n🗓 {deadline} gacha o'qiymiz.\n\n"
        "O'qib tugatganlarga ball va test kutmoqda 🏆",
        "🔖 <b>Klub kitobi: «{book_title}»</b> — {book_author}\n🗓 Muddat: {deadline}\n\n"
        "Har kuni bir oz — va marra sizniki! 💪",
    ),
    "notify.READING_REMINDER": (
        "📖 «{book_title}» — muddat {deadline} da tugaydi. Oxirgi sahifalarga oz qoldi! 💪",
        "⏳ «{book_title}»ni tugatishga ulguring: muddat {deadline}.",
        "📚 Eslatma: «{book_title}» {deadline} gacha. Kuniga 20 daqiqa — va tamom!",
        "🔖 «{book_title}» sizni kutyapti. Muddat: {deadline} 📖",
    ),
    "notify.QUOTE_OF_DAY": (
        "✨ <b>Bugungi iqtibos</b>\n\n<i>«{quote_text}»</i>\n\n— {quote_author}",
        "💬 <b>Kun so'zi</b>\n\n<i>«{quote_text}»</i>\n\n— {quote_author}",
        "📖 <b>Bir jumla — bir olam</b>\n\n<i>«{quote_text}»</i>\n\n— {quote_author}",
        "🌿 <b>Kun iqtibosi</b>\n\n<i>«{quote_text}»</i>\n\n— {quote_author}",
    ),
    "notify.RANKING_UPDATE": (
        "🏆 Reytingda {rank}-o'rindasiz ({total} ball). Davom eting!",
        "📈 Sizning o'rningiz: {rank} ({total} ball).",
        "🏆 {rank}-o'rin, {total} ball — zo'r natija!",
        "📊 Reyting yangilandi: {rank}-o'rin ({total} ball).",
    ),
    "notify.ACHIEVEMENT_UNLOCKED": (
        "🏅 Yangi yutuq: «{achievement_title}»! Tabriklaymiz ✨",
        "🎉 «{achievement_title}» — sizniki! Kitobxonlik yo'lingizda yangi bekat.",
        "🏅 Tabriklaymiz! «{achievement_title}» yutug'i qo'lga kiritildi.",
        "✨ Ajoyib! Siz «{achievement_title}» nishonini oldingiz.",
    ),
    "notify.REWARD": (
        "🎁 Sizga sovg'a: «{reward_title}»! Batafsil — ilovadagi «Sovg'alarim»da.",
        "🎉 «{reward_title}» sovg'asi sizniki! Ilovada ko'ring.",
        "🎁 Tabriklaymiz — «{reward_title}» sizga berildi. «Sovg'alarim» bo'limiga qarang.",
        "✨ Sovg'a keldi: «{reward_title}». Mutolaangiz yanada maroqli bo'lsin!",
    ),
    "notify.CERTIFICATE": (
        "🎓 <b>Sertifikat sizniki!</b>\n\n🏅 {title}\n\nMehnatingiz munosib baholandi.\n{details}",
        "🎓 <b>Tabriklaymiz — yangi sertifikat!</b>\n\n🏅 {title}\n\n{details}",
        "📜 <b>Sizga sertifikat berildi</b>\n\n🏅 {title}\n\nKitobxonlik yo'lingizda yana bir muhr.\n{details}",
        "🎓 <b>Yutuqingiz muhrlandi</b>\n\n🏅 {title}\n\n{details}",
    ),
    "notify.FEEDBACK_REQUEST": (
        "💬 «{event_title}» qanday o'tdi? Bir bosishda baho bering — bu bizga yordam beradi.",
        "⭐ «{event_title}» sizga yoqdimi? Bahoyingiz keyingi tadbirlarni yaxshilaydi.",
        "💬 Taassurotlaringiz qanday? «{event_title}»ga baho bering 🙏",
        "🙂 «{event_title}» tugadi. Fikringizni bildirish uchun bir daqiqa ajrata olasizmi?",
    ),
    "notify.DIGEST": (
        "📊 <b>Haftangiz qanday o'tdi</b>\n\n{message}\n\nYangi hafta — yangi sahifa! 📚",
        "🗓 <b>Hafta xulosasi</b>\n\n{message}\n\nDavom etamiz! 💪",
        "📈 <b>Haftalik natijalaringiz</b>\n\n{message}\n\nKeyingi hafta yanada yaxshi bo'lsin ✨",
        "📚 <b>Bir haftada nimalar qildik?</b>\n\n{message}\n\nOmad tilaymiz!",
    ),
}
