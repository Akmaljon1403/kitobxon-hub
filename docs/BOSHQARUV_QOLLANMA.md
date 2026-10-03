# Kitobxon Hub — boshqaruv qo'llanmasi (klub rahbari uchun)

Bu qo'llanma dasturchi bo'lmagan klub rahbari uchun: har bir bo'lim nima qiladi va uni qanday
sozlash kerak. Hammasi telefondan, Telegram ichida qilinadi.

---

## 1. Admin panelga kirish

1. Botda **🛠 Boshqaruv** tugmasini bosing (u faqat adminlarga ko'rinadi).
2. **🛠 Admin panelni ochish** — panel Telegram ichida o'zi ochiladi, parol kerak emas.

> Kompyuterdan kirish kerak bo'lsa: botda `/admin` → bir martalik havola (5 daqiqa amal qiladi).

## 2. Adminlar va huquqlar

**Admin panel → 🛡 Adminlar**. A'zoni toping va tayyor to'plamlardan birini tanlang:

| To'plam | Kimga |
|---|---|
| ⭐ To'liq admin | o'rinbosaringizga |
| 📅 Tadbir va davomat | tadbir o'tkazuvchilarga |
| 📚 Kitob va testlar | kitob/test tayyorlovchilarga |
| 🏆 Ballar va sovg'alar | ball va sovg'a bilan ishlovchilarga |
| 📨 Xabar va murojaatlar | a'zolar savollariga javob beruvchilarga |
| 📄 Hisobot va tahlil | rasmiy hisobot tayyorlovchilarga |

«Imkoniyatlar» va «Premium» sahifalari faqat **bosh administrator** (siz) uchun.

## 3. Tadbir va davomat

1. **📅 Tadbirlar** → yangi tadbir: nomi, vaqti, joyi, **davomat oynasi** (masalan, boshlanishidan
   10 daqiqa oldin — 30 daqiqa keyin).
2. Belgilangan vaqtda davomat **o'zi ochiladi**, a'zolarga xabar boradi.
3. Tadbirda **Davomat** sahifasini proyektor/ekranga chiqaring: QR kod va 6 belgili kod **har 10
   soniyada** yangilanadi (suratga olib boshqaga yuborish foyda bermaydi).
4. A'zo botda **✅ Davomat** → QR skaner yoki kodni yozadi — 5 soniyalik ish.
5. Tadbirdan 30 daqiqa keyin bot qatnashganlardan **⭐ baho** so'raydi. Baholar va fikrlar shu
   tadbirning davomat sahifasi pastida ko'rinadi.

## 4. Murojaatlar

A'zolar botda **💬 Yordam → ✉️ Adminga yozish** orqali yozadi. Xabar `SUPPORT` huquqi bor
adminlarga keladi. Javobni botning o'zida («Javob yozish») yoki panelda **📨 Murojaatlar**dan
berasiz — a'zo sizning ismingizni ko'rmaydi, javob «Klub rahbariyati» nomidan boradi.

## 5. Kitobxon pasporti

Har bir a'zoda rasmli ID-karta bor: rasmi, ismi, fakulteti, kursi, guruhi va a'zo raqami (KH-000042).
Ball va reyting har kuni o'zgargani uchun kartaga yozilmaydi — **QR kodni skanerlagan kishi** pasport
haqiqiyligini va a'zoning **jonli natijalarini** (ball, reytingdagi o'rni, kitoblar, tadbirlar,
yutuqlar, sertifikatlar) ko'radi.

- A'zo rasmini o'zi almashtiradi: botda **🪪 Pasportim → 📷 Rasmni almashtirish** yoki ilovada
  «Profil → 📷 Yangi rasm». Rasm o'zi to'g'rilanadi va kesiladi.
- Noma'qul rasm bo'lsa: admin panel → **A'zolar** → a'zo → **🖼 Pasport rasmini o'chirish**.
- Premium a'zolar 4 ta dizayndan birini tanlaydi: klassik yashil, **oltin**, **tungi ko'k**, **yoqut**.

## 6. Sertifikatlar

**Avtomatik beriladi:**

- har bir test yopilganda **1-, 2-, 3-o'rin** egalariga (tadbir testida — faqat davomatdan
  o'tganlarga);
- har oy boshida (1-sana, soat 10:00 dan) o'tgan oy reytingidagi **eng faol uchlikka**.

Sertifikat PDF ko'rinishida bot orqali darhol yuboriladi. **🎓 Sertifikatlar** sahifasida qo'lda ham
berasiz (masalan, «Faol kitobxon»), yuklab olasiz yoki bekor qilasiz.

**Sozlash:** **⚙️ Sozlamalar → 🎓 Sertifikatlar** — imzo egasining lavozimi va ismi (masalan,
«Klub rahbari — A. Bahodirov»), avtomatik berishni o'chirish.

