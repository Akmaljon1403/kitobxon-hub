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

### Karta orqali to'lov (so'mda)

Telegram Stars'siz ham to'lash mumkin: a'zo klub kartasiga pul o'tkazadi va chek rasmini yuboradi,
siz tasdiqlaysiz — Premium **o'zi yoqiladi**.

> Muhim: bot a'zolarga Telegram Stars «bera olmaydi» — Telegram bunga ruxsat bermaydi. Shuning uchun
> karta to'lovi tasdiqlanganda a'zo tanlagan **Premium muddati** (yoki hissa) avtomatik yoziladi.
> Payme/Click orqali to'liq avtomatik to'lov uchun klub nomidan merchant (shartnoma) kerak bo'ladi —
> kerak bo'lsa, keyin qo'shamiz.

**Yoqish (bir marta):**

1. **⚙️ Sozlamalar → 💳 Karta orqali to'lov** — karta raqami va karta egasining ismi.
2. **💎 Premium → Tariflar** — har bir tarifga **«Karta narxi (so'm)»** yozing (masalan, 1 oy — 25 000).
   Narx yozilmagan tarif karta orqali sotilmaydi.
3. **🧩 Imkoniyatlar → 💳 Karta orqali to'lov → Hammaga**.

**Har kuni:** a'zo chek yuborsa, botga darhol xabar keladi: **«🧾 Chekni ko'rish»** → chek rasmi →
**✅ Tasdiqlash** yoki **❌ Rad etish** (sababini yozasiz, a'zoga boradi). Xuddi shu ishni admin
panelda **💎 Premium → 💳 Karta orqali to'lovlar** bo'limida ham qilasiz. Pul kartaga **haqiqatan tushganini**
bank ilovangizda tekshirib, keyin tasdiqlang. Bu ishni faqat **bosh administrator** qiladi.

## 10. Sovg'a o'yinlari (boshqa ilovalar uchun promokodlar)

Promokodlarni adolatli qoida bo'yicha tarqatish: **Admin panel → 🎲 Sovg'a o'yinlari**.

**Tayyorgarlik:** **🎁 Sovg'alar** → yangi sovg'a (masalan, «Kitob ilovasi — 1 oylik obuna») →
**Berish va kodlar** → hamkor bergan kodlarni kiriting (har qatorda bitta). Kodlar shifrlangan holda
saqlanadi, faqat g'olib o'z kodini ko'radi.

**O'yin turlari:**

| Qoida | Qachon ishlatiladi |
|---|---|
| 🎲 Tasodifiy g'oliblar | tasodifiy a'zolarga. Adminlar qatnashmaydi; xohlasangiz faqat tadbirga kelganlar yoki faqat Premium a'zolar orasida. Premium a'zolarga ikki baravar imkoniyat |
| 📝 Testlarda eng ko'p ball | oyda bir marta — oy davomida testlardan eng ko'p ball to'plaganga |
| 📅 Har bir tadbir testining o'rinlari | oyda 4 ta tadbir bo'lsa, har birining 1-, 2-, 3-o'rinlariga **alohida** (4 × 3 = 12 g'olib). Faqat tadbirga kelganlar (davomat) hisoblanadi |
| 🏆 Reyting peshqadamlari | davr bo'yicha reytingdagi birinchi o'rinlarga |

**Qanday ishlatiladi:**

1. **+ Yangi o'yin** → nomi, sovg'a, qoida, g'oliblar soni, davr («Shu oy» tugmasi).
2. **Belgilangan vaqtda avtomatik** — masalan, oyning oxirgi kuni soat 20:00. **🔁 Har oy takrorlansin**
   belgilansa, keyingi oyning o'yini o'zi rejalashtiriladi — har oy qayta yaratish shart emas.
3. Yoki **Ko'rish va o'tkazish** → kim g'olib bo'lishini oldindan ko'rasiz → **🎲 Hozir o'tkazish**.

G'oliblarga kod va tabrik xabari darhol boradi, kod ilovadagi **🎁 Sovg'alarim** bo'limida ochiladi.
«E'lon qilinsin» belgilangan bo'lsa, barcha a'zolar va kanal g'oliblar ro'yxatini ko'radi. A'zolar
ilovada yaqindagi o'yinlarni va so'nggi g'oliblarni ko'rib turadi — bu qatnashishga undaydi.
Kodlar yetmasa, o'yin o'tkazilmaydi va sizga xabar keladi — kod qo'shsangiz, o'zi o'tkaziladi.

## 11. Telegram kanal (@FJSTIMutolaaxona)

Bot kanalga o'zi qiziqarli postlar joylaydi va o'quvchilarni botga taklif qiladi.

**Ulash (bir marta):**

1. Telegram'da kanal → **Administratorlar → Administrator qo'shish** → botni toping → **«Xabar
   joylash»** huquqini yoqing.
2. **⚙️ Sozlamalar → 📣 Telegram kanal** → «Bot klub kanaliga post joylaydi» ni yoqing. Kanal manzili
   allaqachon `@FJSTIMutolaaxona` deb yozilgan.
3. **📣 Telegram kanal** sahifasida **🧪 Sinov posti** ni bosing — bir necha soniyada kanalda chiqadi.
   Chiqmasa, sahifada xato sababi ko'rinadi (ko'pincha — bot admin qilinmagan).

**Bot o'zi joylaydigan postlar:**

- yangi tadbir: «Shanba, 15-noyabr, soat 15:00 … **«O'tkan kunlar» asarini o'qib kelamiz!**» (tadbirga
  kitob biriktirilgan bo'lsa, muqovasi bilan);
- tadbirdan bir kun va 3 soat oldin eslatma: «Ertaga soat 15:00 da …»;
- yangi kitob, muddatning yarmida «Yarmiga yetdingizmi?» va oxirida **«Asarni tugatay deb
  qoldingizmi, kitobxonlar?»**;
- kun iqtibosi, test g'oliblari, sovg'a o'yini g'oliblari, oyning eng faol kitobxonlari;
- har dushanba botga qo'shilishga taklif.

Har bir post ostida **«📲 Botga qo'shilish»** tugmasi bor. Kechasi (21:30 – 08:00) post joylanmaydi —
ertalab soat 9:00 da chiqadi. Qaysi postlar chiqishini sozlamalarda alohida o'chirib qo'yasiz.

**O'zingiz yozish:** **📣 Telegram kanal → Kanalga post yozish** — matn, rasm, stiker, istalgan vaqtga
rejalashtirish.

**Stikerlar:** botga **/stiker** deb yozing va yoqqan stikerlaringizni yuboring (animatsion stikerlar
ham bo'ladi). Avtomatik postlardan keyin ulardan biri qo'shiladi. Matn ichidagi Telegram Premium
emojilari esa faqat Fragment'dan sotib olingan bot nomiga ega botlarda ishlaydi — shuning uchun
stikerlardan foydalanamiz.

## 12. Kundalik ish — qisqa ro'yxat

- Har tadbirdan oldin: tadbir yaratilganini, kitob biriktirilganini va davomat oynasini tekshiring.
- Tadbirda: Davomat sahifasini ekranga chiqaring.
- Kelgan cheklarni (karta to'lovlari) bank ilovasi bilan solishtirib tasdiqlang.
- Haftada bir: **📨 Murojaatlar**, **⭐ baholar**, **📈 Tahlillar**, **📣 Telegram kanal** (xato yo'qmi).
- Oy boshida: **🗓 Davr hisoboti** → PDF → institut rahbariyatiga; **🎲 Sovg'a o'yinlari** — kodlar
  yetarlimi.
