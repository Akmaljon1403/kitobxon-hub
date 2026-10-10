"""Frequently asked questions: one list for the bot («❓ Savol-javoblar») and the Mini App («Yordam»)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    code: str
    title: str
    items: tuple[tuple[str, str], ...]  # (question, answer), plain text


TOPICS: tuple[Topic, ...] = (
    Topic(
        "start",
        "🌱 Boshlash",
        (
            (
                "Kitobxon Hub nima?",
                "Kitobxonlar klubimizning boti va ilovasi: kitoblar, davra suhbatlari, bilim testlari, ballar, "
                "reyting, sertifikatlar va sovg'alar bir joyda.",
            ),
            (
                "Kanalga obuna nega shart?",
                "Yangi kitoblar, tadbirlar, test natijalari va sovg'alar haqidagi xabarlar avval kanalda chiqadi. "
                "Obuna bo'lsangiz, hech narsani o'tkazib yubormaysiz.",
            ),
            (
                "Ilova qayerda?",
                "Botdagi «📱 Ilova» tugmasi yoki pastdagi menyu tugmasi orqali — Telegram ichida ochiladi.",
            ),
        ),
    ),
    Topic(
        "points",
        "🏆 Ballar va reyting",
        (
            (
                "Ball nima uchun beriladi?",
                "Tadbirga kelganingiz (davomat), test yechganingiz va testda o'rin olganingiz, kitobni o'qib "
                "tugatganingiz, yutuqlar va do'stingizni taklif qilganingiz uchun.",
            ),
            (
                "Reyting qanday tuziladi?",
                "Haftalik, oylik va umumiy reyting bor. Ballar teng bo'lsa: avval davomat bali, keyin test bali, "
                "keyin ballni avvalroq to'plagan yuqorida turadi.",
            ),
            (
                "Ballarim qayerda ko'rinadi?",
                "«📊 Natijalarim» bo'limida — har bir ball qayerdan kelgani bilan.",
            ),
        ),
    ),
    Topic(
        "events",
        "📅 Tadbirlar va davomat",
        (
            (
                "«✅ Qatnashaman» tugmasi nima beradi?",
                "Joylarni shunga qarab tayyorlaymiz, tadbirdan oldin sizga eslatma keladi va davomat ochilganda "
                "xabar beramiz. Smenali tadbirda o'z smenangizni tanlaysiz.",
            ),
            (
                "Davomat qanday qilinadi?",
                "Tadbir vaqti kelganda davomat o'zi ochiladi: «✅ Davomat»ni bosib ekrandagi kodni yozing yoki QR "
                "kodni telefon kamerasi bilan skanerlang. Tadbir davomida «qatnashyapsiz», tugagach «qatnashdingiz» "
                "deb ko'rinadi.",
            ),
            (
                "Telefonim o'chib qoldi yoki kod ishlamadi — nima qilay?",
                "«✉️ Adminga yozing». Admin sizni qo'lda qo'shadi, bosh administrator tasdiqlagach ball tushadi.",
            ),
            (
                "Bir kunda 2 smena bo'lsa-chi?",
                "O'z smenangizda davomat qilasiz. Tadbir testi esa har kimga bir marta — ikkinchi smenada qayta "
                "yechib bo'lmaydi.",
            ),
        ),
    ),
    Topic(
        "tests",
        "📝 Testlar",
        (
            (
                "Testni necha marta yechsa bo'ladi?",
                "Odatda bir marta. Vaqt chegarasi bor — boshlagach, taymer to'xtamaydi.",
            ),
            (
                "Tadbir testida o'rin olish uchun nima kerak?",
                "Tadbirda davomat qilgan bo'lish. Davomatsiz natijalar ro'yxatda «davomatsiz» belgisi bilan "
                "ko'rinadi, lekin sovrinli o'rin, sertifikat va sovg'a faqat qatnashganlarga.",
            ),
            (
                "To'g'ri javoblar qachon ko'rinadi?",
                "Test yopilgandan keyin — ilovada test sahifasida, izohlari bilan birga.",
            ),
        ),
    ),
    Topic(
        "books",
        "📚 Kitoblar",
        (
            (
                "«O'qib tugatdim» ball beradimi?",
                "Ha, muddat ichida. Kitob bo'yicha tadbirga kelsangiz yoki uning testini yechsangiz, o'qiganingiz "
                "o'zi tasdiqlanadi va ball tushadi.",
            ),
            (
                "Muddat o'tib ketdi — endi belgilasam bo'ladimi?",
                "Bo'ladi: kitob portfoliongizga qo'shiladi, faqat ball berilmaydi.",
            ),
        ),
    ),
    Topic(
        "documents",
        "🎓 Sertifikat va hujjatlar",
        (
            (
                "Sertifikat qanday olinadi?",
                "Testda 1–3-o'rinni olganlar (tadbir testida — qatnashganlar) va oy yakunida reyting yetakchilari "
                "avtomatik oladi. Sertifikat ilovada «🎓 Sertifikatlarim»da ko'rinadi.",
            ),
            (
                "Dizaynini almashtirsam, yangi sertifikat bo'ladimi?",
                "Yo'q. Sertifikat bitta — tekshirish kodi o'zgarmaydi, faqat ko'rinishi boshqa. Uni istalgan "
                "kishi QR kod orqali tekshira oladi.",
            ),
            (
                "Yuklab olgan fayllarim qayerga keladi?",
                "Ilova telefoningizga hech narsa saqlamaydi: pasport, sertifikat, portfolio va boshqa hujjatlar "
                "shu bot chatiga yuboriladi.",
            ),
        ),
    ),
    Topic(
        "premium",
        "💎 Premium va to'lov",
        (
            (
                "Premium nima beradi?",
                "Qo'shimcha imkoniyatlar: oltin pasport va dizaynlar, to'liq reyting, shaxsiy statistika, "
                "sertifikatni cheklovsiz yuklab olish va boshqalar. Asosiy imkoniyatlar hamma uchun bepul.",
            ),
            (
                "Qanday to'layman?",
                "Eng osoni — bank kartasi (Uzcard, Humo; Click yoki Payme orqali ham): summani klub kartasiga "
                "o'tkazasiz va chekni yuborasiz. Yoki Telegram Stars bilan bir zumda.",
            ),
            (
                "Chek yubordim — qachon yoqiladi?",
                "Chek administratorga tekshirish uchun yuboriladi, odatda bir kun ichida ko'rib chiqiladi. "
                "Natijasi botda xabar qilinadi, Premium o'zi yoqiladi.",
            ),
            (
                "Stars'ni karta orqali olsa bo'ladimi?",
                "Ha, «💳 Bank kartasi» bo'limida. Buning uchun Telegram profilingizda username bo'lishi kerak — "
                "Stars aynan shu username'ga yuboriladi.",
            ),
        ),
    ),
    Topic(
        "account",
        "👤 A'zolik",
        (
            (
                "Ma'lumotlarimni qanday o'zgartiraman?",
                "Ilovada «👤 Profil» → «✏️ O'zgartirish» (fakultet, kurs, guruh). Ism yoki telefon uchun adminga "
                "yozing.",
            ),
            (
                "A'zolikni bekor qilsam nima bo'ladi?",
                "«⚙️ Sozlamalar»da bekor qilish mumkin. 14 kun ichida o'zingiz, 30 kungacha admin orqali "
                "ballaringiz bilan qayta tiklanasiz.",
            ),
            (
                "Adminga qanday yozaman?",
                "Botda «❓ Yordam» → «✉️ Adminga yozish» yoki ilovada «Yordam» sahifasida. Javob shu yerga keladi.",
            ),
        ),
    ),
)

BY_CODE = {topic.code: topic for topic in TOPICS}


def as_dicts() -> list[dict[str, object]]:
    return [
        {"code": topic.code, "title": topic.title, "items": [{"q": q, "a": a} for q, a in topic.items]}
        for topic in TOPICS
    ]