## 7. Rasmiy hisobotlar (PDF)

**📄 Hisobotlar → + Yangi hisobot** va turini tanlang:

| Tur | Nima uchun | Raqamlar |
|---|---|---|
| 📅 Tadbir hisoboti | bitta tadbir | davomat, fakultetlar, testlar, baholar — bazadan |
| 🗓 Davr hisoboti | oylik/choraklik hisobot | tadbirlar, yangi a'zolar, kitoblar, eng faollar — bazadan |
| 📝 Umumiy hisobot | istalgan mavzu (aksiya, uchrashuv...) | faqat sizning matningiz |

Keyin:

1. Maydonlarga o'z so'zlaringiz bilan yozing (maqsad, nima qilindi, xulosa).
2. **📷 Rasm tanlash** — 8 tagacha rasm (izoh bilan).
3. **Shablon bo'yicha** (yoki AI ulangan bo'lsa **AI bilan**) — rasmiy matn tayyorlanadi.
4. Tekshiring, kerak bo'lsa tuzating → **Tasdiqlash** → rasmiy PDF tayyor.

Tizim bazada yo'q raqamni matnda qoldirmaydi — hisobotdagi har bir raqam tekshiriladi.

## 8. Imkoniyatlar (bot funksiyalarini yoqish/o'chirish)

**🧩 Imkoniyatlar** sahifasida har bir bo'lim uchun uchta holat bor:

- **O'chiq** — a'zolar uni ko'rmaydi;
- **Hammaga** — barcha a'zolar uchun;
- **💎 Premium** — faqat Premium a'zolar uchun (boshqalar 💎 belgisini va taklifni ko'radi).

«Yoqilganda a'zolarga e'lon yuborilsin» belgilangan bo'lsa, bo'lim yoqilganda hamma a'zoga
**«🎉 Tabriklaymiz, bot yangilandi! Endi sizda yangi imkoniyat bor: …»** xabari boradi.

## 9. Premium obuna va hissalar (daromad)

To'lov **Telegram Stars (⭐)** orqali: karta ma'lumotlari, shartnoma yoki to'lov tizimi kerak emas —
Telegram raqamli xizmatlar uchun aynan shu usulni talab qiladi.

**Yoqish:**

1. **🧩 Imkoniyatlar → 💎 Premium obuna → Hammaga** (e'lon bilan).
2. Xohlasangiz **❤️ Klubni qo'llab-quvvatlash → Hammaga** (ixtiyoriy hissa: 50/100/250/500 ⭐).
3. Qaysi bo'limlar Premium bo'lishini o'sha sahifada tanlang. Boshlang'ich holatda Premium
   a'zolarga **📊 Haftalik xulosa** va **oltin pasport** beriladi; asosiy imkoniyatlar (kitob,
   tadbir, davomat, test, reyting) bepul qoladi — klub hamma uchun ochiq bo'lishi muhim.

**Narxlar:** **💎 Premium** sahifasida o'zgartiriladi. Boshlang'ich: 1 oy — 100 ⭐, 3 oy — 250 ⭐,
1 yil — 900 ⭐. Tarifni «Sotuvdan olish» mumkin.

**Premium sovg'a qilish:** o'sha sahifada a'zoni tanlab, kunlar sonini yozasiz (masalan, oy
g'olibiga 30 kun yoki naqd to'laganga).

**Qaytarish (refund):** «To'lovlar» jadvalida **Qaytarish** — Stars a'zoga qaytadi, Premium muddati
bekor bo'ladi. A'zolar to'lov bo'yicha savolni botda `/paysupport` orqali yozadi; shartlar —
`/terms`.

**Stars'ni pulga aylantirish:** bot yig'gan Stars botning balansida turadi. **@BotFather → botingiz
→ Balance** (yoki Telegram'dagi bot sozlamalari) orqali ularni **Fragment** platformasida TON
kriptovalyutasiga, keyin so'mga almashtirish mumkin. Telegram qoidalariga ko'ra Stars odatda
to'lovdan bir necha hafta o'tib yechiladi va eng kam yechish miqdori bor — aniq shartlar o'sha
«Balance» sahifasida ko'rsatiladi.

> Tavsiya: tushumlar va xarajatlarni (kitoblar, sovg'alar, tadbirlar) ochiq e'lon qilib boring —
> bu a'zolar ishonchini oshiradi. Institut ma'muriyati bilan ham kelishib oling.

## 10. Kundalik ish — qisqa ro'yxat

- Har tadbirdan oldin: tadbir yaratilganini va davomat oynasini tekshiring.
- Tadbirda: Davomat sahifasini ekranga chiqaring.
- Haftada bir: **📨 Murojaatlar**, **⭐ baholar**, **📈 Tahlillar**.
- Oy boshida: **🗓 Davr hisoboti** → PDF → institut rahbariyatiga.
