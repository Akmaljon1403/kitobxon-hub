# Kitobxon Hub — to'liq qo'llanma

Farg'ona jamoat salomatligi tibbiyot instituti kitobxonlar klubi uchun. Bu qo'llanma dasturchi
bo'lmagan klub rahbari uchun yozilgan: botning va ilovaning **har bir funksiyasi**, **har bir qadami**
qanday ishlashi, nimani qayerda sozlash, muammo bo'lsa nima qilish — hammasi shu yerda.

**Qanday o'qish kerak.** Avval «A. Tizim nimalardan iborat» bo'limini o'qing. Keyin:

- a'zolar nimani ko'rishini bilish uchun — **B, C, D bo'limlari** (bot, ilova va «Mening mutolaam»);
- boshqaruv uchun — **1–35-bo'limlar** (admin panel, to'lovlar, kanal, avtomatik ishlar, savol-javob);
- sozlama, huquq yoki buyruqni tez topish uchun — oxiridagi **ma'lumotnoma jadvallari** (ular
  dastur kodidan avtomatik olingan, shuning uchun to'liq va aniq);
- tushunmagan narsangizni menga (Claude'ga) yozib so'rang.

---

## A. Tizim nimalardan iborat

| Qism | Kim ishlatadi | Nima qiladi |
|---|---|---|
| **🤖 Telegram bot** | hamma a'zolar | ro'yxatdan o'tish, menyu, davomat, xabarlar, to'lov, murojaat |
| **📱 Ilova (Mini App)** | hamma a'zolar | botning ichida ochiladigan sahifalar: kitoblar, testlar, reyting, javon, missiyalar va boshqalar |
| **🛠 Admin panel** | adminlar | boshqaruv: a'zolar, tadbirlar, testlar, ballar, hisobotlar, sozlamalar |
| **📣 Klub kanali** | hamma | bot o'zi post joylaydi (tadbir, kitob, iqtibos, g'oliblar) |
| **💳 To'lovlar kanali** | bosh admin va to'lov adminlari | pulga oid hamma narsa: cheklar, qarorlar, Stars buyurtmalari, to'lov savollari |

**Rollar:**

| Rol | Kim | Nima qila oladi |
|---|---|---|
| A'zo | ro'yxatdan o'tgan talaba | botdan va ilovadan foydalanadi |
| Admin | siz huquq bergan odam | faqat berilgan huquqlar doirasida (masalan, faqat tadbir va davomat) |
| **⭐ Stars yuboruvchi admin** | `STARS_SEND` huquqi berilgan admin | bosh admin tasdiqlagan Stars buyurtmalarini Telegram'da a'zoga sovg'a qiladi |
| **Bosh admin** | siz | hamma narsa: to'lovlarni tasdiqlash, imkoniyatlarni yoqish, adminlarni tayinlash |

Bosh adminlar umrbod 💎 Premium'ga ega va hech qachon reyting, tanlov yoki sovg'a o'yinida
qatnashmaydi (adolat uchun).

---

## B. A'zo nigohida: bot (qadam-baqadam)

### B.1. Ro'yxatdan o'tish

1. A'zo botni ochib **Start** ni bosadi (yoki do'sti yuborgan taklif havolasi orqali kiradi).
2. Majburiy obuna yoqilgan bo'lsa — avval klub kanaliga obuna bo'lish so'raladi: **📢 kanal** tugmasi
   va **✅ Obuna bo'ldim**. Obuna bo'lgach, to'xtagan joyidan davom etadi.
3. Bot savollar beradi:
   1. **Ismingiz?** (masalan: Akmaljon)
   2. **Familiyangiz?**
   3. **Telefon raqami** — pastdagi **📱 Raqamni yuborish** tugmasi bilan (qo'lda yozilmaydi; faqat
      o'zining raqami qabul qilinadi; raqamni faqat klub rahbariyati ko'radi).
   4. **Fakultet** (ro'yxatdan tanlanadi; fakultetlar kiritilmagan bo'lsa bu qadam o'tkazib yuboriladi).
   5. **Kurs** (1-, 2-, … kurs tugmalari).
   6. **Guruh** (masalan: 301 yoki 301-A).
4. Ma'lumotlarni tekshirish: **✅ Tasdiqlash** yoki **🔄 Qaytadan to'ldirish**.
5. Tayyor: qisqa tanishuv (davomat, testlar, kitoblar, ilova), bir martalik **bepul Premium sinov**
   (odatda 7 kun) va bosh menyu chiqadi. Agar a'zolarni tasdiqlash yoqilgan bo'lsa, admin tasdiqlaguncha
   kutadi.

To'xtatish: `/cancel` yoki `/stop` — istalgan jarayon to'xtaydi, menyuga qaytadi.

### B.2. Bosh menyu — har bir tugma

| Tugma | Nima qiladi |
|---|---|
| **📚 Kitoblar** | joriy klub kitobi, muddati va qancha kun qolgani; «📱 Batafsil — ilovada» |
| **📅 Tadbirlar** | yaqin tadbir: sana, joy, kitob; ilovada ro'yxatdan o'tish |
| **✅ Davomat** | tadbirda davomat: QR kodni skanerlash yoki 6 belgili kodni yozish (B.3) |
| **📝 Testlar** | ochiq testlar va qancha vaqt qolgani; test ilovada ishlanadi |
| **📊 Natijalarim** | ballar, o'rinlar, so'nggi natijalar |
| **🏆 Reyting** | haftalik reyting va a'zoning o'rni (to'liq reyting — Premium, sozlanadi) |
| **🪪 Pasportim** | rasmli a'zolik kartasi (B.4) |
| **🏅 Yutuqlar** | nishonlar; sertifikatlar, portfolio va «🎁 Sizning foydangiz» tugmalari |
| **🎁 Sizning foydangiz** | taklif havolasi, taklif qilgan do'stlar va ularning ballari (B.5) |
| **⚙️ Sozlamalar** | bildirishnomalarni yoqish/o'chirish, ma'lumotlarni o'zgartirish, a'zolikni bekor qilish |
| **💬 Yordam** | savol-javoblar va «✉️ Adminga yozish» |
| **💎 Premium** | Premium do'koni ochiq bo'lsa ko'rinadi |
| **🛠 Boshqaruv** | faqat adminlarga ko'rinadi: qisqa holat va admin panel |

Menyu tugmasi bosilganda bot qisqa xulosa yozadi va «📱 Batafsil — ilovada» tugmasini qo'shadi.
Bosh admin biror bo'limni o'chirsa (masalan, Reyting), tugma menyudan yo'qoladi.

### B.3. Davomat

1. Tadbirda davomat ochilganda a'zolarga xabar keladi.
2. A'zo **✅ Davomat** (yoki `/davomat`) → **📷 QR kodni skanerlash** (ekrandagi QR) yoki ekrandagi
   **6 belgili kodni** yozadi.
3. «✅ Davomatingiz qayd etildi» va ball. Kod har 10 soniyada yangilanadi — rasmga olib boshqaga
   yuborish foyda bermaydi. Bir tadbirga ikki marta davomat qilib bo'lmaydi.

### B.4. Kitobxon pasporti

**🪪 Pasportim** (yoki `/pasport`) — ID-karta rasmi: rasm, ism, fakultet, kurs, guruh, a'zo raqami
(KH-000042) va QR kod. Tugmalar: **📷 Rasmni almashtirish**, **↩️ Telegram rasmiga qaytish**,
**🎨 Dizayn (Premium)**, **📥 Fayl sifatida (asl sifat)**, **🎓 Sertifikatlarim**. QR kodni
skanerlagan odam pasport haqiqiyligini va a'zoning jonli natijalarini ko'radi.

### B.5. «🎁 Sizning foydangiz» (do'stlarni taklif qilish)

Bu bo'lim **doim ochiq** — uni o'chirib bo'lmaydi. Uch joydan ochiladi: bot menyusidagi
**🎁 Sizning foydangiz** tugmasi, `/referal` (yoki eski `/taklif`) buyrug'i va ilovadagi bosh sahifa
yoki profildagi «🎁 Sizning foydangiz» kartasi.

A'zo ko'radi:

1. **Shaxsiy taklif havolasi** (`https://t.me/<bot>?start=ref_1024`) va **📤 Do'stlarga yuborish**.
2. Mukofot sharti: do'sti havola orqali ro'yxatdan o'tib, **birinchi tadbirga kelsa** — +20 ball va
   7 kunlik Premium (sozlanadi; oyiga 5 tagacha).
3. **📊 Qisqacha**: nechta do'st taklif qilgani, nechtasi tadbirga kelgani, ular to'plagan **jami ball**,
   o'qigan kitoblari, a'zoning o'zi olgan ball va Premium kunlar.
4. **Do'stlari ro'yxati**: «1. Bekzod K. — ⭐ 120 ball ✅» (✅ — tadbirga keldi, ⏳ — hali kelmadi).
   Sozlamaga ko'ra faqat ismlar yoki faqat sonlar ko'rsatilishi mumkin.
5. Eng faol taklif qiluvchilar orasidagi o'rni va davom etayotgan taklif tanlovi.

> Avval havola ba'zan «yopiq» chiqardi: u faqat `BOT_USERNAME` sozlamasiga bog'liq edi. Endi bot o'z
> nomini Telegram'dan o'zi so'rab oladi — havola har doim ishlaydi.

### B.6. «📚 Mening mutolaam» botda: /oqidim, /javonim, /kartam

- **`/oqidim 25`** — «O'qiyapman» javonidagi kitobga bugun 25 bet qo'shiladi (mutolaa kundaligi).
  Izoh bilan: `/oqidim 25 Juda qiziq bob edi`. Javob: kitob nomi, «25/40 bet (62%)», bugungi jami va
  🔥 seriya (necha kun ketma-ket o'qilgani). Kitob tugasa, «O'qib bo'ldim» deb belgilash va 3 savolga
  javob yozish taklif qilinadi. Bir kunda yozish mumkin bo'lgan eng ko'p bet — sozlamada (odatda 500).
- **`/javonim`** — o'qiyotgan kitoblar va progress, javon bo'yicha sonlar, haftalik betlar, seriya,
  bu yil o'qilgan kitoblar.
- **`/kartam`** — **«🪪 Kitobxonlik kartam»** rasmi: o'qilgan kitoblar, betlar, eng uzun seriya, jami
  ball, reytingdagi o'rin, yutuqlar, hozir o'qiyotgan kitob va sevimli iqtibos. Rasmni bosib turib
  do'stlarga ulashish mumkin.

### B.7. Premium va to'lov

**💎 Premium** tugmasi yoki `/premium`. Avval Premium nima berishi ko'rsatiladi, keyin tarif tanlanadi,
keyin to'lov usuli:

- **💳 Bank kartasi orqali (Uzcard / Humo)** — summani klub kartasiga o'tkazib, chek rasmini yuboradi.
  Bosh admin tasdiqlagach Premium **o'zi yoqiladi**.
- **⭐ Telegram Stars orqali** — Telegram ichida bir zumda.
- **⭐ Stars'ingiz yo'qmi?** — Stars usuli ichida: Stars'ni karta orqali sotib olish (9-bo'lim,
  «⭐ Stars karta orqali»). A'zoning Telegram profilida **username** bo'lishi kerak.

To'lov bo'yicha savol: `/paysupport` → yozadi → savol to'lovlar kanaliga boradi, **faqat bosh admin**
javob beradi, javob a'zoga keladi va kanalga ham yoziladi.

### B.8. Yordam, sozlamalar, chiqish

- **💬 Yordam** → **❓ Savol-javoblar** (mavzular bo'yicha) va **✉️ Adminga yozish** (matn yoki rasm).
  Javob «Klub rahbariyati» nomidan keladi. Bloklangan yoki klubdan chiqqan a'zo ham yoza oladi.
- **⚙️ Sozlamalar** → bildirishnomalar (har birini ✅/❌): 📅 Tadbir eslatmalari, 📝 Test eslatmalari,
  📖 O'qish muddati, 💬 Kun iqtibosi, 🏆 Reyting yangiliklari, 🏅 Yutuqlar; **✏️ Ma'lumotlarimni
  o'zgartirish**; **🚪 A'zolikni bekor qilish**. To'lov, davomat va natija xabarlari doim keladi.

---

## C. A'zo nigohida: ilova (Mini App)

Ilova botning ichida ochiladi (menyu yonidagi «Ilova» tugmasi yoki «📱 Batafsil — ilovada»). Pastda 5 ta
asosiy tab: **🏠 Asosiy, 📚 Kitoblar, 📅 Tadbirlar, 🏆 Reyting, 👤 Profil**.

| Sahifa | Nima bor |
|---|---|
| **🏠 Asosiy** | salomlashuv va jami ball/o'rin; ochiq davomat va test kartalari; joriy kitob; yaqin tadbir; **🎁 Sizning foydangiz** kartasi; barcha bo'limlar tugmalari |
| **📚 Kitoblar** | klub kitoblari; kitob sahifasida «O'qishni boshladim / O'qib tugatdim», **📖 Javonimda ochish**, iqtiboslarni **💾 Saqlash** |
| **📖 Javonim** | shaxsiy javon: O'qiyapman / O'qimoqchiman / O'qib bo'ldim / Keyinroq; 🔥 seriya, haftalik betlar, 14 kunlik grafik; «Bugun necha bet?» — tezkor yozish; ➕ kitob qo'shish (klubdan yoki o'zingizniki) |
| **Kitob (javonda)** | progress, kundalikka yozish (bugun/kecha/2 kun oldin, betlar, daqiqa, izoh), holatni o'zgartirish, ⭐ baho, **💡 Kitobdan keyin 3 savol**, shu kitob iqtiboslari, kundalik yozuvlari |
| **💬 Iqtiboslarim** | saqlangan iqtiboslar, qidiruv, yangi iqtibos; har biri **🖼 Kartochka** (chiroyli rasm) va **📤 Ulashish** (bot chatiga yuboriladi) |
| **🎯 Missiyalar** | davom etayotgan, boshlash mumkin va bajarilgan missiyalar; progress va qolgan vaqt |
| **🪪 Kartam** | «Kitobxonlik kartam» rasmi va **📤 Botga yuborish** |
| **🌍 A'zolar fikrlari** | boshqa kitobxonlarning iqtiboslari, fikrlari, taassurotlari va e'tiroflari (yangi / ❤️ eng yoqqan / meniki), ❤️ bosish, kartochka; **✍️ Yozish** — tur, matn, kitob yoki tadbir, 6 xil kartochka dizayni |
| **🏛 Fakultetlar ligasi** | fakultetlar bellashuvi: o'rtacha ball, faol a'zolar ulushi, betlar, kitoblar, tadbirlar; o'z fakulteti ajratib ko'rsatiladi |
| **📅 Tadbirlar** | tadbirlar, ro'yxatdan o'tish (smena tanlash), davomat |
| **📝 Testlar** | testni ishlash (taymer bilan), natija |
| **📊 Natijalarim / 📈 Statistikam** | ballar tarixi; Premium: oylar bo'yicha grafiklar |
| **🏆 Reyting** | hafta, oy, mavsum, fakultetim, guruhim, fakultetlar (bir qismi Premium) va **🏛 Fakultetlar ligasi** havolasi |
| **🏅 Yutuqlar, 🎓 Sertifikatlar, 🎁 Sovg'alar** | nishonlar, sertifikatlar (PDF — Premium), yutilgan promokodlar |
| **🎁 Sizning foydangiz** | havola, «Qisqacha», taklif qilgan do'stlar va ularning ballari, tanlovlar, eng faollar jadvali |
| **💎 Premium** | tarif → to'lov usuli → to'lash; «⭐ Stars'ingiz yo'qmi?»; to'lovlarim holati |
| **👤 Profil** | pasport, ma'lumotlar, bildirishnomalar, sovg'alar, javon, karta, missiyalar, yordam |

---

## D. «📚 Mening mutolaam» — to'liq tushuntirish

Bu yangi to'plam a'zoning **o'z mutolaasini** yuritishga yordam beradi. Hammasi **🧩 Imkoniyatlar**
sahifasida alohida yoqiladi/o'chiriladi (odatda hammasi «Hammaga» yoqilgan).

### D.1. 📖 Shaxsiy javon

- Kitob qo'shish: klub kitobi (ro'yxatdan) yoki **o'z kitobi** (nomi, muallifi, betlar soni).
- To'rtta holat: **O'qimoqchiman**, **O'qiyapman**, **O'qib bo'ldim**, **Keyinroq**.
- Klub kitobini «O'qiyapman / O'qib bo'ldim» qilsangiz, klub ro'yxatida ham belgilanadi (ball va
  yutuqlar avvalgidek ishlaydi) va aksincha: kitob sahifasida «O'qishni boshladim» bosilsa, kitob javonga
  o'zi tushadi.

### D.2. ✍️ Mutolaa kundaligi va seriya

- Har kuni o'qilgan betlar yoziladi (ilovada yoki botda `/oqidim 25`). Faqat **oxirgi 7 kun** uchun
  yozish mumkin; bir kunda eng ko'pi `reading.daily_page_limit` (odatda 500) bet.
- **🔥 Seriya** — necha kun ketma-ket o'qilgani (bugun yoki kecha yozilgan bo'lsa davom etadi).
- Kitob «O'qimoqchiman»da turgan bo'lsa, birinchi yozuv bilan o'zi «O'qiyapman»ga o'tadi.

### D.3. 💡 Kitobdan keyin 3 savol

Kitob «O'qib bo'ldim» bo'lgach: 1) asosiy g'oya; 2) eng yoqqan joy; 3) hayotda nimani qo'llaydi.
Har javob kamida 10 belgi. Ball: `reading.reflection_points` (odatda 5), har kitobga **bir marta**,
oyiga `reading.reflection_monthly_limit` tagacha (odatda 4). Halollik uchun **o'z kitobi** uchun ball
faqat kundalikda o'qilgani ko'rinsa beriladi (klub kitobi uchun — har doim).

### D.4. 💬 Iqtiboslar sandig'i

Iqtibos qo'lda yoziladi (bet raqami va izoh bilan) yoki klub kitobidagi iqtibos **💾 Saqlash** bilan
olinadi. **🖼 Kartochka** — iqtibos to'q ko'k-oltin brend uslubidagi chiroyli rasmga aylanadi (Lora
yozuvi, klub belgisi, «Saqlagan: Madina K.», bot nomi). **📤 Ulashish** — kartochka bot chatiga keladi,
u yerdan do'stlarga yuboriladi.

Saqlashdan oldin a'zo tanlaydi: **🔒 Faqat o'zim uchun** (hech kim ko'rmaydi) yoki **🌍 Umumiy** (admin tasdiqlagach
«💬 A'zolar fikrlari» lentasida hamma ko'radi). Keyin ham o'zgartiradi: «🌍 Umumiy qilish» / «Shaxsiyga qaytarish».
Oldindan tanlangan variant va «Umumiy» umuman bo'ladimi — **⚙️ Sozlamalar → community** (`community.quote_box_default`,
`community.quote_box_common`). Admin panelda umumiylari **💬 A'zolar fikrlari**da, filtr «📦 Iqtiboslar sandig'idan».

### D.5. 🎯 Shaxsiy missiyalar

Kichik maqsadlar: a'zo **🎯 Boshlash** ni bosadi va shu daqiqadan missiya muddati boshlanadi. Natija
**qo'lda yozilmaydi** — kundalik, javon, tasdiqlangan davomat, topshirilgan testlar, saqlangan iqtiboslar
va «3 savol»dan o'zi hisoblanadi. Maqsadga yetganda ball va 🎉 tabrik keladi. Vaqt tugasa — «Qaytadan
boshlash» mumkin; bajarilgan missiya qayta olinmaydi. Bir vaqtda 5 tagacha missiya.

Tayyor missiyalar (birinchi ishga tushishda o'zi qo'shiladi, keyin o'zgartirasiz):

| Missiya | Shart | Ball |
|---|---|---|
| 📖 7 kunda 100 bet | 7 kun ichida kundalikka 100 bet | 15 |
| 🔥 5 kun ketma-ket o'qish | 7 kun ichida 5 kunlik seriya | 10 |
| 📚 Bir oyda 2 ta kitob | 30 kunda 2 kitobni tugatish | 25 |
| 💬 Iqtiboslar sandig'i: 5 ta iqtibos | 14 kunda 5 iqtibos | 5 |
| 💡 Kitobdan keyin 3 savol | 30 kunda 1 marta | 5 |
| 📅 2 haftada 2 ta tadbir | 14 kunda 2 ta tasdiqlangan davomat | 10 |

Halollik: missiya **olingandan keyin** qilingan ishlar sanaladi; o'z kitobi «tugatilgan» hisoblanishi
uchun kundalikda o'qilgani ko'rinishi kerak.

**Admin panel → 🎯 Missiyalar** (huquq: «Mavsumlar va kitobxonlik kampaniyalarini boshqarish»): yangi missiya (belgi, nom,
tavsif, nima hisoblanadi, maqsad, muddat, ball, holat), tahrirlash va arxivlash; har missiya uchun
«oldi / bajardi» va bajarilish foizi. A'zolar olgan missiyaning sharti va maqsadi o'zgartirilmaydi —
yangisini yarating.

**🎯 O'z missiyam** — a'zo o'zi uchun ham maqsad qo'yadi: nima hisoblanadi (bet, o'qilgan kun, seriya, kitob,
tadbir, test, iqtibos, «3 savol»), maqsad, necha kunda (1–90) va belgi. Bir vaqtda 10 tagacha. Bajarsa —
kichik ball (`missions.personal_points`, standart 2), bir oyda ko'pi bilan `missions.personal_monthly_limit` (4) tasiga;
juda oson maqsadga (masalan 1 bet) ball berilmaydi — halollik uchun. O'chirish: `missions.personal_enabled`.
Admin panelda **🎯 Missiyalar** pastida «🙋 A'zolarning o'z missiyalari»: kim nima qo'ydi, eng ko'p tanlanganlari;
**⬆️ Hammaga** — yaxshi missiyani klub missiyasiga qoralama qiladi, 🗑 — noo'rin bo'lsa o'chiradi.

### D.6. 🪪 Kitobxonlik kartam

Ilovada **Kartam** yoki botda `/kartam` — 1080×1350 rasm (Telegram/Instagram uchun qulay o'lcham).
Har safar yangi raqamlar bilan chiziladi.

### D.7. 🏛 Fakultetlar ligasi

Fakultetlar jamoa bo'lib bellashadi (hafta / oy / umumiy). O'rin — **a'zolarning o'rtacha bali**
bo'yicha (katta-kichik fakultetlar teng). Yonida: faol a'zolar (%), kundalikdagi betlar, o'qilgan
kitoblar, tadbirlarga kelishlar. Hamma uchun bepul (Imkoniyatlarda o'zgartiriladi).

### D.9. 💬 A'zolar fikrlari — iqtibos, fikr, e'tirof

A'zo istalgan vaqtda yozadi: ilovada **🌍 A'zolar fikrlari → ✍️ Yozish** yoki botda **`/fikr`**. Besh xil:

| Tur | Nima |
|---|---|
| 📖 Kitobdan iqtibos | kitobdagi yoqqan jumla (muallif va kitob bilan) |
| 💡 O'z fikrim | o'z hikmati yoki fikri |
| 📚 Kitob haqida taassurot | o'qigan kitobi haqida |
| 📅 Tadbir haqida taassurot | faqat o'zi qatnashgan tadbir haqida |
| 🌟 Klub haqida e'tirof | klub unga nima bergani haqida |

- Iqtibos va fikrlar a'zoning **«💬 Iqtiboslar sandig'i»**ga ham saqlanadi (o'zi uchun). Sandiqdagi o'zi yozgan
  iqtibosni **🌍 Hamma bilan ulashish** bilan umumiy lentaga yuborish ham mumkin.
- Matn admin tasdiqlagach **umumiy lentada** chiqadi (sozlamada «darhol chiqsin» ham qilish mumkin). A'zo
  «Meniki» bo'limida holatni ko'radi: ⏳ ko'rib chiqilmoqda / ✅ lentada / 🙈 yashirilgan.
- **6 xil kartochka dizayni**: Klassik (to'q ko'k va oltin), Qog'oz, Tungi osmon, Zumrad, Tong, Minimal.
  Kartochkada matn, manba, «Yubordi: Madina K., fakulteti» va bot nomi bo'ladi.
- **Ball**: qabul qilingan har bir matn uchun (odatda 2, oyiga 5 tagacha) va «⭐ Tanlangan» bo'lsa yoki kanalda
  e'lon qilinsa yana bir marta (odatda 5).
- **O'zi so'raydi**: kitobni o'qib tugatganda — «eng yoqqan iqtibosingizni yozing»; tadbirga 4–5 ⭐ baho berib
  izoh yozganda — «fikringizni boshqalar ham o'qisinmi?» (rozilik bilan).
- «Ismim ko'rinsin» o'chirilsa, matn «Klub a'zosi» nomi bilan chiqadi.

### D.8. 📖 Kitobxonlik izi (yil yakuni)

`academic.summary_day` kuni (odatda 20-iyun) har faol a'zoga yillik natija keladi. Unda avvalgi
raqamlar (kitoblar, tadbirlar, testlar, ball, o'rin, sertifikatlar, yutuqlar, do'stlar) bilan birga
**kundalikdagi betlar, eng uzun seriya, saqlangan iqtiboslar, bajarilgan missiyalar** va `/kartam`
taklifi ham bor.

---

# Boshqaruv: admin panel va bosh admin uchun

Hammasi telefondan, Telegram ichida qilinadi.

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
| 💳 To'lov savollari | to'lov bo'yicha savollarga (botda va to'lovlar kanalida) javob beruvchilarga |
| 📄 Hisobot va tahlil | rasmiy hisobot tayyorlovchilarga |

«Imkoniyatlar» va «Premium» sahifalari faqat **bosh administrator** (siz) uchun.

To'plamdan tashqari istalgan huquqni alohida berish mumkin. Masalan, **«Telegram Stars'ni a'zolarga yuborish»**
(`STARS_SEND`) — Premium'i va Stars hamyoni bor ishonchli adminga (29-bo'lim). **«📝 Matnlar»** (`TEXTS_MANAGE`) —
bot va kanal matnlarini o'zgartirish (12-bo'lim). Barcha huquqlar ro'yxati — oxiridagi **II-jadval**.

**🛡 Bosh admin nazorati.** Pul, kanallar, imzo-muhr, bot va klub nomiga oid sozlamalarni (`payments.*`,
`subscription.*`, `channel.chat_id`, `certificates.signer_*`, `certificates.seal`, `org.*`, `bot.*`) faqat bosh admin
o'zgartiradi — Sozlamalarda ular «🔒 faqat bosh admin» deb belgilangan. Ularning har bir o'zgarishi, kimgadir admin
huquqi berilishi yoki olinishi haqida barcha bosh adminlarga darhol «🛡 Xavfsizlik» xabari keladi (kim, qachon,
avval va endi; karta raqami yashirilgan holda). Admin panelga kompyuterdan (havola orqali) kirilsa, o'sha adminga
xabar keladi — o'zi kirmagan bo'lsa **«🔒 Barcha seanslarni yopish»**ni bosadi. **🛰 Nazorat markazi** — 12-bo'lim.

> **«Server dasturchilari sezmasin» haqida.** Matnlar va sozlamalar muharriri — tizimning **oddiy, rasmiy**
> qismi: hamma o'zgarish ma'lumotlar bazasida va audit jurnalida yoziladi, server uni xato deb ko'rmaydi
> (dastur kodi o'zgarmaydi, qayta ishga tushirish kerak emas). Lekin u yashirin «orqa eshik» emas — buni
> ataylab shunday qildik: yashirin kirish yo'li xavfsizlik teshigi bo'lardi va uni boshqalar ham topib qolishi
> mumkin edi. Sizning nazoratingiz — bosh admin huquqi orqali.

## 3. Tadbir va davomat

1. **📅 Tadbirlar va tanlovlar → Tadbirlar** → yangi tadbir: nomi, boshlanish/tugash sanasi, joyi.
   **Davomat ochilish/yopilish — faqat soatini belgilaysiz** (masalan, 14:50 va 16:10); sana tadbir
   kuniga o'zi qo'yiladi. Bo'sh qoldirsangiz — boshlanishdan 10 daqiqa oldin ochiladi, 20 daqiqa keyin
   yopiladi.
2. Belgilangan vaqtda davomat **o'zi ochiladi**, a'zolarga xabar boradi. Tadbir e'loni (bot va kanal)
   endi boshlanish, davomat ochilish vaqti va smenalarni aniq ko'rsatadi.
3. Tadbirda **Davomat** sahifasini proyektor/ekranga chiqaring: QR kod va 6 belgili kod **har 10
   soniyada** yangilanadi (suratga olib boshqaga yuborish foyda bermaydi).
4. A'zo botda **✅ Davomat** → QR skaner yoki kodni yozadi — 5 soniyalik ish.
5. Tadbirdan 30 daqiqa keyin bot qatnashganlardan **⭐ baho** so'raydi. Baholar va fikrlar shu
   tadbirning davomat sahifasi pastida ko'rinadi.

**📖 Tadbirga kitob tanlovi biriktirish.** Tadbir oynasining o'zida **«Shu tadbirga kitob tanlovi
biriktirish»**ni belgilab, bitta tadbirga **bitta** kitob tanlovini qo'shasiz: nomi, kitobi (yoki
bir nechta), kitob uchun ball va yakunlash bonusi. Tanlov muddati tadbir sanasiga qarab o'zi qo'yiladi.
U **«Kitob tanlovlari»** tabida ham ko'rinadi («📅 Tadbirga biriktirilgan» belgisi bilan) — o'sha yerdan
boshlaysiz (e'lon qilib yoki e'lonsiz), qatnashchilarni tasdiqlaysiz va hisobotini olasiz. Belgini
olib tashlasangiz, tanlov o'chmaydi — tadbirdan ajraydi, xolos.

**🎓 G'oliblar sertifikati dizaynini shu yerda tanlaysiz** — pastdagi «6. Sertifikatlar» bo'limiga qarang.

## 4. Murojaatlar

A'zolar botda **💬 Yordam → ✉️ Adminga yozish** orqali yozadi. Xabar `SUPPORT` huquqi bor
adminlarga keladi. Javobni botning o'zida («Javob yozish») yoki panelda **📨 Murojaatlar**dan
berasiz — a'zo sizning ismingizni ko'rmaydi, javob «Klub rahbariyati» nomidan boradi.

**Umumiy va to'lov murojaati — alohida.** Bir a'zo ham oddiy savol, ham to'lov savolini yozsa, ular aralashmaydi:
har biri o'z suhbati sifatida yuritiladi. Paneldagi **📨 Murojaatlar** faqat **umumiy** savollarni ko'rsatadi
(badge ham faqat umumiylarni sanaydi); **to'lov** savollari to'lovlar kanalida hal qilinadi va ularga «💳 To'lov
savollari» huquqi borlar (hamda bosh admin) javob beradi. Shunday qilib, to'lovga berilgan javob hech qachon
umumiy murojaatda ko'rinmaydi va «kim javob berdi» ham to'g'ri saqlanadi.

**⭐ Stars buyurtmalari shu bo'lim ichida.** «📨 Murojaatlar» endi ikki qismli: **✉️ Murojaatlar** (a'zolar savollari)
va **⭐ Stars buyurtmalari** (karta orqali olingan Telegram Stars). Yuqoridagi tugmalar bilan almashtirasiz. Har bir
qism o'z huquqiga qarab ko'rinadi: murojaatlar — `SUPPORT_MANAGE`, Stars — `STARS_SEND` (shuning uchun faqat Stars
huquqi borlar ham «📨 Murojaatlar»ni ochib, to'g'ridan-to'g'ri Stars buyurtmalariga tushadi).

Har bir adminga kelgan nusxada holat yoziladi: **⏳ javob kutmoqda** → kimdir javob bersa, **hamma adminning
nusxasida** (bosh adminnikida ham) «✅ Javob berildi — Ism, vaqt» va javobning boshi. Uzun xabar to'liq keladi;
**📄 Batafsil** — butun yozishma (savollar, javoblar, kim javob bergani); **🔒 Yopish** — murojaatni yopadi
(hamma nusxada «🔒 Yopildi»). Kanalda kimdir «✍️ Javob yozish»ni bossa, hamma nusxada «✍️ Ism javob yozmoqda…»
chiqadi — ikki admin bir savolga ikki marta javob yozib o'tirmaydi.

**To'lov bo'yicha savollar** (`/paysupport` yoki «💳 To'lov bo'yicha» mavzusi) boshqacha: ular **💳 To'lovlar
kanaliga** «✍️ Javob yozish» tugmasi bilan keladi. Ularga **bosh admin** va **«💳 To'lov savollari»** huquqi
berilgan adminlar javob beradi — kanalning o'zida («Reply» yoki tugma), guruhda yoki botda. Javob kanalga
ham «↪️ Javob» bo'lib yoziladi. Kanal sozlanmagan bo'lsa — savol shu adminlarga botda keladi.

## 5. Kitobxon pasporti

Har bir a'zoda rasmli ID-karta bor: rasmi, ismi, fakulteti, kursi, guruhi va a'zo raqami (KH-000042).
Ball va reyting har kuni o'zgargani uchun kartaga yozilmaydi — **QR kodni skanerlagan kishi** pasport
haqiqiyligini va a'zoning **jonli natijalarini** (ball, reytingdagi o'rni, kitoblar, tadbirlar,
yutuqlar, sertifikatlar) ko'radi.

- A'zo rasmini o'zi almashtiradi: botda **🪪 Pasportim → 📷 Rasmni almashtirish** yoki ilovada
  «Profil → 📷 Yangi rasm». Rasm o'zi to'g'rilanadi va kesiladi.
- Noma'qul rasm bo'lsa: admin panel → **A'zolar** → a'zo → **🖼 Pasport rasmini o'chirish**.
- Premium a'zolar dizaynni tanlaydi: **oltin** (haqiqiy oltin rang), **kumush**, **tungi ko'k**, **yoqut**,
  **okean**, **lavanda** (klassik yashil — hamma uchun).

## 6. Sertifikatlar

**Avtomatik beriladi:**

- har bir test yopilganda **1-, 2-, 3-o'rin** egalariga (tadbir testida — faqat davomatdan
  o'tganlarga);
- agar testda **«Testdan o'tgan har bir a'zoga sertifikat»** belgilansa — o'tish balidan o'tgan
  **hamma** ishtirokchiga «ishtirok sertifikati» (nafaqat 1–3 o'rin);
- har oy boshida (1-sana, soat 10:00 dan) o'tgan oy reytingidagi **eng faol uchlikka**.

Sertifikat haqida xabar darhol boradi. **PDF nusxasini yuklab olish va chop etish — 💎 Premium**
imkoniyati (Premium a'zoga PDF xabar bilan birga keladi). Premium bo'lmagan a'zo sertifikatni ilovada
ko'radi va **onlayn tasdiq havolasini** istalgan kishiga ko'rsata oladi. Buni **🧩 Imkoniyatlar →
📄 Sertifikat PDF** da «Hammaga» qilib, hamma uchun ochib qo'yishingiz mumkin.

**🎓 Sertifikatlar** sahifasida qo'lda ham berasiz (masalan, «Faol kitobxon»), yuklab olasiz yoki bekor
qilasiz.

### 🎨 Sertifikat dizayni (vizual muharrir)

**🎓 Sertifikatlar → 🎨 Dizaynlar (muharrir)** bo'limida o'z sertifikat dizayningizni yaratasiz:

1. **➕ Yangi dizayn** → **🖼 Rasm yuklash**: o'z dizayningizni **PNG, JPG yoki PDF** holida yuklaysiz
   (PDF bo'lsa, birinchi sahifasi olinadi). Rasm qanday bo'lsa, shundayligicha ishlatiladi — ustiga
   hech qanday qo'shimcha parda yoki xiralashtiruvchi qatlam qo'yilmaydi.
2. Kerakli elementlarni (**ism-familiya, QR kod, muhr, imzo, sana, tekshirish kodi, tashkilot/klub
   nomi, erkin matn** va h.k.) qo'shib, ularni sichqoncha bilan **xohlagan joyingizga** sudraysiz,
   burchagidan **o'lchamini** o'zgartirasiz; har biriga **shrift, o'lcham, rang va tekislashni**
   belgilaysiz.
3. **👁 Namuna** tugmasi tayyor sertifikatni (PDF ko'rinishida) namuna ma'lumotlar bilan ko'rsatadi.
   **💾 Saqlash** bosilganda dizayn saqlanadi va keyin ham tahrirlashingiz mumkin.
4. **«Asosiy dizayn»** belgilangan dizayn test g'oliblari va oy yetakchilariga **avtomatik** beriladi.
   Alohida testga esa **⚙️ test sozlamalari → Sertifikat dizayni** orqali o'z dizaynini biriktirasiz.

**🎓 Tadbir g'oliblari sertifikatini tadbir oynasidan tanlash.** Tadbirni yaratish/tahrirlash oynasida
**«🎓 G'oliblar sertifikati dizayni»** bo'limi bor. U yerda tayyor sertifikatning **namunasi** ko'rinadi
va to'rtta tanlovdan birini qo'yasiz:

- **🔄 Navbatdagi** — tanlamasangiz, 12 ta tayyor dizayn **navbat bilan** ishlatiladi; qaysi biri
  navbatda turgani grid'da **➡️** belgisi bilan ko'rsatiladi;
- **tayyor dizaynlardan birini** — rasmchalardan bosib tanlaysiz (bot aynan shu dizaynda chizadi);
- **mening shablonlarim** — **🎓 Sertifikatlar** bo'limida yaratgan o'z shablonlaringizdan biri;
- **🖼 O'z rasmim** — A4 yotiq rasm yuklaysiz, matn uning ustiga yoziladi.

Bir tanlov boshqasini almashtiradi; o'zgartirishni tadbir boshlangunicha adminlar, test yakunlangunicha
bosh admin kirita oladi.

**Sovg'a sifatida qo'lda berish:** **🎓 Sertifikatlar → ➕ Sertifikat berish** da a'zoni, dizaynni va
matnni tanlaysiz; **«Shaxsiy xabar»** yozsangiz — sertifikat PDF o'sha tabrik bilan birga bot orqali
sovg'a sifatida darhol yuboriladi. Bu test natijasiga bog'liq emas — istalgan munosib sabab bilan.

**Sozlash:** **⚙️ Sozlamalar → 🎓 Sertifikatlar** — imzo egasining lavozimi va ismi (masalan,
«Klub rahbari — A. Bahodirov»), avtomatik berishni o'chirish.

### 🔐 Sertifikatdagi kod nima va undan qanday foydalaniladi

Har bir sertifikatning **yagona tekshirish kodi** bor (masalan `K7F2Q-9XA3B`) — u QR kod yonida yozilgan.
Kod sertifikatning «pasport raqami»: soxta sertifikatni haqiqiysidan ajratadi.

| Kim | Qanday tekshiradi | Nima ko'radi |
|---|---|---|
| Istalgan kishi (ish beruvchi, institut, grant komissiyasi) | QR kodni telefon kamerasi bilan skanerlaydi **yoki** `https://<sizning-manzilingiz>/v` sahifasida kodni yozadi (QR shart emas) | ✅ Haqiqiy sertifikat: kimga, nima uchun, qachon berilgan; bekor qilingan bo'lsa — ⛔ va sanasi |
| Siz (admin) | **🛡 Ishonch markazi → 🎓 Sertifikatni tekshirish** yoki **🎓 Sertifikatlar** dagi qidiruv | yuqoridagilar + bekor qilish sababi |
| A'zo | ilovada sertifikatini ochib, **onlayn tasdiq havolasini** ulashadi | — |

Imkoniyatlari:

- Sertifikat qaysi dizaynda yuklab olinmasin, **kod bitta** — barcha nusxalar shu kod bilan tasdiqlanadi.
- Sertifikatni **bekor qilsangiz** (masalan, adashib berilgan), kod tekshirilganda «⛔ Bekor qilingan» chiqadi —
  qog'ozdagi nusxa ham kuchini yo'qotadi.
- Kod rezyume, grant va stipendiya hujjatlariga yoziladi: tekshiruvchi sizga qo'ng'iroq qilmasdan o'zi
  ishonch hosil qiladi.
- **Kitobxon pasporti**dagi kod ham xuddi shu sahifada tekshiriladi (a'zoning jonli natijalari chiqadi).
- **🗂 Hujjatlar → Sertifikatlar reyestri** — davr bo'yicha barcha sertifikatlar va kodlari (Excel/Word/PDF).

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

> **Qayerda:** «🧩 Imkoniyatlar» endi alohida menyu emas — **💎 Premium va imkoniyatlar** bo'limi ichida,
> yuqoridagi «🧩 Imkoniyatlar» tugmasi ostida (faqat bosh admin).

**🧩 Imkoniyatlar** sahifasida har bir bo'lim uchun uchta holat bor:

- **O'chiq** — a'zolar uni ko'rmaydi;
- **Hammaga** — barcha a'zolar uchun;
- **💎 Premium** — faqat Premium a'zolar uchun (boshqalar 💎 belgisini va taklifni ko'radi).

«Yoqilganda a'zolarga e'lon yuborilsin» belgilangan bo'lsa, bo'lim yoqilganda hamma a'zoga
**«🎉 Tabriklaymiz, bot yangilandi! Endi sizda yangi imkoniyat bor: …»** xabari boradi.

**«🎁 Sizning foydangiz»** (do'stlarni taklif qilish) bu ro'yxatda yo'q — u **doim ochiq**. Barcha imkoniyatlar va
ularning odatiy holati — oxiridagi **I-jadval**.

## 9. Premium obuna va hissalar (daromad)

> **Qayerda:** **💎 Premium va imkoniyatlar** bo'limi (bosh admin). Bitta bo'limda ikki qism: «💎 Premium va
> to'lovlar» va «🧩 Imkoniyatlar».

To'lov **Telegram Stars (⭐)** orqali: karta ma'lumotlari, shartnoma yoki to'lov tizimi kerak emas —
Telegram raqamli xizmatlar uchun aynan shu usulni talab qiladi.

**Yoqish:**

1. **🧩 Imkoniyatlar → 💎 Premium obuna → Hammaga** (e'lon bilan).
2. Xohlasangiz **❤️ Klubni qo'llab-quvvatlash → Hammaga** (ixtiyoriy hissa: 50/100/250/500 ⭐).
3. Qaysi bo'limlar Premium bo'lishini o'sha sahifada tanlang.

> Diqqat: «💎 Premium» deb belgilangan bo'limlar Premium do'koni **o'chiq** bo'lsa ham faqat Premium
> a'zolarga ochiq qoladi. Shuning uchun 1-qadamni (do'konni yoqish) unutmang.

**Premium nima beradi (boshlang'ich holat):** asosiy imkoniyatlar — kitob, tadbir, davomat, test,
reytingning **«Hafta»** va **«Hammasi»** bo'limlari — **bepul**. Premium a'zoga qo'shimcha:

- reytingning qolgan bo'limlari (oy, mavsum, fakultetlar);
- sertifikatni PDF yuklab olish va chop etish;
- **🗂 Kitobxonlik portfoliosi** — barcha kitoblar, sertifikatlar, testlar, tadbirlar va yutuqlar bitta
  PDF'da (rezyume, grant, stipendiya uchun);
- oltin va boshqa pasport dizaynlari, 📊 haftalik xulosa, reytingda 💎 belgisi.

**Narxlar (talabalarga mos):** 1 oy — 50 ⭐ (≈9 000 so'm), 3 oy — 120 ⭐ (≈22 000 so'm), 1 yil — 400 ⭐
(≈75 000 so'm). **💎 Premium** sahifasida o'zgartirasiz yoki tarifni «Sotuvdan olish» mumkin.

**A'zoni bezdirmaslik uchun:**

- har bir a'zo **bir marta 7 kunlik bepul sinov** oladi (pul yechilmaydi; **⚙️ Sozlamalar → 💎 Premium**
  da kunlar sonini o'zgartirasiz yoki 0 qilib o'chirasiz);
- Premium tugashidan bir kun oldin bitta muloyim eslatma boradi (kunduzi);
- sovg'a o'yinlarida **chegirma** (masalan, −50%) yutib olinadi — narx a'zo uchun avtomatik kamayadi.

**Bosh administratorlar** umrbod Premium'ga ega (♾) — hech narsa qilish shart emas.

**🎁 Ommaviy sovg'a:** **💎 Premium** sahifasidagi «🎁 Ommaviy sovg'a» bo'limida bir vaqtda **hammaga** yoki
bir **fakultet, kurs, guruh**ga N kunlik Premium berasiz (masalan, «Bilimlar kuni munosabati bilan hammaga 7 kun»).
Avval necha kishiga borishi ko'rsatiladi, keyin tasdiqlaysiz. «Faqat Premium'i yo'qlarga» belgisi bor. Premium'i
borlarga kunlar joriy muddatidan keyin qo'shiladi; bosh adminlar va umrbod Premium egalari kirmaydi. Har bir
a'zoga 🎉 tabrik boradi, to'lovlar kanaliga va audit jurnaliga bitta qator yoziladi.

**Premium sovg'a qilish (bitta a'zoga):** o'sha sahifada a'zoni tanlab, kunlar sonini yozasiz (masalan, oy
g'olibiga 30 kun yoki naqd to'laganga) yoki **«Umrbod»** belgisini qo'yasiz.

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
siz tasdiqlaysiz. Karta orqali uch narsa sotiladi:

- **💎 Premium** — tasdiqlashingiz bilan **o'zi yoqiladi**;
- **❤️ Hissa** — klubga yordam;
- **⭐ Telegram Stars** — Stars'ni o'zi sotib ololmaydigan a'zolar uchun (quyida).

**⭐ Stars'ni karta orqali sotish.** Bu xizmat a'zoga **«⭐ Telegram Stars orqali»** usulining ichida
(«⭐ Stars'ingiz yo'qmi?») ko'rinadi. A'zo to'plamni tanlaydi (50, 100, 250, 500 ⭐). Narx so'mda ko'rsatiladi
(1 ⭐ ≈ 250 so'm, **⚙️ Sozlamalar → 💳 Karta orqali to'lov** da o'zgartirasiz). A'zo kartangizga pul o'tkazib,
chekni yuboradi. Keyingi qadamlar:

1. **Bosh admin** chekni tasdiqlaydi.
2. Buyurtma **«⭐ Stars yuborish»** huquqli adminga ketadi: «Bosh admin tomonidan tasdiqlandi, <a'zo> ga N Stars
   kerak» va qadam-baqadam ko'rsatma bilan.
3. U Stars'ni Telegram'da yuborib, **«✅ Stars yuborildi»** ni bosadi.
4. A'zoga xabar boradi. Har bir qadam to'lovlar kanaliga yoziladi.

To'liq jarayon — **29-bo'lim**.

> Nega bot o'zi yubormaydi: Telegram botlarga Stars berishga ruxsat bermaydi — Stars'ni faqat odam
> sovg'a qila oladi. Payme/Click orqali to'liq avtomatik to'lov uchun klub nomidan merchant (shartnoma) kerak
> bo'ladi — kerak bo'lsa, keyin qo'shamiz.

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

> **Qayerda:** Panel ixchamlashtirildi — **🏅 Yutuqlar**, **🎁 Sovg'alar**, **🎲 Sovg'a o'yinlari**, **🏁 Taklif
> tanlovlari** va **🎯 Missiyalar** endi bitta **🎁 Sovg'a va yutuqlar** bo'limida, yuqoridagi tugmalar bilan
> almashtiriladi. Har qism o'z huquqiga qarab ko'rinadi.

Promokodlarni adolatli qoida bo'yicha tarqatish: **🎁 Sovg'a va yutuqlar → 🎲 Sovg'a o'yinlari**.

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
| 🆕 Botga qo'shilgan birinchi N kishi | masalan, «1–15-oktabr kunlari botga qo'shilgan birinchi 20 kishiga Premium'ga −50%». Sovg'a qo'shilishi bilan **darhol** beriladi |

**Sovg'a turi:** promokod (hamkor ilovalari uchun), **💎 N kunlik Premium** yoki **🎟 Premium'ga chegirma**
(masalan, −30%, 30 kun amal qiladi). Premium va chegirma uchun kod kerak emas.

**Qanday ishlatiladi:**

1. **+ Yangi o'yin** → nomi, sovg'a, qoida, g'oliblar soni, davr («Shu oy» tugmasi).
2. **Belgilangan vaqtda avtomatik** — masalan, oyning oxirgi kuni soat 20:00. **🔁 Har oy takrorlansin**
   belgilansa, keyingi oyning o'yini o'zi rejalashtiriladi — har oy qayta yaratish shart emas.
3. Yoki **Ko'rish va o'tkazish** → kim g'olib bo'lishini oldindan ko'rasiz → **🎲 Hozir o'tkazish**.

G'oliblarga kod va tabrik xabari darhol boradi, kod ilovadagi **🎁 Sovg'alarim** bo'limida ochiladi.
«E'lon qilinsin» belgilangan bo'lsa, barcha a'zolar va kanal g'oliblar ro'yxatini ko'radi. A'zolar
ilovada yaqindagi o'yinlarni va so'nggi g'oliblarni ko'rib turadi — bu qatnashishga undaydi.
Kodlar yetmasa, o'yin o'tkazilmaydi va sizga xabar keladi — kod qo'shsangiz, o'zi o'tkaziladi.

### Test g'oliblariga sovg'a berish (qayta berib qo'ymaslik uchun)

**🎁 Sovg'alar** → sovg'ani tanlang → **Berish va kodlar** → **«📝 Test g'oliblari»** bloki. Oxirgi 90 kun
testlari chiqadi, har birida **1-, 2-, 3-o'rin** egalari. Har bir o'rin yonida **«🎁 Berish»** tugmasi:
bosganingizda shu sovg'aning navbatdagi kodi o'sha o'quvchiga boradi va o'rin **«✅ berilgan»** bo'lib
qoladi — bir o'ringa ikki marta sovg'a berib bo'lmaydi. Masalan, oyda 4 ta tadbir bo'lsa — 12 ta kod,
hech kim tushib qolmaydi va hech kim ikki marta olmaydi.

Testdan tashqari **istalgan a'zoga** ham bera olasiz (yuqoridagi qidiruvdan a'zoni tanlab, «Berish»). Bir a'zoga shu sovg'a
avval berilgan bo'lsa, panel ogohlantiradi — tasdiqlasangizgina yana beriladi.

## 10.5. 📖 Kitob tanlovlari (1 hafta/1 oy — 1 kitob)

**Qayerda?** Kitob tanlovi endi alohida menyu emas — u **📅 Tadbirlar va tanlovlar** bo'limi ichida,
yuqoridagi **«📖 Kitob tanlovlari»** tugmasi ostida. Ya'ni tadbirlar bilan bir joyda yaratasiz va
boshqarasiz.

Bir vaqtning o'zida bir nechta kitob tanlovini o'tkazishingiz mumkin — masalan, oy davomida 4 marta
«1 hafta — 1 kitob» va 1 marta «1 oy — 1 kitob», har biriga boshqa kitob. **Har bir tanlov butunlay
alohida**: o'z kitobi, o'z qatnashchilari, o'z kanal posti va o'z hisoboti bilan — hech narsa
aralashmaydi.

**📅 Tadbirlar va tanlovlar → 📖 Kitob tanlovlari** bo'limida:

1. **➕ Yangi tanlov** → nom (masalan «1 hafta — 1 kitob, noyabr 1-hafta»), sana oralig'i, kitob(lar)ni
   belgilash, kitob uchun ball va yakunlash bonusi. **Ballar oxirgi marta ishlatilgan holatda tayyor
   turadi** — o'zgartirsangiz, keyingi tanlov ham shu qiymatdan boshlanadi; o'zgartirmasangiz, oldingidek
   qoladi. Saqlang — tanlov «Qoralama» bo'ladi.
2. **▶️ Boshlash + e'lon** — tanlovni faollashtiradi va kanalga **shu tanlovning** alohida postini
   joylaydi (boshqa tanlovlar postiga aralashmaydi). «Boshlash (e'lonsiz)» ham bor.
3. A'zolar botda **/tanlov** yoki «📖 Kitob tanlovlari» orqali faol tanlovlarni ko'radi, biriga
   **«✅ Qatnashaman»**, kitobni o'qib bo'lgach **«📘 O'qib tugatdim»** ni bosadi.
4. **👥 Qatnashchilar** — kim qatnashyapti, kim «o'qib tugatdim» degan. Har birini **«✅ Tasdiqlash»**
   bilan tasdiqlaysiz — shunda a'zoga shu tanlovning ballari (kitob uchun ball + bonus) **bir marta**
   qo'shiladi va unga tabrik boradi.
5. **🏁 Yakunlash** — tanlovni tugatadi. **📄 Hisobot** — aynan shu tanlov bo'yicha qatnashchilar va
   yakunlaganlar ro'yxati (Excel/Word/PDF), boshqa tanlovlardan ajralgan holda.

Ikki tanlov bir xil kitobdan foydalansa ham, ularning qatnashchilari va ballari aralashmaydi — har
bir qatnashuv o'z tanloviga bog'langan.

## 11. Telegram kanal (@FJSTIMutolaaxona) — endi «📢 Xabarlar» ichida

Bot kanalga o'zi qiziqarli postlar joylaydi va o'quvchilarni botga taklif qiladi. **Yangi:** kanal alohida
bo'lim emas — u endi **📢 Xabarlar** bo'limi ichida. Bitta joyda xabar yozasiz va **«Qayerga yuborish»**da
tanlaysiz: **📱 bot** (a'zolarga) va/yoki **📣 kanal(lar)**ga. Bir nechtasini birdek belgilash mumkin —
masalan, matn botga ham, kanalga ham birdek ketadi.

**Ulash (bir marta):**

1. Telegram'da kanal → **Administratorlar → Administrator qo'shish** → botni toping → **«Xabar
   joylash»** huquqini yoqing.
2. **⚙️ Sozlamalar → 📣 Telegram kanal** → «Bot klub kanaliga post joylaydi» ni yoqing. Kanal manzili
   allaqachon `@FJSTIMutolaaxona` deb yozilgan.
3. **📢 Xabarlar** bo'limidagi **🧪 Sinov posti** ni bosing — bir necha soniyada kanalda chiqadi.
   Chiqmasa, xato sababi ko'rinadi (ko'pincha — bot admin qilinmagan).

**➕ Bir nechta kanal (A kanal, B kanal...).** Klub kanalidan tashqari kanallarga ham joylamoqchi bo'lsangiz,
**⚙️ Sozlamalar → 📣 Telegram kanal → «Qo'shimcha kanallar»**ga ularni vergul bilan yozing: `@kanal` yoki
`-100…` ID. Nom berish uchun `Nom=@kanal` (masalan `Ustozlar=@kanalB`). Shu kanallar **📢 Xabarlar**dagi
«Qayerga yuborish»da ham chiqadi. **Muhim:** bot har bir kanalda administrator bo'lishi va «Xabar joylash»
huquqiga ega bo'lishi kerak.

### 📢 Majburiy obuna (kanalga obuna shart)

«Majburiy obuna» yoqilgan bo'lsa, a'zo kanalga obuna bo'lmaguncha botdan ham, ilovadan ham
foydalana olmaydi; obunadan chiqib ketsa ham, keyingi urinishda «**Davom etish uchun kanalga obuna
bo'ling**» deb chiqadi.

**Muhim:** bu tekshiruv ishlashi uchun **bot o'sha kanalda administrator bo'lishi shart**. Agar bot
admin bo'lmasa, tizim a'zoni to'sib qo'ya olmaydi (hammani qulflab qo'ymaslik uchun) — natijada
obunasiz ham bot ishlayveradi. Shuning uchun **⚙️ Sozlamalar → 📢 Majburiy obuna** bo'limi tepasida
holat ko'rsatiladi:

- ✅ **«Majburiy obuna ishlayapti»** — hammasi joyida;
- ⚠️ **«YOQILGAN, lekin ishlamayapti»** — bot qaysi kanalda admin emasligini aytadi. O'sha kanalga
  botni admin qiling — tekshiruv o'z-o'zidan ishlay boshlaydi.

Sozlash: **⚙️ Sozlamalar → 📢 Majburiy obuna** — yoqish/o'chirish va shart bo'lgan kanallar ro'yxati
(bo'sh bo'lsa — klub kanali).

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

**Adminlar oldindan ko'radi (5 daqiqa).** Har bir avtomatik post kanalga chiqishidan 5 daqiqa oldin
adminlarga botda ko'rsatiladi. Uchta tugma bor:

- **✅ Hozir joylash** — darhol chiqadi;
- **❌ Bekor qilish** — kanalga chiqmaydi;
- **✏️ Matnni o'zgartirish** — yangi matnni botga yozasiz (qalin/kursiv saqlanadi), post shu matn
  bilan chiqadi.

Hech kim javob bermasa — post belgilangan vaqtda **o'zi chiqadi**. Bitta admin hal qilgach, boshqalarning
tugmasi ishlamaydi (ikki marta joylanmaydi). Daqiqalar soni: **⚙️ Sozlamalar → 📣 Telegram kanal**
(0 — tekshiruvsiz). Xuddi shu ishni **📢 Xabarlar** bo'limida ham qilasiz («▶️ Hozir joylash»,
«✏️ Tahrirlash»).

**O'zingiz yozish:** **📢 Xabarlar → Yangi xabar** — «Qayerga yuborish»da kanalni (yoki bir nechta kanalni)
belgilaysiz, matn yozasiz, rasm, stiker va istalgan vaqtga rejalashtirish qo'shasiz.

**Stikerlar:** botga **/stiker** deb yozing va yoqqan stikerlaringizni yuboring (oddiy, animatsion yoki
Premium stikerlar). Bot har birining kayfiyatini emojisidan aniqlaydi va mos joyda ishlatadi: 🎉 quvnoq
stikerlar — g'oliblar postidan va a'zolarning g'alaba xabarlaridan keyin, 📚 kitobli stikerlar — kitob
postlaridan keyin, 👋 salomlashuvchilar — yangi a'zoga. Kanal postlarida premium **emojilar** faqat
botda Fragment'dan olingan username bo'lsa chiqadi — kanalda stikerlar va oddiy emojilar ishlatiladi
(batafsil — 30-bo'lim).

## 12. Bot xabarlari

Bot xabarlari kitobxonlar tilida: yangi kitob — «Har bir kitob — yangi dunyo», tadbir eslatmasi —
«kitobingiz va savollaringizni olib keling». O'qish eslatmalarida **o'sha kitobdan iqtibos** chiqadi
(kun iqtibosi sifatida yuborilganlaridan), ro'yxatdan o'tganda va haftalik xulosada esa mashhur
kitobxonlik hikmatlari (Navoiy, Dekart, xalq maqollari...).

G'alaba xabarlari (testda 1–3-o'rin, yutuq, sertifikat, sovg'a, Premium) Telegram'ning **🎉 konfetti
effekti** va quvnoq stiker bilan keladi. O'chirish: **⚙️ Sozlamalar → 🔔 Bildirishnomalar**. Xabar
matnlarini **🔔 Bildirishnomalar → Shablonlar** da o'zingiz o'zgartirasiz.

### 📝 Matnlar — botning har bir so'zi sizning qo'lingizda

> **Qayerda:** «📝 Matnlar» endi alohida menyu emas — **⚙️ Sozlamalar** bo'limi ichida, yuqoridagi
> «📝 Matnlar (bot va kanal)» tugmasi ostida (fakultetlar singari sozlamalar ichiga olindi).

Admin panel → **⚙️ Sozlamalar → 📝 Matnlar (bot va kanal)** (huquq: «📝 Matnlar», bosh adminda doim bor). Bo'limlar: ro'yxatdan
o'tish, salomlashish, menyu javoblari, yordam va murojaatlar, Premium, karta orqali to'lov, mutolaa, a'zolar fikrlari,
a'zolarga bildirishnomalar, **📣 Kanal postlari** (kanalga chiqadigan postlar iboralari) va boshqalar.

- Xabarni bosing → o'zingizcha yozing → **Saqlash**. `{first_name}` kabi qavsdagi so'zlar o'rniga bot o'zi
  ism, sana, summa qo'yadi — ularni o'chirmang (o'chirsangiz, saqlashdan oldin ogohlantiradi).
- **5 tagacha variant**: bot ularni navbatma-navbat yuboradi, bir xil xabar ketma-ket takrorlanmaydi. Ko'p xabarda
  tayyor 5 tadan variant bor. Hammasi uchun o'chirish — `texts.rotate`.
- **📤 Botda ko'rish** — xabar sizga botda keladi, Telegram'da qanday chiqishini ko'rasiz. **↩️ Asl holiga
  qaytarish** — dasturdagi matn.
- **⬇️ Nusxa (fayl)** — hamma o'zgarishlaringiz bitta faylga; **⬆️ Fayldan tiklash** (faqat bosh admin) — qaytarish.
- To'lov matnlari (karta raqami, narxlar) faqat bosh adminniki. Har bir o'zgarish audit jurnalida va bosh adminga
  xabar qilinadi.

**Kanal postlari qayerdan keladi?** Ular dasturdagi tayyor shablonlardan tuziladi (tadbir, yangi kitob, kun
iqtibosi, kitob yakuni, eslatmalar, taklif postlari); iboralari endi **📝 Matnlar → 📣 Kanal postlari**da.
Har bir post chiqishdan oldin **📢 Xabarlar** bo'limida turadi (5 daqiqa admin ko'rigi) — u yerda tahrirlaysiz
yoki bekor qilasiz.

### 🛰 Nazorat markazi (faqat bosh admin)

Bir sahifada: murojaatlar, cheklar, Stars buyurtmalari, a'zolar fikrlari, qo'lda davomat va boshqa navbatlar —
nechta kutmoqda va eng eskisi qancha vaqtdan beri; bot xabarlari navbati (yuborildi / xato / o'tkazildi);
kanalga chiqmagan postlar; so'nggi harakatlar (kim nima qildi) va shu hafta kim nechta murojaatga javob berdi.
Qatorni bosing — o'sha bo'limda o'zingiz hal qilasiz; qaroringiz boshqa adminlarning botdagi nusxalarida ham ko'rinadi.

## 13. A'zolikni bekor qilish va ma'lumotlarni o'chirish

**A'zolar** → a'zo → «Bloklash» yonida:

- **🚪 A'zolikni bekor qilish** — sababini yozasiz (a'zoga boradi). A'zo xabar olmaydi va reytingda
  ko'rinmaydi. Ma'lumotlari 30 kun saqlanadi;
- **♻️ A'zolikni tiklash** — chiqib ketgan a'zoni qaytarish (ballari, sertifikatlari joyida);
- **🗑 Ma'lumotlarini o'chirish** — faqat **bosh administrator**: ism, telefon, Telegram, rasmlar,
  cheklar va xabarlar butunlay o'chadi (tasdiqlash uchun «O'CHIRISH» deb yozasiz). Klub statistikasi
  (ballar, davomat) nomsiz holda qoladi.

**A'zo botni bloklasa** — avtomatik «klubdan chiqqan» bo'ladi:

- **14 kun ichida** /start bossa — **«♻️ Ma'lumotlarimni tiklash»** bilan hammasini o'zi tiklaydi;
- **14–30 kun ichida** — **tiklash so'rovini** yuboradi; a'zolarni boshqaruvchi adminlarga botda
  **✅ Tiklash / ❌ Rad etish** tugmalari bilan xabar keladi;
- **30 kundan keyin** — shaxsiy ma'lumotlari avtomatik o'chiriladi, xohlasa yangidan ro'yxatdan o'tadi.

Adminlar botni bloklasa, klubdan chiqarilmaydi (adashib bloklash mumkin). A'zo o'zi ham **⚙️ Sozlamalar →
🚪 A'zolikni bekor qilish** orqali chiqa oladi.

## 14. 🎁 «Sizning foydangiz» — do'stlarni taklif qilish

Bu bo'lim **doim ochiq** (uni o'chirib bo'lmaydi). A'zo uni uch joydan ochadi:

- botning bosh menyusidagi **🎁 Sizning foydangiz** tugmasi;
- **`/referal`** buyrug'i (eski `/taklif` ham ishlaydi; buyruqlar menyusida ham bor);
- ilovada bosh sahifa va profildagi **🎁 Sizning foydangiz** kartochkasi (qisqacha: havola, nechta do'st,
  ular to'plagan ball) → bosilsa, to'liq sahifa.

Har bir a'zoning shaxsiy havolasi bor. Do'sti shu havola orqali ro'yxatdan o'tib, **birinchi tadbirga kelsa**
(davomat tasdiqlansa), taklif qilgan a'zo **+20 ball** va **7 kunlik Premium** oladi. Tadbirga kelish sharti
soxta akkauntlardan himoya qiladi. Bir a'zo oyiga 5 tagacha mukofot oladi.

Sozlash: **⚙️ Sozlamalar → 👥 Do'stlarni taklif qilish** (`referral.points`, `referral.premium_days`,
`referral.monthly_limit`).

> Avval havola ba'zan «yopiq» chiqardi: u faqat `BOT_USERNAME` muhit o'zgaruvchisiga bog'liq edi. Endi bot
> nomini Telegram'dan o'zi so'rab oladi — havola har doim ishlaydi.

### 🎁 «Sizning foydangiz» sahifasi — a'zo o'z hissasini ko'radi

A'zo ko'radi:

- shaxsiy havola, «📤 Yuborish» va «📋 Nusxalash»;
- **📊 Qisqacha**: nechta do'st taklif qilgan va ulardan nechtasi tadbirga kelgan; olib kelgan do'stlari jami
  **qancha ball to'plagani**, nechta kitob o'qigani, necha marta tadbirga kelgani va test yechgani; a'zoning o'zi
  taklif uchun olgan ballar va Premium kunlar;
- **do'stlari ro'yxati**: ismi, qachon qo'shilgani, tadbirga kelgan-kelmagani (✅/⏳) va **ballari**. Botda
  10 tagacha, ilovada hammasi;
- **Eng faol taklif qiluvchilar** — butun klub bo'yicha jadval va a'zoning o'z o'rni;
- davom etayotgan va yaqinda tugagan **taklif tanlovlari**.

A'zo nimani ko'rishini **⚙️ Sozlamalar** da tanlaysiz:

| Sozlama | Ma'nosi |
|---|---|
| `referral.friend_details` | FULL — do'stlarning ismi, ballari, kitoblari; NAMES — faqat ism va tadbirga kelgani; COUNT — faqat sonlar |
| `referral.leaderboard_size` | «Eng faol taklif qiluvchilar» jadvalida nechta o'rin ko'rinadi (0 — jadval yashirin) |
| `referral.leaderboard_rule` | ATTENDED — faqat tadbirga kelgan do'stlar sanaladi (tavsiya); REGISTERED — ro'yxatdan o'tganlarning hammasi |

Yutuqlar: do'sti birinchi tadbirga kelganda **🤗 Birinchi do'st**, 5 ta do'st kelganda
**📣 Targ'ibotchi** (**🏅 Yutuqlar** bo'limida o'zgartirasiz yoki yangisini qo'shasiz, mezon — «Taklif qilgan va
tadbirga kelgan do'stlar soni»).

### 🏁 Taklif tanlovlari («kim ko'p do'st olib kelsa — sovg'a»)

**Admin panel → 🎲 Sovg'a o'yinlari → 🏁 Taklif tanlovlari → + Yangi tanlov**. Masalan: «Oktabr oxirigacha klubga eng ko'p do'st olib
kelgan 3 kishiga sovg'a».

1. **Nomi, tavsifi, boshlanish va tugash vaqti.**
2. **Qoidalar** — qaysi do'stlar sanaladi:
   - ✅ **tadbirga kelgan do'stlar** (tavsiya: soxta akkauntlardan eng yaxshi himoya);
   - 👤 ro'yxatdan o'tgan do'stlar (tez, lekin jadvalni tekshirib turing);
   - ⭐ kamida N ball to'plagan do'stlar.
   Faqat tanlov davrida havola orqali qo'shilganlar sanaladi. «Kamida necha do'st» — bundan kam bo'lsa sovrin
   berilmaydi. Qatnashuvchilarni fakultet yoki kurs bo'yicha cheklash mumkin. Adminlar hech qachon qatnashmaydi.
3. **Sovrinlar** — har bir o'ringa alohida: **ball**, **Premium kunlar**, **promokod** («🎁 Sovg'alar»dagi
   sovg'adan) va/yoki **qo'lda beriladigan sovg'a** (masalan, kitob). Shartni bajargan hammaga qo'shimcha ball ham
   berish mumkin.
4. **A'zolar nimani ko'radi**: jadval (yoki faqat o'z natijasi), jadvaldagi do'stlar soni, ismlar (to'liq,
   «Aziza K.» yoki yashirin — «Ishtirokchi»), har kimning o'z o'rni, sovrinlar (yoki sir), **oxirgi soatlarda
   jadvalni yashirish** (intriga uchun).
5. **Xabarlar**: boshlanganda hammaga e'lon (sovrinlar va havola tugmasi bilan), tugashidan N soat oldin har bir
   ishtirokchiga o'rni va kerakli do'stlar soni bilan eslatma, natijalarni hammaga e'lon qilish va kanalga post.

**📢 E'lon qilish** tugmasi bilan tanlov boshlanadi (boshlanish vaqti kelganda a'zolarga xabar boradi). Tanlov
boshlangach adolat uchun shartlar va sovrinlar **qulflanadi**; nomi, ko'rinish sozlamalari va tugash vaqtini
o'zgartirish mumkin.

Tanlov davomida **Batafsil** → jadval (adminlar to'liq ismlarni ko'radi) → **Do'stlari** — har bir ishtirokchi olib
kelgan do'stlar ro'yxati (telefoni, tadbirga kelgani, ballari, sanaladimi). Shubhali bo'lsa — **Chiqarish** (sababi
bilan) yoki shubhali akkauntlarni **👥 A'zolar** da bloklang — ular jadvaldan o'zi chiqadi.

Tugash vaqti kelganda tanlov **o'zi yakunlanadi**: g'oliblar aniqlanadi, ball / Premium / promokod avtomatik
beriladi, g'oliblarga 🎉 tabrik boradi, natijalar e'lon qilinadi. Qo'lda beriladigan sovg'ani topshirgach —
**✅ Topshirildi deb belgilash**. Kerak bo'lsa **🏁 Hozir yakunlash** yoki **Bekor qilish** (a'zolarga sababi bilan
xabar boradi).

Sahifa pastida — **barcha vaqt bo'yicha eng ko'p do'st olib kelganlar** (ro'yxatdan o'tgan va tadbirga kelgan
do'stlari soni bilan).

## 15. Tadbirlar: smenalar, qo'lda davomat, vaqtni o'zgartirish

- **Smenalar**: bir tadbir bir necha vaqtda o'tsa (masalan, 1-smena 10:00, 2-smena 14:00), tadbirga
  smenalar qo'shing. A'zo o'z smenasini tanlab ro'yxatdan o'tadi, davomat har smenada alohida ochiladi.
  Qaysi smenaga kelmasin — **ball bir marta** beriladi, tadbir testi ham **bir marta** ishlanadi.
- **Qo'lda davomat**: kodni skanerlay olmagan a'zoni admin sababini yozib qo'shadi. Oddiy admin
  qo'shgan yozuv **bosh administrator tasdiqlagandan** keyin ball beradi (tasdiqlash so'rovi botga
  tugmalar bilan keladi); bosh administrator qo'shsa — darhol.
- **Vaqt yoki joy o'zgarsa**: tadbirni tahrirlang — davomat oynasi tadbir bilan birga suriladi,
  ro'yxatdan o'tganlarga xabar o'zi boradi, eslatmalar va kanal postlari yangi vaqtga moslashadi.
- Tadbir vaqti tugagach **o'zi «o'tkazildi»** bo'ladi; 30 daqiqadan keyin qatnashchilardan ⭐ baho
  so'raladi. Baholar bo'yicha tadbirlar reytingi **📈 Tahlillar** da.
- Hisobot tasdiqlangach, uni rasmlari bilan kanalga **post** qilish mumkin.

## 16. Sertifikat dizaynlari

12 ta tayyor dizayn bor, ular navbat bilan almashadi (bir xil sertifikatlar ketma-ket chiqmaydi).
**🎓 Sertifikatlar → Dizaynlar** da hammasini ko'rasiz. Tadbir yoki test uchun **o'z fon rasmingizni**
yuklasangiz (tahrirlash sahifasida «Sertifikat dizayni»), ism, matn, sana va QR kod shu rasm ustiga
yoziladi.

- A'zo sertifikatini ilovada ko'radi; **yuklab olish**: Premiumsiz — har sertifikat uchun
  `certificates.free_downloads` marta (odatda 1), Premium — cheklovsiz.
- Premium a'zo dizaynni `certificates.design_changes` marta (odatda 3) almashtira oladi; QR kod va
  raqam o'zgarmaydi.
- Imzo egasi: **Sozlamalar** → `certificates.signer_title`, `certificates.signer_name`.

## 17. Majburiy obuna

Bot va ilovadan faqat klub kanaliga obuna bo'lganlar foydalanadi (adminlardan so'ralmaydi).
Obuna bo'lmagan kishiga kanal tugmasi va **«✅ Obuna bo'ldim»** chiqadi — bosgach, to'xtagan joyidan
davom etadi.

- Qaysi kanallar: **Sozlamalar** → `subscription.channels` (vergul bilan: `@kanal`, yopiq kanal uchun
  `-100…=https://t.me/+taklif`). Bo'sh bo'lsa — klub kanali.
- **Bot o'sha kanallarda administrator bo'lishi shart**, aks holda tekshiruv o'tkazib yuboriladi
  (a'zolar to'xtab qolmasligi uchun).
- O'chirish: `subscription.required` → o'chiq.

## 18. Yangi a'zolar: tanishuv va bepul Premium sinov

Ro'yxatdan o'tgach, bot qisqa tanishuv ko'rsatadi (davomat, testlar, kitoblar, ilova) va har bir
a'zoga **bir marta** `premium.trial_days` kunlik (odatda 7) bepul Premium beradi. Sinovdagi
imkoniyatlar ilovada 💎 belgisi bilan ko'rinadi. Tasdiqlash yoqilgan bo'lsa, sinov admin
tasdiqlagan kundan boshlanadi.

## 19. To'lovlar kanali, cheklar va premium emojilar

**To'lovlar kanali** — pulga oid hamma narsa sizning shaxsiy chatingizga emas, alohida yopiq kanalga
keladi:

| Nima | Qayerga |
|---|---|
| Karta cheklari (Premium, Stars, hissa) — ✅ / ❌ tugmalari bilan | 💳 To'lovlar kanali |
| A'zolarning «To'lov bo'yicha» savollari — **✍️ Javob yozish** tugmasi bilan (faqat bosh admin javob beradi) va javoblar («↪️ Javob») | 💳 To'lovlar kanali |
| Stars buyurtmasining har bir qadami: tasdiqlandi → «⭐ Yuborish topshirildi: …» → «⭐ Stars yuborildi» (yoki ↩️ qaytarildi) | 💳 To'lovlar kanali |
| Stars yuborish bo'yicha ko'rsatma va «✅ Stars yuborildi» tugmasi | «⭐ Stars yuborish» huquqli adminning shaxsiy chati |
| Har bir Telegram Stars to'lovi va qaytarilgan Stars | 💳 To'lovlar kanali |
| Har dushanba 09:00 — o'tgan haftaning moliyaviy xulosasi | 💳 To'lovlar kanali |
| 10:00 va 17:00 — 3 soatdan ko'p kutib qolgan cheklar haqida eslatma | 💳 To'lovlar kanali |

Sozlash (bir daqiqa, hech narsa yozish shart emas):

1. Telegram'da **yopiq kanal** yarating (masalan «Kitobxon — to'lovlar»). Kanalni ko'radigan
   adminlarni qo'shing.
2. Kanal → **Administratorlar** → **Administrator qo'shish** → botni toping → **Xabar joylash**
   huquqi yoqilgan bo'lsin → saqlang.
3. Bot sizga shaxsiy xabar yozadi: «Bu kanal nima uchun?» → **💳 To'lovlar kanali** ni bosing.
   Kanalga «✅ Sinov xabari» keladi — tayyor.

Holatni **Premium** sahifasidagi «💳 To'lovlar kanali» kartasida ko'rasiz (✅ ulangan yoki
muammo nimada), u yerda **🧪 Sinov xabari** tugmasi va oxirgi 30 kunlik moliyaviy xulosa bor.
Qo'lda sozlash ham mumkin: **Sozlamalar** → `payments.chat_id` (`@username` yoki `-100…`).

### «-100…» nima va uni qayerdan olamiz

Telegram har bir kanal va guruhga **ID raqami** beradi. Kanal va superguruhlarniki doim **-100** bilan
boshlanadi, masalan `-1001234567890`. «-100» — raqamning bir qismi, uni o'chirmang.

- **Ochiq kanal** (manzili bor): ID shart emas — `@kanal_nomi` yozasiz.
- **Yopiq kanal** (manzilsiz): ID kerak. Uni bilishning 2 yo'li:
  1. **Eng osoni:** botni kanalga **administrator** qiling — bot sizga o'zi «Bu kanal nima uchun?» deb yozadi,
     tugmani bosasiz va hammasi o'zi yoziladi (hech narsa terish shart emas).
  2. Kanaldagi istalgan postni **botga forward** qiling (siz admin bo'lishingiz kerak) — bot ID raqamini va
     ochiq manzilini aytadi. Shu raqamni Sozlamalarga yozasiz.

### Kanal ichida javob berish («Reply»)

To'lov bo'yicha hamma narsa **bitta kanalda**: cheklar, qarorlar, Stars buyurtmalari, Telegram Stars to'lovlari,
Premium sovg'alari (bitta yoki ommaviy), a'zolarning to'lov savollari, haftalik xulosa va eslatmalar.

Endi kanalning o'zida javob berasiz: kanaldagi xabarga **«Reply» (Javob)** qilib yozing —

- **to'lov savoliga** reply → javob a'zoga «Klub rahbariyatidan javob» bo'lib boradi (uning murojaatlar tarixiga
  ham yoziladi), a'zo «✍️ Yana yozish» bilan davom etadi;
- **chekka** yoki to'lov qatoriga reply → a'zoga «Klub rahbariyatidan — to'lovingiz bo'yicha: ⭐ 100 Telegram
  Stars, 23 000 so'm» sarlavhasi bilan boradi (masalan: «Chekning to'liq rasmini yuboring»), a'zo «✍️ Javob
  yozish» bilan javob qaytaradi — u ham shu kanalga keladi.

Yuborilgach, xabaringizga 👍 reaksiya qo'yiladi (reaksiyalar o'chiq bo'lsa — «✅ A'zoga yuborildi» qatori).
Kanalda faqat siz qo'shgan adminlar yoza oladi; to'lovlar **guruh** bo'lsa, faqat **bosh admin** va
**«💳 To'lov savollari»** huquqi borlarning replylari a'zoga boradi. Kanalda javob kim nomidan yozilgani
(kanal imzosi yoki «✍️ Javob yozish»ni bosgan admin) panelda va boshqa nusxalarda ko'rinadi. «✍️ Javob yozish» tugmasi ham ishlaydi — javobni bot chatida yozasiz.
Botni kanaldan chiqarsangiz, bot darhol ogohlantiradi va cheklar vaqtincha botda keladi —
hech narsa yo'qolmaydi.

**Takroriy chek**: a'zo (yoki boshqa kishi) avval yuborilgan chek faylini qayta yuborsa, chek ostida
«⚠️ Diqqat: bu chek avval ham yuborilgan — sana, kim, summa» deb yoziladi, admin paneldagi ro'yxatda
esa «⚠️ takroriy chek» belgisi chiqadi. Bunday chekni bank ilovasi bilan albatta solishtiring.

Chek kelganda: **✅ Tasdiqlash** yoki **❌ Rad etish** → tayyor sabablardan birini tanlaysiz
(«Chek o'qilmayapti yoki to'liq emas», «Summa tarif narxiga mos emas», «To'lov kartaga kelib
tushmagan») yoki **✍️ Boshqa sabab** ni yozasiz. Adashib bosilgan qarorni **48 soat ichida**
**↩️ Qaytarish** bilan bekor qilasiz. Kanal sozlanmagan bo'lsa, cheklar bosh
administratorlarga botda keladi. Hissa (donat) uchun chek so'ralmaydi.

**Premium emojilar** — bot xabarlaridagi oddiy emojilarni Telegram premium (animatsion) emojilariga
almashtirish. Masalan, xabarda «Assalomu alaykum ❤️» bo'lsa, ❤️ o'rnida siz oldindan yuklagan premium yurakcha
turadi — barcha xabarlarda (e'lonlar, eslatmalar, tabriklar) o'zi almashadi:

1. Botga `/emoji` yozing (yoki premium emojili xabarni shunchaki yuboring — bot «saqlaymi?» deb so'raydi).
2. Premium emojili xabar yuboring: bot har bir premium emojini o'zining oddiy «egizagi» o'rniga eslab qoladi.
   Boshqa oddiy emojiga bog'lamoqchi bo'lsangiz — juftlab yozing: `❤️ = <premium emoji>`.
3. **🧪 Tekshirish** — Telegram premium emojini qabul qilyaptimi, aniq javob.
4. `/tayyor` — tugatish.

Emojilarni Premium'i bor **istalgan admin** kiritadi («A'zolarga xabar yuborish» yoki «Tizim sozlamalari»
huquqi bilan) — bosh admin bo'lishi shart emas. Ro'yxatni ko'rish, o'chirish va namuna — **📢 Xabarlar**
sahifasi pastidagi «✨ Premium emojilar» bo'limida.

> ⚠️ **Telegram qoidasi:** bot premium emojini faqat **bot egasining** (botni @BotFather'da yaratgan
> akkauntning) Telegram Premium'i bo'lsa ishlata oladi. Emojini kiritgan adminning Premium'i hisobga olinmaydi.
> Bo'lmasa, bot buni sezib, xabarni oddiy emoji bilan yuboradi — hech narsa buzilmaydi. Yechim va batafsil —
> **30-bo'lim**.

## 20. Testlar: fayldan yuklash, rasmli savollar, natijalar

**Savollar bazasi**: testga ko'p savol yuklang (500 tagacha) va **«Har bir a'zoga nechta savol»**ga son yozing —
har a'zoga bazadan shuncha tasodifiy savol, tasodifiy tartibda tushadi (ko'chirish qiyin bo'ladi). Qayta urinishda
avval ko'rmagan savollari beriladi. Son bazadagi savollardan oshmasligi kerak; a'zolar yechishni boshlagach, son
o'zgarmaydi. Bo'sh qoldirilsa — hamma hamma savolni yechadi.

**Fayldan yuklash** — test sahifasida **Fayldan yuklash (TXT, Word, PDF)**, 15 MB gacha:

```
1. «O'tkan kunlar» romani muallifi kim?
A) Cho'lpon
*B) Abdulla Qodiriy
C) Oybek
Izoh: Roman 1922–1925-yillarda yozilgan.
```

- To'g'ri javob: oldiga yoki oxiriga `*` (yoki `+`, `#`), yoki alohida `Javob: B` qatori; Word'da
  **qalin** yoki rang bilan belgilansa ham bo'ladi.
- `(2 ball)` — savolga 2 ball; `Izoh:` — testdan keyin ko'rinadigan izoh.
- Word yoki PDF'da savol tagidagi **rasm** o'sha savolga biriktiriladi. Rasmni qo'lda ham qo'shish
  mumkin.
- Hech narsa darhol saqlanmaydi: savollar tahrirlovchiga tushadi, ogohlantirishlarni o'qib,
  tekshirib, **Saqlash** ni bosasiz.

**Natijalar**: tadbirga bog'langan testda davomatdan o'tmagan a'zolar ham ro'yxatda turadi, lekin
**«davomatsiz»** belgisi bilan — sovrinli o'rin, bonus ball va sertifikat faqat davomatdan
o'tganlarga. Testni bir marta ishlash mumkin (smenalar bo'lsa ham).

**Promokodlarni tarqatish**: **🎁 Sovg'alar** → **🎟 Promokodlarni test g'oliblariga tarqatish**: davr
va testlarni tanlaysiz, avval reja ko'rsatiladi (1-o'rinlar birinchi, bir a'zoga bitta kod, oldin
olganlar chiqarib tashlanadi), keyin bitta tugma bilan tarqatiladi va g'oliblarga xabar boradi.

## 21. Kitoblar

- **Muqova**: kitob tahririda rasm yuklang (yoki havola). Ilova va kanal postlarida ko'rinadi.
- **O'qish muddati — ixtiyoriy.** Muddatni **bo'sh qoldirsangiz**, a'zo kitobni xohlagan vaqtida o'qiydi
  va o'qib tugatgani uchun ball oladi. **Muddat qo'ysangiz**, ball faqat **shu muddatgacha** o'qib
  tugatgan a'zoga beriladi; muddatdan keyin tugatgan a'zoning kitobi «o'qildi» deb tarixda qoladi, lekin
  ball berilmaydi.
- Tadbirga kitob biriktirilgan bo'lsa, tadbirga kelgan a'zo kitobni o'qigan hisoblanadi.

## 22. Yordam, /stop va tugmali xabarlar

- **Savol-javoblar**: botda **💬 Yordam → ❓ Savol-javoblar** va ilovada **Yordam** sahifasi —
  ball, tadbir, test, kitob, hujjat, Premium, hisob mavzulari bo'yicha. Topa olmasa — **✉️ Adminga
  yozish** (bloklangan yoki klubdan chiqqan a'zo ham yoza oladi).
- **/stop** — a'zo istalgan jarayonni (ro'yxatdan o'tish, to'lov, murojaat) to'xtatib, menyuga
  qaytadi.
- **📢 Xabarlar** (e'lon): matn ostiga **havola tugmalari** qo'shish mumkin — har qatorga bittadan:
  `Ro'yxatdan o'tish | https://havola`. **👀 Ko'rib chiqish** — a'zolar xabarni qanday ko'rishini va
  necha kishiga borishini ko'rasiz, **🧪 O'zimga sinov** — avval o'zingizga keladi. «Yuborish»
  faqat ko'rib chiqilgandan keyin ochiladi.

## 23. 🗂 Hujjatlar markazi

**Admin panel → 🗂 Hujjatlar va hisobotlar**: talabalar ro'yxati va faolligi, statistika (QR kodlar ilovasi bilan),
davomat, test natijalari, a'zolar, sertifikatlar, kitoblar, **to'lovlar va daromad**, **sovg'alar**, tadbir
hisoboti — **Excel, Word yoki PDF**da. Davr (odatda joriy o'quv yili), fakultet, kurs va guruh bo'yicha tanlanadi.
Shu sahifaning yuqorisida ikki tab: **🗂 Hujjatlar** (eksportlar) va **📄 Rasmiy hisobotlar** (ilgari alohida
«Hisobotlar» bo'limi bo'lgan rasmiy tadbir hisobotlari).

- **💳 To'lovlar va daromad** — davr ichida tasdiqlangan karta to'lovlari, Telegram Stars va hissalar, jami
  daromad xulosasi bilan (faqat haqiqatan kelib tushgan, tasdiqlangan to'lovlar). **🎁 Sovg'alar ro'yxati** —
  kimga qanday sovg'a (promokod, Premium) berilgani va holati.
- Kompyuterda — **📥** (yuklab olish); telefonda — **📨 Botga** (fayl bot chatingizga keladi).
- Har bir hujjat faqat tegishli huquqi bor adminga ko'rinadi.
- **Tartib hamma joyda bir xil**: fakultet (fakultetlar ro'yxatidagi tartibda) → kurs → guruh **raqami bo'yicha**
  (301, 1001, 5424, 5524 …) → familiya. «Guruhlar kesimida» jadvalida fakultet alohida ustunda turadi.
- **Statistik hisobot + QR**: ilovada faqat **eng faol 5 nafar** talabaning QR kodi (ball, keyin tadbir, test va
  kitoblar bo'yicha), o'rni bilan. **📈 Tahlillar** da ham «Guruhlar kesimida» jadvali shu tartibda.
- A'zo o'zi ham ilovada portfolio kartasidagi **Ma'lumotnoma (PDF / Word)** tugmasi bilan o'z
  faoliyati haqida ma'lumotnoma oladi (bot chatiga keladi).
- **Ma'lumotnoma** bitta sahifada: raqami, a'zo haqidagi matn, faoliyati, **«…kerakli joyga taqdim etish uchun
  berildi»**, **berilgan sana va vaqt** (masalan «13.10.2026, soat 14:20»), imzo, muhr va haqiqiyligini
  tekshirish uchun QR kod.
- **Imzo va muhr hamma hujjatda**: «Klub rahbari: ____ Ism Familiya» va klub muhri imzo ustiga o'zi bosiladi
  (PDF va Word'da rasm, Excel'da imzo qatori). Lavozim va ism — **⚙️ Sozlamalar → certificates**
  («Imzo egasining lavozimi», «…ismi familiyasi»; ism bo'sh bo'lsa — birinchi bosh admin). Muhrni o'chirish —
  `certificates.seal`. Bu sozlamalarni faqat bosh admin o'zgartiradi.

## 24. O'quv yillari va faol bo'lmagan a'zolar (o'zi ishlaydi)

- **Har yili 1-sentabr**: faol a'zolarning kursi bittaga oshadi (oxirgi kurs o'zgarmaydi),
  **«2027–2028 o'quv yili»** mavsumi boshlanadi va a'zolarga xabar boradi. Reyting va hisobotlar
  yillar bo'yicha aralashmaydi; a'zolar, ballar tarixi, kitoblar, sertifikatlar joyida qoladi.
  Sozlamalar: `academic.year_start` (boshlanish kuni), `academic.promote_courses`,
  `academic.auto_season`.
- **Uzoq vaqt kirmagan a'zo** (`membership.inactive_days`, odatda 365 kun): avval «👋 Sizni ancha
  vaqtdan beri ko'rmadik» eslatmasi va **✋ Men shu yerdaman** tugmasi; 7 kundan keyin hisob
  **«faol emas»** bo'ladi — xabarlar to'xtaydi, hech narsa o'chmaydi. Botga yoki ilovaga kirsa,
  **o'zi faollashadi**. Adminlarga tegilmaydi. `0` — o'chiq.
- **Eski yozuvlar** (yetkazilgan xabarlar, test signallari, eski bot holatlari) har kecha
  tozalanadi — baza yillar o'tib ham tez ishlaydi. Audit jurnali hech qachon o'chmaydi.

### Yangi o'quv yilida yana nimalar o'zi bo'ladi

- **Guruh raqami o'zgarmaydi**: 1-sentabrda faqat **kurs** oshadi, guruh raqami a'zo yozganicha qoladi.
  (Xohlasangiz, `academic.promote_groups` ni yoqib, «201» → «301» kabi avtomatik oshirishni qaytarish mumkin.)
- **Bitiruvchilar**: oxirgi kursdagi a'zolarga «🎓 Bitirdingizmi?» savoli boradi — «Ha, bitirdim» deganlar
  **bitiruvchi** bo'ladi: klubda qoladi (ballari, kitoblari, sertifikatlari joyida), lekin kurs bo'yicha
  hisobotlarga kirmaydi. Admin ham **👥 A'zolar** → a'zo → «🎓 Bitiruvchi» belgisi bilan qo'yishi mumkin.
  O'chirish: `academic.ask_graduates`.
- **📖 Yil yakuni** (`academic.summary_day`, odatda 20-iyun): har bir faol a'zoga o'quv yilidagi natijalari —
  o'qigan kitoblari, tadbirlari, testlari, ballari, yillik reytingdagi o'rni, sertifikatlari, yutuqlari va olib
  kelgan do'stlari 🎉 bilan yuboriladi. Bo'sh qoldirilsa — yuborilmaydi.

### Kundalik yordamchilar

- **🌅 Xayrli tong** (`admin.morning_digest`): har kuni soat 08:00 da bosh administratorlarga qisqa hisobot —
  kecha qo'shilgan a'zolar, tasdiq kutayotganlar, tekshirilmagan cheklar, javobsiz murojaatlar, tasdiq kutayotgan
  qo'lda davomat, ko'rib chiqilmagan a'zolar fikrlari, litsenziyasi 30 kun ichida tugaydigan ijarachilar, bugungi
  tadbirlar, bugun tugaydigan testlar va davom etayotgan tanlovlar.
- **🌙 Tungi tinchlik** (`notifications.quiet_hours`, odatda 22:00–08:00): bu vaqtda ommaviy xabarlar (e'lonlar,
  yangi kitob va tadbirlar, yutuqlar, haftalik xulosa) yuborilmaydi — ertalab boradi. Shaxsiy va shoshilinch
  xabarlar (davomat, to'lov, test natijasi) har doim darhol boradi.
- **⏰ Rejalashtirilgan e'lonlar**: **📢 Xabarlar** da «Yuborish vaqti»ni tanlang (90 kungacha oldin) — masalan,
  bayram tabrigini oldindan yozib qo'yasiz. Yuborilguncha «So'nggi e'lonlar» ro'yxatida **Bekor qilish** mumkin.

## 25. 🔍 Qidiruv

Admin panel tepasidagi qidiruv qatoriga yozing (masalan **«stiker»**, a'zo familiyasi, telefon,
KH-raqam, kitob, tadbir, test): a'zolar, kitoblar, tadbirlar, testlar, sovg'alar, panel bo'limlari,
sozlamalar va **bot buyruqlari** bitta ro'yxatda chiqadi. Natijani bosing — kerakli joy ochiladi
(sozlama bo'lsa, o'sha qatorga olib boradi). Har kim faqat ruxsati bor narsani ko'radi.

## 26. 🏢 Boshqa tashkilotlarga ijaraga berish (litsenziya)

Kitobxon Hub'ni boshqa institut, kollej yoki maktabga ijaraga berish mumkin. Har bir tashkilot
**o'z nusxasini** oladi: o'z serveri (Render), o'z bazasi, o'z boti, o'z bosh administratori —
**ma'lumotlari sizniki bilan ham, bir-biriniki bilan ham hech qachon aralashmaydi** (ular umuman boshqa
bazalarda turadi).

Hammasini **Admin panel → 🏢 Ijara (tashkilotlar)** sahifasida boshqarasiz (faqat sizda — bosh admin, va faqat
asosiy serveringizda; ijarachilar nusxasida bu sahifa ko'rinmaydi):

1. **🔑 Kalit yaratish** — bir marta. Bu sizning imzo kalitingiz: u bilan berilgan litsenziyani hech kim qalbaki
   qila olmaydi. Maxfiy qismi bazada shifrlangan holda turadi (`SECRET_KEY` ni o'zgartirmang). Avval
   `licence_tool` bilan kalit yaratgan bo'lsangiz — «Avval yaratilgan kalitim bor» orqali qo'yasiz.
2. **+ Yangi tashkilot** — nomi, mas'ul shaxs, telefon, Telegram, tarif (Kichik / O'rta / Katta / Kelishilgan —
   a'zolar chegarasi va narx o'zi to'ladi), to'lov davri (yillik/oylik), ularning server manzili va boti.
3. Tashkilot → **🔐 Kalit berish**: qachongacha va necha a'zogacha. Panel tayyor **3 qatorni** ko'rsatadi:
   ```
   LICENCE_REQUIRED=true
   LICENCE_PUBLIC_KEY=…
   LICENCE_KEY=…
   ```
   **📋 Nusxalash** → ularning Render xizmatida **Environment** ga qo'yasiz → **Save**.
4. **💵 To'lovlar** — har to'lovni yozib borasiz; sahifa tepasida **bu yilgi tushum**, faol va muddati tugayotgan
   tashkilotlar soni.
5. Muddatni uzaytirish — yangi kalit berish (eski kalitlar tarixda qoladi).

Yangi tashkilotni ulash qadamlari sahifaning pastida ham yozilgan: ular o'z botini @BotFather'da yaratadi; Render'da
alohida xizmat va alohida baza ochiladi; Environment'ga ularning `BOT_TOKEN`, `SUPER_ADMIN_TELEGRAM_IDS` va 3 ta
`LICENCE_…` qatori yoziladi.

- Litsenziya tugashiga **30 kun** qolganda: sizga «🌅 Xayrli tong» xabarida eslatma; ularning admin panelida ham
  ogohlantirish chiqadi.
- Muddat tugagach **7 kun** imtiyoz; keyin a'zolar uchun xizmat to'xtaydi («vaqtincha to'xtatilgan» xabari),
  xabarlar yuborilmaydi. **Ularning adminlari ishlashda davom etadi** va hamma hujjatlarni yuklab oladi. Yangi
  kalit qo'yilishi bilan hammasi joyidan davom etadi.
- A'zolar chegarasi to'lsa, yangi ro'yxatdan o'tish to'xtaydi.
- O'z klubingiz serverida litsenziya **kerak emas** (`LICENCE_REQUIRED` o'chiq).

**Narx taklifi** (bitta tashkilot uchun, server xarajati alohida):

| Tarif | A'zolar | Yillik | Oylik |
|---|---|---|---|
| Kichik (maktab, kollej) | 300 gacha | 3 000 000 so'm | 300 000 so'm |
| O'rta (institut) | 1 500 gacha | 6 000 000 so'm | 600 000 so'm |
| Katta (universitet) | cheklovsiz | 12 000 000 so'm | 1 200 000 so'm |

O'rnatish va sozlash bir martalik 1 500 000 so'm; birinchi oy sinov uchun bepul. Yillik to'lovda
2 oy chegirma (jadvaldagi yillik narx shuni hisobga olgan).

## 27. Bot buyruqlari

| Buyruq | Kim uchun | Nima qiladi |
|---|---|---|
| `/start` | hamma | Boshlash, ro'yxatdan o'tish, bosh menyu |
| `/menu` | a'zo | Bosh menyu |
| `/davomat` | a'zo | Tadbirda davomat (QR yoki 6 belgili kod) |
| `/pasport` | a'zo | Kitobxon pasporti |
| `/oqidim 25` | a'zo | Bugun o'qilgan betlarni kundalikka yozish (izoh bilan ham bo'ladi) |
| `/javonim` | a'zo | O'qiyotgan kitoblar, progress va 🔥 seriya |
| `/kartam` | a'zo | «Kitobxonlik kartam» rasmi |
| `/fikr` | a'zo | 💬 Iqtibos, fikr yoki klub haqida e'tirof yuborish («A'zolar fikrlari») |
| `/referal` (yoki `/taklif`) | a'zo | 🎁 Sizning foydangiz: taklif havolasi, do'stlar va ularning ballari |
| `/premium` | a'zo | Premium va klubni qo'llab-quvvatlash |
| `/portfolio` | a'zo | Kitobxonlik portfoliosi (PDF va Word) |
| `/help` | hamma | Yordam, savol-javoblar, adminga yozish |
| `/paysupport` | hamma | To'lov bo'yicha savol (bosh adminga) |
| `/terms` | hamma | To'lov shartlari |
| `/cancel` | hamma | Joriy amalni bekor qilish |
| `/stop` | hamma | Hamma jarayonni to'xtatib, menyuga qaytish |
| `/myid` | hamma | Telegram ID ni bilish |
| `/admin` | admin | Qisqa holat va admin panel havolasi |
| `/stiker` | xabar yoki sozlamalar huquqli admin | Stikerlarni saqlash (tugatish — `/tayyor`) |
| `/emoji` | xabar yoki sozlamalar huquqli admin | Premium emojilarni o'rgatish va 🧪 tekshirish (tugatish — `/tayyor`) |

Buyruqlar menyusini (chatdagi «/» yoki «Menu» tugmasi) bot **o'zi sozlaydi**: a'zolar faqat
a'zolar buyruqlarini ko'radi; admin qilingan odamda darhol `/admin` (va xabar yuborish huquqi
bo'lsa `/stiker`, `/emoji`) paydo bo'ladi, adminlikdan olinganda yo'qoladi. Kanal va guruhlarda
menyu chiqmaydi.

### 🤖 Bot profili (nom, tavsif, avatar)

**Sozlamalar** sahifasining yuqorisida **🤖 Bot profili** kartasi bor. @BotFather'ga kirish shart
emas — bot hammasini o'zi Telegram'ga yozadi:

- **Bot nomi** (bo'sh — @BotFather'dagi nom qoladi), **qisqa tavsif** (profil va ulashilgan
  havolada) va **to'liq tavsif** (botning bo'sh chatida, «Start» ustida). O'ngda a'zo ko'radigan
  ko'rinish (oldindan ko'rish). **Saqlash** — darhol Telegram'da yangilanadi.
- **🔄 Telegram'ga qayta yuborish** — nom, tavsif, buyruqlar menyusi va kanal huquqlarini qayta
  yozadi (masalan, kimdir @BotFather'da qo'lda o'zgartirib yuborgan bo'lsa).
- **🖼 Klub avatarini o'rnatish** — botning rasmi klub avatari bilan almashtiriladi. Botda rasm
  umuman bo'lmasa, bot buni ishga tushganda o'zi qiladi.

**Brend** (logotip, pechat, avatar) tizimga qo'yilgan: pechat sertifikatlarda imzo ustida (och
dizaynlarda ko'k siyoh, to'q dizaynlarda oltin), belgi sertifikat va hisobot tepasida, QR tekshirish
sahifasida, portfolio sarlavhasida, ilova va admin panel ikonkasida chiqadi. O'chirish:
**Sozlamalar** → `certificates.seal`, `certificates.logo`. To'liq to'plam (4K) —
`Kitobxon-Brend-4K.zip`; uni ishlab chiquvchi `node brand/tools/build.mjs` bilan qayta yasaydi.

- **Bot rasmi** — yuqoridagi **🖼 Klub avatarini o'rnatish** tugmasi.
- **Bot tavsif rasmi** (bo'sh chatdagi rasm) — faqat @BotFather orqali: `/mybots` → bot → **Edit Bot**
  → **Edit Description Picture** → `08_Banner/bot-tavsif-rasmi-640px.png`.
- **Stiker to'plami** — @Stickers botiga `/newpack` → nom → `10_Stikerlar/*-512px.png` fayllarini
  **fayl sifatida** yuboring → har biriga emoji. So'ng botga `/stiker` bilan saqlab qo'ying (kanal
  postlaridan keyin chiqadi).

Botni kanal yoki guruhga administrator qilib qo'shganingizda, Telegram kerakli huquqlarni (xabar
joylash, tahrirlash, o'chirish, taklif havolasi) **o'zi belgilab** ko'rsatadi — faqat «Saqlash»ni
bosasiz.

## 28. Kundalik ish — qisqa ro'yxat

- Har tadbirdan oldin: tadbir yaratilganini, kitob biriktirilganini va davomat oynasini tekshiring.
- Tadbirda: Davomat sahifasini ekranga chiqaring.
- Kelgan cheklarni (karta to'lovlari) bank ilovasi bilan solishtirib tasdiqlang. Stars buyurtmalarini
  «⭐ Stars yuborish» huquqli admin yuboradi — **📨 Murojaatlar → ⭐ Stars buyurtmalari** bo'limida «Kutilmoqda»
  bo'sh ekanini ko'rib turing.
- To'lovlar kanalidagi a'zo savollariga javob bering (ular faqat sizga keladi).
- Kanal posti haqida xabar kelsa — ko'zdan kechiring (javob bermasangiz ham o'zi chiqadi).
- Tiklash so'rovlari kelsa — ✅ yoki ❌.
- Haftada bir: **📨 Murojaatlar**, **⭐ baholar**, **📈 Tahlillar** («🔁 Faollik va qaytish»), **🛡 Ishonch
  markazi**, **📢 Xabarlar** (kanalda xato yo'qmi).
- Oyda bir: **Sozlamalar → 🩺 Tizim holati** (hammasi ✅ mi), bosh sahifadagi ogohlantirishlar.
- Oy boshida: **🗓 Davr hisoboti** → PDF → institut rahbariyatiga; **🎲 Sovg'a o'yinlari** — kodlar
  yetarlimi.

## 29. ⭐ Stars karta orqali — to'liq jarayon (kim nima qiladi)

**Maqsad:** Telegram Stars'i yo'q a'zo ham Stars bilan to'lay olsin. A'zo so'mda klub kartasiga
to'laydi, klub esa unga Telegram'da Stars sovg'a qiladi. Bu xizmat **«⭐ Telegram Stars orqali»** to'lov
usulining ichida turadi.

**Ishtirokchilar:**

| Kim | Vazifasi |
|---|---|
| A'zo | to'plamni tanlaydi, kartaga pul o'tkazadi, chek rasmini yuboradi |
| **Bosh admin** (siz) | chekni bank ilovasi bilan solishtirib **tasdiqlaydi yoki rad etadi**; a'zoning pulga oid savollariga javob beradi |
| **⭐ Stars yuboruvchi admin** | «⭐ Stars yuborish» (`STARS_SEND`) huquqi berilgan admin: tasdiqlangan buyurtma bo'yicha Stars'ni a'zoga **o'z Telegram'idan** yuboradi va «✅ Stars yuborildi» ni bosadi |
| 💳 To'lovlar kanali | **har bir qadam** shu yerga yoziladi — kim, qachon, nima qildi |

> Nega shunday: bosh adminda Telegram Premium yo'q, Stars'ni esa Telegram faqat **odam** sovg'a qila
> oladi (bot qila olmaydi). Shuning uchun Stars'ni Premium'i va Stars hamyoni bor ishonchli admin
> yuboradi, pulga oid qarorni esa faqat siz qabul qilasiz.

### Qadam-baqadam

**1. A'zo buyurtma beradi.**

- Ilovada: **💎 Premium** → tarif → **⭐ Telegram Stars** usuli → ichida **«⭐ Stars'ingiz yo'qmi?»** →
  to'plam (50 / 100 / 250 / 500 ⭐; narx so'mda, masalan 100 ⭐ = 25 000 so'm). Botda: **💎 Premium** →
  **💳 Bank kartasi orqali** → «⭐ N Stars — narx» tugmalari.
- Kartaga pul o'tkazadi va **chek rasmini (skrinshot)** botga yuboradi. Javob: «⏳ Chekingiz administratorga
  tekshirish uchun yuborildi».
- Shart: a'zoning Telegram profilida **username** bo'lishi kerak (Stars shu username'ga yuboriladi). Yo'q
  bo'lsa, ilova buni oldindan aytadi.

**2. Bosh admin tekshiradi** (💳 To'lovlar kanalida yoki admin panelda **💎 Premium → 💳 Karta orqali
to'lovlar**).

- Kanalga chek keladi: «🧾 ⭐ 100 Telegram Stars — 25 000 so'm, A'zo: …» va **✅ Tasdiqlash / ❌ Rad etish**
  tugmalari. Bu tugmalarni **faqat bosh admin** bosa oladi.
- Pul kartaga **haqiqatan tushganini** bank ilovasida ko'ring, keyin **✅ Tasdiqlash**.
- Kanalda chek ostiga yoziladi: «✅ Tasdiqlandi — <siz>, <vaqt>» va
  «⭐ Yuborish topshirildi: <Stars yuboruvchi admin> (ko'rsatma ularga shaxsiy xabarda)».
- A'zoga: «✅ To'lovingiz tasdiqlandi! ⭐ 100 Stars tez orada Telegram'da sizga sovg'a sifatida yuboriladi —
  tushishi bilan xabar beramiz.»
- Rad etsangiz: tayyor sabablardan biri yoki **✍️ Boshqa sabab** — a'zoga sabab bilan xabar boradi, kanalga
  «❌ Rad etildi — …» yoziladi.

**3. Stars yuboruvchi admin xabar oladi** (botda, shaxsiy):

> ✅ **Bosh admin tomonidan tasdiqlandi** — <siz>, <vaqt>
> **<A'zo ismi>** ga **⭐ 100 Stars** kerak (karta orqali to'langan: 25 000 so'm).
>
> ⭐ **Endi 100 Stars'ni yuboring** — Kimga: <ism>, Username: @…
> 1. fragment.com/stars/buy sahifasini oching (Telegram yoki TON hamyon bilan kiring).
> 2. «Recipient» maydoniga a'zoning username'ini yozing, miqdor — 100.
> 3. To'lovni tasdiqlang: Stars bir necha daqiqada a'zoning hisobiga tushadi.
> 4. So'ng **«✅ Stars yuborildi»** tugmasini bosing.
>
> Fragment ishlamasa: a'zo profilida ⋮ → 🎁 Sovg'a yuborish → ⭐ Stars.

**4. Admin Stars'ni yuboradi va «✅ Stars yuborildi» ni bosadi.**

- A'zoga: «⭐ 100 Stars sizga sovg'a qilindi! Ularni Telegram → Sozlamalar → Telegram Stars bo'limida
  ko'rasiz. Endi Premium'ni ham bir bosishda olishingiz mumkin.»
- Kanalga: «⭐ Stars yuborildi — Yubordi: <admin> · a'zoga xabar berildi».
- Tugmani faqat bir kishi bosadi: boshqasi bossa «allaqachon yuborilgan» deydi (ikki marta yuborilmaydi).
- Xuddi shu ishni admin panelda **📨 Murojaatlar → ⭐ Stars buyurtmalari** bo'limida qilish mumkin: «Kutilmoqda» va
  «Yuborilgan» ro'yxatlari, har buyurtmada a'zo, username, miqdor, summa va **✅ Yuborildi** tugmasi.

**5. Adashib tasdiqlangan bo'lsa** — 48 soat ichida **↩️ Qaytarish**. Stars yuboruvchi adminga darhol
«↩️ Stars buyurtmasi qaytarildi … Hozircha yubormang: bosh admin chekni qayta ko'rib chiqmoqda» xabari boradi,
kanalga ham yoziladi.

### Muhim qoidalar

- **Hech kim «⭐ Stars yuborish» huquqiga ega bo'lmasa**, buyurtma bosh adminlarning o'ziga keladi (ish to'xtab
  qolmaydi). Bu huquqni berish: **🛡 Adminlar** → admin → huquqlar → «To'lovlar» guruhi →
  **«Telegram Stars'ni a'zolarga yuborish»**.
- Stars yuboruvchi admin Stars'ni **o'z hisobidan** sotib oladi, a'zoning puli esa **klub kartasiga** tushgan.
  Uning xarajatini qanday qoplashni (masalan, haftada bir marta kanaldagi «⭐ Stars yuborildi» qatorlari bo'yicha)
  oldindan kelishib oling.
- A'zoning pulga oid savollari (`/paysupport` yoki «Adminga yozish → 💳 To'lov bo'yicha») ham to'lovlar
  kanaliga **«✍️ Javob yozish»** tugmasi bilan keladi va ularga **faqat bosh admin** javob beradi. Javob
  a'zoga «Klub rahbariyati» nomidan boradi, kanalga esa «↪️ Javob» bo'lib yoziladi — keyin hamma ko'rib turadi.
- To'lovlar kanali sozlanmagan bo'lsa, cheklar va savollar bosh adminlarga botda keladi.
- Narx: **⚙️ Sozlamalar** → `payments.star_price_uzs` (1 ⭐ narxi, odatda 250 so'm) va
  `payments.stars_packages` (to'plamlar). Bo'sh qoldirilsa — Stars sotilmaydi.

## 30. 🎨 Stikerlar va ✨ premium emojilar — qanday ishlaydi

### Kim qo'sha oladi

**Bosh admin** va **«A'zolarga xabar yuborish»** yoki **«Tizim sozlamalari»** huquqi bor adminlar. Shuning
uchun Telegram Premium'i bor admin (bosh admin emas) ham emojilarni bemalol kiritadi. Huquqi yo'q admin
stiker yuborsa, bot qaysi huquq kerakligini aytadi.

### Uch xil yo'l

1. **`/stiker`** — stikerlar rejimi: stikerlarni birma-bir yuborasiz (oddiy, animatsion, Premium). Bot har
   birining emojisidan kayfiyatini aniqlaydi: 🎉 — tabriklar uchun, 📚 — kitob postlari uchun, 👋 —
   salomlashish uchun. Tugatish — `/tayyor`.
2. **`/emoji`** — premium emojilar rejimi: premium emojili xabar yuborasiz, bot har birini oddiy «egizagi»
   o'rniga eslab qoladi (masalan, oddiy ❤️ o'rniga sizning animatsion yurakchangiz). Boshqa emojiga bog'lash —
   `✋ = <premium emoji>`. Rasm izohidagi emojilar ham o'qiladi. Shu rejimda stiker yuborsangiz ham saqlanadi.
   Tugatish — `/tayyor`.
3. **Hech qanday buyruqsiz** — admin botga shunchaki stiker yoki premium emojili xabar yuborsa, bot so'raydi:
   «🎨 Bu stikerni bot va kanal stikerlari ro'yxatiga qo'shaymi?» → **✅ Ha, saqlash / Yo'q**.

### Stikerlar qayerda chiqadi

G'alaba xabarlaridan (test o'rni, yutuq, sertifikat, sovg'a, Premium), yangi a'zoni kutib olishdan va kanal
postlaridan keyin. Odatda **yoqilgan** (`notifications.stickers`). Stikerlar uchun Telegram Premium **kerak emas** —
ular har doim ishlaydi.

### Premium emojilar uchun Telegram qoidasi (muhim!)

Telegram 2026-yil fevralidan beri shunday qoida qo'ygan: bot xabarlarida premium (custom) emoji faqat
**bot egasining** — botni @BotFather'da yaratgan akkauntning — Telegram Premium'i bo'lsa ishlaydi (yoki botda
Fragment'dan sotib olingan qo'shimcha username bo'lsa). Emojini kiritgan adminning Premium'i hisobga olinmaydi.
**Kanallarda** esa premium emoji faqat Fragment username bilan ishlaydi.

Shuning uchun bot egasida Premium bo'lmasa, Telegram premium emojini rad etadi. Bot buni o'zi sezadi:
xabarni **oddiy emoji bilan** yuboradi (hech narsa yo'qolmaydi), bir soatdan keyin yana urinadi. Kanal yoki
guruh rad etsa — faqat o'sha joyda 6 soat oddiy emoji ishlatiladi, shaxsiy xabarlar bunga bog'liq emas.

**Holatni bilish:** `/emoji` → **🧪 Tekshirish** (yoki admin panel → **📢 Xabarlar** → «✨ Premium emojilar» →
**🧪 Tekshirish**). Javob uch xil bo'ladi:

- ✅ «Telegram premium emojini qabul qilyapti» — hammasi ishlaydi;
- ⚠️ «Telegram premium emojini rad etdi» — sabab va yechim yoziladi;
- ℹ️ «hali tekshirilmagan».

**Yechim (bittasi yetarli):**

1. **Bot egasining akkauntiga Telegram Premium olish** — eng oson yo'l.
2. @BotFather → botingiz → **Bot Settings → Transfer Ownership**: botni Premium'i bor ishonchli adminga
   o'tkazish (u botning to'liq egasi bo'ladi — juda ehtiyot bo'ling).
3. Fragment'da botga qo'shimcha username sotib olish (qimmat, lekin kanallarda ham ishlaydi).

Emojilar saqlanib turadi: ruxsat paydo bo'lishi bilan bot ularni **o'zi** ishlata boshlaydi.

## 31. 📈 Faollik va qaytish (tahlil)

**Admin panel → 📈 Tahlillar → 🔁 Faollik va qaytish** (huquq: «Statistika va tahlillarni ko'rish»). Oxirgi 6 oy, oyma-oy:

| Ustun | Ma'nosi |
|---|---|
| Faol | oy davomida ball olgan, kundalikka yozgan yoki tadbirga kelgan a'zolar |
| Yangi | shu oy birinchi marta faol bo'lganlar |
| Qaytgan | o'tgan oy ham faol bo'lganlar |
| To'xtagan | o'tgan oy faol edi, bu oy yo'q |
| Saqlanish | o'tgan oy faollarning necha foizi bu oy ham faol |

Pastida — **oxirgi 30 kun**: missiyalar (olingan / bajarilgan / foiz), kundalik yuritgan a'zolar, o'qilgan
betlar, tugatilgan kitoblar, saqlangan iqtiboslar, «3 savol» javoblari. «To'xtagan» ko'payib ketsa —
missiya, tanlov yoki tadbir e'lon qilish vaqti.

## 32. 🛡 Ishonch markazi

**Admin panel → 🛡 Ishonch markazi** (huquq: «Audit jurnalini ko'rish»). Bu **ayblov emas** — qo'shimcha
tekshirish kerak bo'lishi mumkin bo'lgan holatlar ro'yxati (7, 30 yoki 90 kun):

| Bo'lim | Nima ko'rsatiladi |
|---|---|
| ⚡ Juda tez va juda yuqori test natijalari | ajratilgan vaqtning 25 % idan kam vaqtda 90 %+ ball |
| ✍️ Qo'lda ko'p o'zgartirilgan ballar | bir a'zoga 3+ marta yoki bitta admin tomonidan 15+ marta qo'lda ball |
| 📍 Davomat | «shubhali» davomatlar va bitta admin 20+ marta qo'lda tasdiqlagan holatlar |
| 📖 Kundalikdagi juda katta raqamlar | bir kunda 300+ bet |
| 🧾 Takroriy cheklar | aynan bir xil chek fayli bir necha marta yuborilgan |
| 🎓 Sertifikatni tekshirish | sertifikat ostidagi kod bo'yicha: haqiqiymi yoki bekor qilinganmi, kimga, qachon |

Har bo'limda «toza» yoki «N ta» belgisi turadi. Ro'yxatdagi ism bilan ishlang: a'zo bilan gaplashing, chekni
bankda ko'ring, kerak bo'lsa ballni tuzating (u ham audit jurnaliga yoziladi).

## 33. ⏰ O'zi ishlaydigan ishlar (avtomatik)

Fon xizmati (worker) har daqiqada tekshiradi. Siz hech narsa qilmaysiz — faqat sozlamalarda yoqib/o'chirasiz.

| Ish | Qachon | Nima qiladi |
|---|---|---|
| Testlarni yopish | har daqiqa | vaqti tugagan testlarni yopadi, o'rinlar va sertifikatlarni hisoblaydi |
| Tadbir eslatmalari | tadbirdan 1 kun va 3 soat oldin | ro'yxatdan o'tganlarga va kanalga eslatma |
| Test boshlandi / tugayapti | test ochilganda va tugashidan oldin | a'zolarga xabar |
| O'qish eslatmalari | kitob muddatining yarmi va oxiri | kitobdan iqtibos bilan eslatma |
| Kun iqtibosi | har kuni | iqtibos a'zolarga va kanalga |
| Yutuqlar | doim | yetishilgan nishonlarni beradi (hech biri tushib qolmasin) |
| Oy peshqadamlari | oy boshida | oyning eng faollariga nishon va sertifikat (10:00 dan) |
| Davomatni ochish | tadbir vaqtida | davomat oynasini ochadi va a'zolarga xabar |
| Tadbirga baho | tadbirdan 30 daqiqa keyin | qatnashganlardan ⭐ baho so'raydi |
| Haftalik xulosa | dushanba | Premium a'zolarga shaxsiy xulosa |
| Sovg'a o'yinlari | belgilangan vaqtda | g'oliblarni aniqlaydi, kod yuboradi, e'lon qiladi |
| Kanal postlari | belgilangan vaqtda | adminlarga 5 daqiqa oldin ko'rsatib, kanalga joylaydi |
| Premium eslatmasi | tugashidan 1 kun oldin | bitta muloyim eslatma |
| Chiqib ketganlar ma'lumotini o'chirish | 30 kundan keyin | shaxsiy ma'lumotlarni o'chiradi |
| Tadbirni yakunlash | tadbir tugagach | «o'tkazildi» qiladi |
| Yangi o'quv yili | `academic.year_start` | kurs/guruhni oshiradi, mavsum ochadi |
| Faol bo'lmaganlar | har kuni 11:00 | uzoq kirmaganlarga eslatma, keyin «faol emas» |
| Eski yozuvlarni tozalash | har kecha 04:00 | eski xabarlar va signallar |
| Taklif tanlovlari | boshlanish va tugash vaqtida | e'lon, eslatma, g'oliblar va sovrinlar |
| Yil yakuni | `academic.summary_day`, 10:00 | har faol a'zoga yillik natija va kitobxonlik izi |
| Xayrli tong | har kuni 08:00 | bosh adminlarga qisqa hisobot |
| To'lovlar xulosasi | dushanba 09:00 | o'tgan hafta tushumlari — to'lovlar kanaliga |
| Kutayotgan cheklar | 10:00 va 17:00 | 3 soatdan ko'p kutgan cheklar haqida eslatma |
| **Shaxsiy missiyalar** | doim | missiya natijasini yangilaydi, bajarilganga ball, vaqti tugaganini yopadi |

Tungi tinchlik vaqtida (`notifications.quiet_hours`, odatda 22:00–08:00) ommaviy xabarlar ertalabgacha kutadi.

## 34. ❓ Savol-javob va muammolar

| Muammo | Sabab va yechim |
|---|---|
| Taklif havolasi «yopiq» yoki chiqmayapti | Endi bunday bo'lmaydi: bot o'z nomini Telegram'dan o'zi oladi. Agar baribir chiqmasa — botni qayta ishga tushiring (Render → Manual Deploy) yoki **Sozlamalar → 🤖 Bot profili → 🔄 Telegram'ga qayta yuborish** |
| Premium emoji chiqmayapti, oddiy emoji ketyapti | 30-bo'lim: bot **egasida** Telegram Premium bo'lishi kerak. `/emoji` → 🧪 Tekshirish |
| Stiker chiqmayapti | `/stiker` bilan kamida bitta stiker saqlang; **Sozlamalar** → `notifications.stickers` yoqilganini tekshiring |
| Stars buyurtmasi hech kimga kelmadi | «⭐ Stars yuborish» huquqi kimda borligini **🛡 Adminlar** da tekshiring; hech kimda bo'lmasa, buyurtma bosh adminga keladi. U admin botga `/start` bosgan bo'lishi kerak |
| «✅ Stars yuborildi» bosilmayapti | tugmani faqat bosh admin va «⭐ Stars yuborish» huquqli admin bosadi; buyurtma qaytarilgan (↩️) bo'lsa — yubormang |
| A'zo Stars uchun username'i yo'q | Telegram → Sozlamalar → Username yaratishi kerak, keyin qayta buyurtma beradi |
| Chek kanalga kelmadi | **💎 Premium** sahifasidagi «💳 To'lovlar kanali» kartasi: ✅ ulanganmi; bot kanalda admin va «Xabar joylash» huquqi bormi; **🧪 Sinov xabari** |
| Menyuda yangi tugma ko'rinmayapti | a'zo `/start` yoki `/menu` bossin — menyu yangilanadi |
| `/oqidim` «o'qiyotgan kitob yo'q» deydi | avval ilovada **📖 Javonim** ga kitob qo'shib, «O'qiyapman» qiling (yoki klub kitobida «O'qishni boshladim») |
| Missiya progressi o'zgarmayapti | missiya **olingandan keyingi** ishlar sanaladi; o'z kitobi kundalikda o'qilgan bo'lishi kerak; natija bir necha daqiqada yangilanadi |
| Bo'lim a'zolarga ko'rinmayapti | **🧩 Imkoniyatlar** da «O'chiq» emasligini tekshiring («🎁 Sizning foydangiz» doim ochiq) |
| Kanalga post chiqmadi | **📢 Xabarlar** bo'limidagi xato sababi; ko'pincha bot kanalda admin emas |
| Biror narsa umuman ishlamayapti | **Sozlamalar → 🩺 Tizim holati** — qizil qator nimani aytsa, shuni tuzating; bo'lmasa menga yozing |

> Xavfsizlik: hech kimga (menga ham) **bot tokeni**, **SECRET_KEY** yoki **DATABASE_URL** ni yubormang. Ular
> faqat Render'ning «Environment» bo'limida turadi.

## 35. 🆕 So'nggi o'zgarishlar

### Oktabr, 4-yangilanish

**🔧 Murojaatlar tuzatildi (muhim).** Bitta a'zo ham **umumiy**, ham **to'lov** savolini yuborsa, ilgari ular
aralashib ketardi — to'lovga berilgan javob umumiyda ham ko'rinardi, kim javob bergani ham almashib qolardi.
Endi umumiy va to'lov murojaati **butunlay alohida**: har birining o'z holati, o'z nusxalari va «kim javob
berdi»si bor. Admin paneldagi **📨 Murojaatlar** faqat **umumiy** savollarni ko'rsatadi; to'lov savollari
to'lovlar kanalida hal qilinadi va faqat «💳 To'lov savollari» huquqi borlarga ko'rinadi.

**🧹 Admin menyu soddalashtirildi** (funksiyalar yo'qolmadi — birlashtirildi):
- **💬 Iqtiboslar** → **💬 A'zolar fikrlari** ichidagi «📖 Kitob iqtiboslari» bo'limi (tab).
- **📄 Hisobotlar** → **🗂 Hujjatlar va hisobotlar** ichidagi «📄 Rasmiy hisobotlar» tab.
- **🏁 Taklif tanlovlari** → **🎲 Sovg'a o'yinlari** ichidagi tab.
- **🏛 Fakultetlar** → **⚙️ Sozlamalar** ichidagi «🏛 Fakultetlar» tab.

**📝 Test tuzish osonlashdi.** Testni ochganda endi darhol **savollar qismi** chiqadi; sana, vaqt va
sertifikat dizayni «⚙️ Test sozlamalari» degan yig'iladigan bo'limga olindi (kerak bo'lsa bosib ochasiz).

**🎨 Stikerlar va ✨ emojilarni botda ko'rish va o'chirish.** Endi `/stiker` → «📋 Saqlangan stikerlar»
bilan har bir stikerni ko'rib, keraksizini «🗑 O'chirish» qilasiz; `/emoji` → «📋 Bittalab o'chirish» bilan
har bir premium emojini alohida o'chirasiz (ilgari faqat admin panelda edi).

**📊 To'lov va sovg'a hisobotlari.** **🗂 Hujjatlar va hisobotlar**ga ikkita yangi hujjat qo'shildi:
**«To'lovlar va daromad»** (davr ichida tasdiqlangan karta to'lovlari, Telegram Stars, hissalar — jami
xulosa bilan) va **«Sovg'alar ro'yxati»** (kimga qanday sovg'a berilgani) — Excel, Word yoki PDF.

### Oktabr, 3-yangilanish

**🧪 Savollar bazasi** — testga istalgancha savol yuklaysiz (500 tagacha), **«Har bir a'zoga nechta savol»**
maydoniga son yozasiz (masalan 20): har a'zoga bazadan tasodifiy 20 ta savol, tasodifiy tartibda tushadi. Qayta
urinishda avval ko'rmagan savollari beriladi. Bo'sh qoldirsangiz — hamma hamma savolni yechadi (20-bo'lim).

**🎯 O'z missiyam** — a'zo ilovada o'zi uchun maqsad qo'yadi (masalan «7 kunda 150 bet»). Kichik ball (2) beriladi,
bir oyda ko'pi bilan 4 tasiga; juda oson maqsadga ball yo'q. Adminlar **🎯 Missiyalar** sahifasida
ko'radi (pastdagi «🙋 A'zolarning o'z missiyalari»), yaxshisini bir bosishda klub missiyasiga aylantirasiz (D.5).

**💬 Iqtiboslar sandig'i** — saqlashdan oldin a'zo tanlaydi: **🔒 Faqat o'zim uchun** yoki **🌍 Umumiy**. Umumiylari
admin panelda **💬 A'zolar fikrlari**ga keladi (filtr «📦 Iqtiboslar sandig'idan») — tasdiqlaysiz, yashirasiz,
kanalga uzatasiz (D.4).

**📚 Javonim** — ilovaning pastki menyusida «Kitoblar» o'rniga **«Javonim»**: a'zoning o'z javoni, ichida
«🏛 Klub kitoblari» ham bor. Javon o'chiq bo'lsa — eskicha «Kitoblar».

**⭐ Stars sotib olish** — «💳 Bank kartasi orqali» bosilganda tariflar ostida bitta **⭐ Stars sotib olish**
tugmasi; bosilsa Stars miqdorlari va narxlari chiqadi.

**💳 To'lov savollariga kanalning o'zida javob** — bosh admin va yangi **«💳 To'lov savollari»** huquqi berilgan
adminlar javob beradi (kanalda «Reply» yoki «✍️ Javob yozish»; guruh bo'lsa ham). Admin panelda tayyor to'plam ham
qo'shildi: **💳 To'lov savollari** (19-bo'lim).

**🔄 Hamma adminning nusxasi bir xil** — murojaat har bir adminda «⏳ javob kutmoqda» deb turadi; kimdir javob
bersa, **hamma nusxada** «✅ Javob berildi — Ism, vaqt» bo'ladi (bosh adminnikida ham). Xuddi shunday: cheklar,
Stars buyurtmalari, a'zolar fikrlari, qo'lda davomat so'rovlari, a'zolikni tiklash, kanal postlari ko'rigi.

**📄 Batafsil** — uzun murojaat endi to'liq keladi; **📄 Batafsil** tugmasi butun yozishmani ko'rsatadi
(a'zoning savollari, javoblar, kim javob bergani). **🔒 Yopish** ham botning o'zida (4-bo'lim).

**🛰 Nazorat markazi** (faqat bosh admin) — nima kutmoqda va qancha vaqtdan beri, bot xabarlari navbati,
so'nggi harakatlar, shu hafta kim nechta javob berdi. Istalgan qatorni bosib o'sha joyda o'zingiz hal qilasiz.

**📝 Matnlar** — botning har bir xabari, a'zolarga boradigan bildirishnomalar va kanal postlari iboralari endi
sizning qo'lingizda: o'zgartirasiz, **5 tagacha variant** yozasiz (bot navbatma-navbat yuboradi, takrorlanmaydi),
oldindan ko'rasiz, asliga qaytarasiz. Ko'p xabarda 5 tadan tayyor variant bor. Yangi huquq: **«📝 Matnlar»** (12-bo'lim).

**🔏 Muhr va imzo** — barcha hujjatlarda (ma'lumotnoma, ro'yxatlar, statistika, portfolio, hisobotlar,
sertifikat) **«Klub rahbari: ____ Ism Familiya»** va muhr imzo ustiga o'zi bosiladi. Ism Sozlamalardagi
«Imzo egasining ismi familiyasi»dan, bo'sh bo'lsa — birinchi bosh admin (siz).

**📄 Ma'lumotnoma** — bitta sahifada: raqami, matn, **«…kerakli joyga taqdim etish uchun berildi»**, **berilgan
sana va vaqt**, imzo, muhr va QR kod (23-bo'lim).

**🛡 Xavfsizlik** — pul, kanallar, imzo-muhr va klub nomiga oid sozlamalarni **faqat bosh admin** o'zgartiradi
(Sozlamalarda «🔒 faqat bosh admin» belgisi); ularning har bir o'zgarishi, adminlarga huquq berish/olish haqida
sizga darhol xabar keladi. Admin panelga kompyuterdan kirilsa — o'sha adminga xabar va **«🔒 Barcha seanslarni
yopish»** tugmasi. A'zoga bir kunda 6 tadan ortiq ommaviy xabar bormaydi (spam deb bloklanmaslik uchun).

**Siz qilishingiz kerak bo'lgan ishlar (3-yangilanish):**

1. **⚙️ Sozlamalar → «certificates»**: «Imzo egasining ismi familiyasi»ni tekshiring (bo'sh bo'lsa — sizning ismingiz yoziladi).
2. **🛡 Adminlar**: to'lov savollariga javob beradigan adminlarga **«💳 To'lov savollari»** huquqini bering.
   Matnlarni o'zgartiradigan ishonchli adminga — **«📝 Matnlar»** huquqi.
3. **📝 Matnlar**ni bir ko'rib chiqing: yoqmagan xabarni o'zingizcha yozing.
4. Testlarda savollar bazasidan foydalanmoqchi bo'lsangiz — testni ochib «Har bir a'zoga nechta savol»ni yozing.

### Oktabr, 2-yangilanish

**💬 A'zolar fikrlari (yangi bo'lim)** — a'zolar iqtibos, o'z fikri, kitob va tadbir taassuroti, klub haqida
e'tirof yuboradi (ilovada yoki `/fikr`). Umumiy lenta, ❤️, 6 xil kartochka dizayni, kitob tugaganda va tadbirdan
keyin o'zi so'raydi. Admin panelda **💬 A'zolar fikrlari**: tasdiqlash, ⭐ tanlash, yashirish, tuzatish va istalgan
joyga uzatish — kanalga (hozir yoki rejali), a'zolarga kartochka bilan, kun iqtibosi, o'zingizga botda. Yangi
huquq «A'zolar fikrlari». Batafsil — D.9 va 9-bo'lim.

**📊 Statistika** — hamma joyda bir tartib: fakultet → kurs → guruh raqami (5424 dan keyin 5524); statistik
hisobot QR ilovasida faqat **eng faol 5 talaba**; «Tahlillar»da «Guruhlar kesimida» jadvali.

**🎓 1-sentabr** — endi faqat **kurs** oshadi, guruh raqami o'zgarmaydi.

**🎁 Ommaviy Premium sovg'a** — hammaga yoki fakultet/kurs/guruhga N kun (9-bo'lim).

**💳 To'lovlar kanali** — kanalda **«Reply»** qilib javob berish (savolga, chekka, to'lov qatoriga); kanaldagi
«✍️ Javob yozish» tugmasi ishlamay qolgan xato tuzatildi; Premium sovg'alari ham kanalga yoziladi (19-bo'lim).

**🏢 Ijara paneli** — tashkilotlar, kalit berish (3 qator), to'lovlar va eslatmalar (26-bo'lim).

**🔐 Sertifikat kodi** — `…/v` sahifasida kodni yozib tekshirish (6-bo'lim). **«-100…»** — kanal postini botga
forward qilsangiz, bot ID'ni aytadi (19-bo'lim).

### Oktabr, 1-yangilanish

**🎁 Sizning foydangiz (taklif) — doim ochiq**

- Bot menyusida yangi **🎁 Sizning foydangiz** tugmasi, `/referal` buyrug'i (eski `/taklif` ham ishlaydi),
  ilovada bosh sahifa va profilda kartochka.
- Havola endi hech qachon «yopiq» bo'lmaydi (bot o'z nomini Telegram'dan oladi).
- Taklif qilingan do'stlar ro'yxati va ularning **ballari** ham botda, ham ilovada.
- Imkoniyatlardan «Do'stlarni taklif qilish» olib tashlandi — o'chirib bo'lmaydi.

**⭐ Stars karta orqali — yangi jarayon**

- Xizmat endi «⭐ Telegram Stars orqali» usulining ichida («⭐ Stars'ingiz yo'qmi?»).
- Bosh admin tasdiqlaydi → «⭐ Stars yuborish» huquqli adminga buyurtma va ko'rsatma → u yuboradi va belgilaydi
  → a'zoga xabar.
- Har bir qadam to'lovlar kanaliga yoziladi.
- Yangi huquq **«⭐ Stars yuborish»** va admin panelda **📨 Murojaatlar** ichidagi **⭐ Stars buyurtmalari** bo'limi.
- To'lov savollariga faqat bosh admin javob beradi, javoblar kanalga ham yoziladi.

**🎨 Stikerlar va ✨ premium emojilar tuzatildi**

- Premium'i bor oddiy admin ham qo'sha oladi (xabar yuborish yoki sozlamalar huquqi bilan).
- Buyruqsiz yuborilgan stiker yoki emojini bot «saqlaymi?» deb so'raydi.
- Rasm izohidagi emojilar ham o'qiladi; **🧪 Tekshirish** Telegram nima deyayotganini aniq aytadi.
- Kanal rad etsa, faqat kanal to'xtaydi. Stikerlar odatda yoqilgan.
- Premium emoji ishlamasligining asl sababi topildi: bot **egasining** Premium'i (30-bo'lim).

**📚 Mening mutolaam (yangi)**

- Shaxsiy javon, mutolaa kundaligi va 🔥 seriya, «Kitobdan keyin 3 savol».
- Iqtiboslar sandig'i va chiroyli kartochkalar, **🪪 Kitobxonlik kartam**.
- Shaxsiy missiyalar (admin panelda **🎯 Missiyalar**).
- Botda `/oqidim`, `/javonim`, `/kartam`.

**🏛 Fakultetlar ligasi**: fakultetlar bellashuvi (o'rtacha ball, faollar ulushi, betlar, kitoblar).

**📈 Faollik va qaytish** tahlili va **🛡 Ishonch markazi** (shubhali holatlar ro'yxati va sertifikat tekshirish).

**📖 Kitobxonlik izi**: yil yakunida kundalik betlari, eng uzun seriya, iqtiboslar va missiyalar.

**Halollik himoyalari**

- Kundalikda kunlik bet chegarasi va faqat oxirgi 7 kun.
- Missiyalar faqat olingandan keyingi ishlarni sanaydi.
- O'z kitobi faqat kundalikda o'qilgan bo'lsa missiya va ball beradi.
- «3 savol» uchun ball oyiga cheklangan.
- Faqat e'lon qilingan klub iqtiboslari saqlanadi.

**Qilinmagan g'oyalar va sababi**

| G'oya | Sabab |
|---|---|
| Klublar, to'garaklar | klubning o'zi bitta jamoa. Ichida kichik guruhlar a'zolarni bo'lib yuboradi; fakultetlar ligasi va taklif tanlovlari shu ehtiyojni yopadi |
| O'qish sherigi (buddy) | begona odamlarni juftlash shaxsiy ma'lumot va xavfsizlik masalasini tug'diradi |
| Mentor | o'qituvchi resursi kerak; avval kerak bo'lsa, «Adminga yozish» orqali boshlash mumkin |
| Kitoblar xaritasi | xarita uchun tashqi xizmat va joylashuv ma'lumoti kerak; foydasi kichik |

Bularni keyinroq, kerak bo'lsa, alohida qo'shish mumkin.

### Siz qilishingiz kerak bo'lgan ishlar

0. **💬 A'zolar fikrlari**: yangi bo'limni ko'rib chiqing; xabar va murojaatlar bilan ishlaydigan adminlarga
   «A'zolar fikrlari» huquqini bering (to'plam «📨 Xabar va murojaatlar»da u bor). Ijaraga berishni boshlasangiz —
   **🏢 Ijara** → **🔑 Kalit yaratish**.
1. **🛡 Adminlar** → Premium'i bor ishonchli adminga **«⭐ Stars yuborish»** huquqini bering. U botga
   `/start` bosgan bo'lsin.
2. U admin bilan Stars xarajatini qanday qoplashni kelishib oling.
3. Premium emoji kerak bo'lsa: bot **egasining** akkauntiga Telegram Premium oling (yoki 30-bo'limdagi boshqa
   yo'l). So'ng `/emoji` → **🧪 Tekshirish**.
4. **🎯 Missiyalar** sahifasini ko'rib chiqing: tayyor 6 ta missiya bor, xohlasangiz o'zgartiring yoki yangisini
   qo'shing.
5. A'zolarga yangi imkoniyatlar haqida e'lon qiling: **🧩 Imkoniyatlar** da yangi bo'limni «Hammaga» qayta
   saqlab, «a'zolarga e'lon» belgisini qo'yasiz, yoki **📢 Xabarlar** dan o'zingiz yozasiz.

---

# Ma'lumotnoma jadvallari (dastur kodidan avtomatik olingan)

Bu jadvallar dasturning o'zidan chiqarilgan — shuning uchun to'liq va aniq. Sozlamalar **Admin panel →
⚙️ Sozlamalar** da, imkoniyatlar **🧩 Imkoniyatlar** da, huquqlar **🛡 Adminlar** da o'zgartiriladi.

## I. Imkoniyatlar (🧩)

| Imkoniyat | Odatiy holat | Nima beradi |
|---|---|---|
| 🪪 Kitobxon pasporti | Hammaga | rasmli a'zolik pasporti — yuklab olish va do'stlarga ulashish mumkin |
| 🎓 Sertifikatlar | Hammaga | g'oliblik sertifikatlari — QR kod orqali istalgan kishi haqiqiyligini tekshira oladi |
| 📄 Sertifikat PDF | 💎 Premium | sertifikatni PDF shaklida cheksiz yuklab olish va 12 ta dizayndan birini tanlash |
| 🏆 Reyting | Hammaga | haftalik klub reytingi |
| 🏆 To'liq reyting | 💎 Premium | oylik va umumiy reyting, fakultetim, guruhim va fakultetlar bellashuvi |
| 🏅 Yutuqlar | Hammaga | nishonlar va ularga yetish yo'li |
| 🎁 Sovg'alar | Hammaga | sovg'alar va promo-kodlar |
| 💬 Adminga yozish | Hammaga | klub rahbariyatiga savol va taklif yuborish |
| 📜 Kun iqtibosi | Hammaga | har kuni klub kitoblaridan tanlangan iqtibos |
| ⭐ Tadbirga baho | Hammaga | tadbirdan keyin unga baho berish va fikr qoldirish |
| 📊 Haftalik xulosa | 💎 Premium | har dushanba shaxsiy xulosa: haftalik ballar, reytingdagi o'rin va keyingi tadbirlar |
| 📈 Shaxsiy statistika | 💎 Premium | oylar bo'yicha ballaringiz, davomat foizi, test natijalari va reytingdagi o'sishingiz |
| 🗂 Kitobxonlik portfoliosi | 💎 Premium | barcha natija, sertifikat va yutuqlaringiz bitta chiroyli PDF hujjatda — rezyume va grantlar uchun |
| 📚 Javonim va mutolaa kundaligi | Hammaga | shaxsiy kitob javoni (o'qimoqchiman / o'qiyapman / o'qidim / keyinroq), kunlik betlar kundaligi, ketma-ket o'qish seriyasi va kitobdan keyin 3 savol |
| 💬 Iqtiboslar sandig'i | Hammaga | yoqqan iqtiboslarni saqlash, izoh yozish va chiroyli kartochka qilib do'stlarga ulashish |
| 🎯 Shaxsiy missiyalar | Hammaga | «7 kunda 100 bet», «5 kun ketma-ket o'qish» kabi kichik maqsadlar — bajarganga ball |
| 🪪 Kitobxonlik kartam | Hammaga | o'qigan kitoblar, betlar, seriya va yutuqlaringiz bitta chiroyli rasmda — ulashish uchun |
| 🏛 Fakultetlar ligasi | Hammaga | fakultetlar bellashuvi: o'rtacha ball, faol kitobxonlar ulushi, o'qilgan betlar va kitoblar |
| 💬 A'zolar fikrlari | Hammaga | kitobdan iqtiboslar, o'z fikrlaringiz, kitob va tadbir taassurotlari, klub haqidagi e'tiroflar — yuborish, boshqalarnikini o'qish, ❤️ bosish va chiroyli kartochka qilib ulashish |
| 💎 Premium obuna | O'chiq | Premium a'zolik: qo'shimcha imkoniyatlar, oltin pasport va klub rivojiga hissa |
| 💳 Karta orqali to'lov | O'chiq | Premiumni bank kartasiga o'tkazib, chekni yuborish orqali sotib olish |
| ❤️ Klubni qo'llab-quvvatlash | O'chiq | Telegram Stars orqali klub rivojiga hissa qo'shish |

## II. Admin huquqlari (🛡)

| Bo'lim | Huquq | Kod |
|---|---|---|
| A'zolar | A'zolar ro'yxatini va profillarini ko'rish | `USER_VIEW` |
| A'zolar | A'zolarning telefon raqamlarini ko'rish | `USER_CONTACT_VIEW` |
| A'zolar | A'zolarni tasdiqlash, bloklash va ma'lumotlarini tahrirlash | `USER_MANAGE` |
| Kitoblar | Kitoblarni (qoralamalar bilan) ko'rish | `BOOK_VIEW` |
| Kitoblar | Kitob va iqtibos qo'shish | `BOOK_CREATE` |
| Kitoblar | Kitob va iqtiboslarni tahrirlash, arxivlash | `BOOK_EDIT` |
| Kitoblar | Kitob va iqtiboslarni o'chirish | `BOOK_DELETE` |
| Tadbirlar | Tadbirlarni (qoralamalar bilan) ko'rish | `EVENT_VIEW` |
| Tadbirlar | Tadbir yaratish | `EVENT_CREATE` |
| Tadbirlar | Tadbirni tahrirlash va bekor qilish | `EVENT_EDIT` |
| Tadbirlar | Tadbirni o'chirish | `EVENT_DELETE` |
| Davomat | Davomatni ko'rish va eksport qilish | `ATTENDANCE_VIEW` |
| Davomat | Davomatni ochish/yopish, qo'lda tasdiqlash va tuzatish | `ATTENDANCE_MANAGE` |
| Testlar | Testlar va natijalarni ko'rish | `TEST_VIEW` |
| Testlar | Test yaratish | `TEST_CREATE` |
| Testlar | Testni tahrirlash | `TEST_EDIT` |
| Testlar | Testni o'chirish | `TEST_DELETE` |
| Testlar | Testni e'lon qilish va yopish | `TEST_PUBLISH` |
| Ballar | Ballar tarixini ko'rish | `SCORE_VIEW` |
| Ballar | Ballarni qo'lda o'zgartirish (sabab ko'rsatilishi shart) | `SCORE_MANAGE` |
| Hisobotlar | Hisobotlarni ko'rish va yuklab olish | `REPORT_VIEW` |
| Hisobotlar | Hisobot tayyorlash va tahrirlash | `REPORT_CREATE` |
| Hisobotlar | Hisobotni tasdiqlash va PDF yaratish | `REPORT_APPROVE` |
| Xabarlar | A'zolarga xabar yuborish | `NOTIFICATION_SEND` |
| Statistika | Statistika va tahlillarni ko'rish | `ANALYTICS_VIEW` |
| Sovg'alar | Sovg'alar, promo-kodlar va sertifikatlarni boshqarish | `REWARD_MANAGE` |
| Mavsumlar | Mavsumlar va kitobxonlik kampaniyalarini boshqarish | `SEASON_MANAGE` |
| Tizim | Tizim sozlamalari, ball qoidalari va fakultetlarni o'zgartirish | `SETTINGS_MANAGE` |
| Tizim | Audit jurnalini ko'rish | `AUDIT_LOG_VIEW` |
| Murojaatlar | A'zolar murojaatlarini o'qish va ularga javob berish | `SUPPORT_MANAGE` |
| To'lovlar | Telegram Stars'ni a'zolarga yuborish: bosh admin tasdiqlagan Stars buyurtmalari shu adminga keladi | `STARS_SEND` |
| A'zolar fikrlari | A'zolar fikrlari va iqtiboslarini ko'rib chiqish, kartochka qilish va kanal yoki a'zolarga ulashish | `COMMUNITY_MANAGE` |
| To'lovlar | To'lov bo'yicha savollarga javob berish — botda va to'lovlar kanalining o'zida («✍️ Javob yozish» yoki «Reply») | `PAYMENT_SUPPORT` |
| Tizim | «📝 Matnlar»: bot xabarlari, a'zolarga bildirishnomalar va kanal postlari matnini o'zgartirish | `TEXTS_MANAGE` |

## III. Sozlamalar (⚙️)

**`score.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `score.attendance_points` | 30 | Tadbirda tasdiqlangan qatnashuv uchun ball |
| `score.test_max_points` | 20 | Test uchun maksimal ball |
| `score.test_rank_bonus` | 10, 5, 3 | Test bo'yicha 1-, 2-, 3-o'rinlar uchun qo'shimcha ball |
| `score.book_completion_points` | 10 | Kitobni o'qib tugatgani uchun ball |
| `score.book_completion_requires_verification` | yoqiq | Kitob uchun ball faqat test yoki admin tasdig'idan keyin beriladi |

**`registration.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `registration.require_approval` | o'chiq | Yangi a'zolar admin tasdig'idan so'ng faollashadi |
| `registration.max_course` | 6 | Eng yuqori kurs raqami |

**`attendance.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `attendance.token_ttl_seconds` | 30 | QR/kodning amal qilish vaqti (soniya) |
| `attendance.rotation_seconds` | 10 | QR/kod qanchada yangilanadi (soniya) |
| `attendance.require_registration` | o'chiq | Davomat uchun tadbirga oldindan ro'yxatdan o'tish shart |

**`notifications.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `notifications.event_reminder_minutes` | 1440, 60 | Tadbirdan necha daqiqa oldin eslatma yuboriladi |
| `notifications.test_ending_minutes` | 60 | Test yopilishidan necha daqiqa oldin eslatiladi (0 = eslatilmaydi) |
| `notifications.reading_reminder_days` | 2 | Kitob muddati tugashidan necha kun oldin eslatiladi (0 = eslatilmaydi) |
| `notifications.quote_of_day_time` | 09:00 | Kun iqtibosi yuboriladigan vaqt |
| `notifications.quiet_hours` | 22:00-08:00 | Tungi tinchlik (SS:DD-SS:DD): shu vaqtda ommaviy xabarlar (e'lonlar, yangi kitob va tadbirlar, yutuqlar, haftalik xulosa) yuborilmaydi — ertalab boradi. Shaxsiy va shoshilinch xabarlar (davomat, to'lov, test natijasi) har doim boradi. Bo'sh — o'chiq |
| `notifications.stickers` | yoqiq | Tabrik va xush kelibsiz xabarlaridan keyin adminlar /stiker bilan saqlagan stikerlardan biri ham yuborilsin (stiker saqlanmagan bo'lsa — yuborilmaydi). 🎉 animatsiya baribir qoladi |
| `notifications.daily_limit` | 6 | Bitta a'zoga bir kunda ko'pi bilan nechta ommaviy xabar (yangiliklar, eslatmalar, kun iqtibosi, reyting...) boradi. Shaxsiy va muhim xabarlar (javoblar, to'lovlar, davomat, test natijasi) bunga kirmaydi. Ko'p xabar a'zolarni bezdiradi va Telegram botni spam deb bloklashi mumkin (0 — cheklovsiz) |

**`admin.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `admin.morning_digest` | yoqiq | Har kuni soat 08:00 da bosh administratorlarga qisqa hisobot: yangi a'zolar, tekshirilmagan cheklar, javobsiz murojaatlar, tasdiq kutayotgan davomat va bugungi tadbirlar |

**`org.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `org.organization_name` | Farg'ona jamoat salomatligi tibbiyot instituti | Tashkilot (universitet) nomi |
| `org.club_name` | Kitobxon Hub | Klub nomi |

**`certificates.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `certificates.test_winners` | yoqiq | Test g'oliblariga (1-3-o'rin) sertifikat avtomatik beriladi (tadbir testida — faqat davomatdan o'tganlarga) |
| `certificates.monthly_top` | yoqiq | Oy yakunida reytingdagi 1-3-o'rinlarga sertifikat beriladi |
| `certificates.signer_title` | Klub rahbari | Imzo egasining lavozimi — sertifikat, ma'lumotnoma, hisobot va ro'yxatlarda imzo oldida yoziladi |
| `certificates.signer_name` | — | Imzo egasining ismi familiyasi (masalan: Akmaljon Bahodirov). Bo'sh bo'lsa — bosh admin (klub rahbari) ismi o'zi yoziladi |
| `certificates.seal` | yoqiq | Klub pechati imzo ustiga avtomatik bosilsin: sertifikat, ma'lumotnoma, portfolio, tasdiqlangan hisobot va ro'yxatlarda (app/brand/seal.png) |
| `certificates.logo` | yoqiq | Sertifikat tepasida klub belgisi (app/brand/logo-mark.png bo'lsa) |
| `certificates.free_downloads` | 1 | Premiumsiz a'zo har bir sertifikatini necha marta bepul yuklab oladi (Premium — cheklovsiz) |
| `certificates.design_changes` | 3 | Premium a'zo bitta sertifikat dizaynini necha marta almashtira oladi |

**`payments.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `payments.card_number` | — | Klub kartasi raqami (Uzcard/Humo), masalan 8600 1234 5678 9012 |
| `payments.card_holder` | — | Karta egasining ismi (to'lovchi tekshirishi uchun) |
| `payments.chat_id` | — | To'lovlar kanali yoki guruhi: cheklar (✅/❌ tugmalari bilan), to'lov savollari, Stars to'lovlari va haftalik moliyaviy xulosa faqat shu yerga keladi. Qo'lda yozish shart emas: botni kanalga administrator qilsangiz, bot sizdan «💳 To'lovlar kanali» tugmasini bosishni so'raydi. Ochiq kanal — @username; yopiq kanal — -100 bilan boshlanadigan ID raqami (masalan -1001234567890). ID'ni bilish: kanaldagi istalgan postni botga forward qiling — bot raqamni aytadi (bo'sh — cheklar bosh administratorlarga botda) |
| `payments.stars_packages` | 50, 100, 250, 500 | Karta orqali sotiladigan Stars to'plamlari (bo'sh — sotilmaydi) |
| `payments.star_price_uzs` | 250 | 1 ta Stars narxi so'mda (Telegram'da sotib olish narxiga qarab; 0 — sotilmaydi) |

**`premium.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `premium.trial_days` | 7 | Har bir a'zoga bir marta bepul Premium sinov (kun; 0 — sinov yo'q) |

**`referral.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `referral.points` | 20 | Do'stini taklif qilgan a'zoga ball (do'sti birinchi tadbirda qatnashganda) |
| `referral.premium_days` | 7 | Do'stini taklif qilgan a'zoga Premium kunlar (0 — Premium berilmaydi) |
| `referral.monthly_limit` | 5 | Bir a'zo bir oyda nechta taklif uchun mukofot oladi (0 — cheklovsiz) |
| `referral.friend_details` | FULL | «Sizning foydangiz»da a'zo taklif qilgan do'stlari haqida nimani ko'radi: FULL — ismi, ballari, o'qigan kitoblari va tadbirlari; NAMES — faqat ismi va tadbirga kelgani; COUNT — faqat sonlar |
| `referral.leaderboard_size` | 10 | «Eng faol taklif qiluvchilar» ro'yxatida nechta a'zo ko'rinadi (0 — ro'yxat a'zolarga ko'rinmaydi) |
| `referral.leaderboard_rule` | ATTENDED | Umumiy taklif reytingida qaysi do'stlar sanaladi: ATTENDED — kamida bitta tadbirga kelganlar (soxta hisoblardan himoya); REGISTERED — ro'yxatdan o'tganlarning hammasi |

**`reading.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `reading.daily_page_limit` | 500 | Mutolaa kundaligi: bir kunda yozish mumkin bo'lgan eng ko'p bet (haddan tashqari sonlar va missiyalarni aldashdan himoya) |
| `reading.reflection_points` | 5 | «Kitobdan keyin 3 savol»ga javob yozgan a'zoga ball (har kitob uchun bir marta; 0 — ballsiz) |
| `reading.reflection_monthly_limit` | 4 | «3 savol» uchun bir oyda nechta kitobga ball beriladi (0 — cheklovsiz) |

**`missions.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `missions.personal_enabled` | yoqiq | A'zolar o'zlari uchun shaxsiy missiya yarata oladimi («🎯 O'z missiyam») |
| `missions.personal_points` | 2 | O'zi yaratgan missiyani bajargan a'zoga ball (juda oson maqsadlarga berilmaydi; 0 — ballsiz) |
| `missions.personal_monthly_limit` | 4 | Bir oyda nechta shaxsiy missiya uchun ball beriladi (0 — cheklovsiz) |

**`community.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `community.quote_box_default` | PERSONAL | Iqtiboslar sandig'iga yangi iqtibos saqlanayotganda oldindan tanlangan variant: PERSONAL — «🔒 Faqat o'zim uchun», COMMON — «🌍 Umumiy» (hammaga ko'rinadi; a'zo saqlashdan oldin o'zgartira oladi) |
| `community.quote_box_common` | yoqiq | A'zolar sandiqdagi iqtibosini «🌍 Umumiy» qila oladimi (o'chiq — sandiq faqat shaxsiy bo'ladi) |
| `community.auto_publish` | o'chiq | A'zolar yuborgan iqtibos va fikrlar admin tasdiqlamasdan umumiy lentada darhol chiqsinmi (o'chiq — avval admin ko'rib chiqadi) |
| `community.points` | 2 | Fikri yoki iqtibosi umumiy lentaga qabul qilingan a'zoga ball (har biriga bir marta; 0 — ball berilmaydi) |
| `community.monthly_points_limit` | 5 | Bir oyda nechta fikr uchun ball beriladi (0 — cheklovsiz) |
| `community.featured_points` | 5 | Fikri «⭐ Tanlangan» bo'lgan yoki kanalda e'lon qilingan a'zoga qo'shimcha ball (bir marta) |
| `community.daily_limit` | 5 | Bir a'zo bir kunda nechta fikr yubora oladi (spamdan himoya) |
| `community.ask_after_book` | yoqiq | Kitobni o'qib tugatgan a'zodan iqtibos yoki taassurot yozishni so'rash |
| `community.ask_after_event` | yoqiq | Tadbirga baho bergan a'zoni tadbir haqida taassurot yozishga taklif qilish |
| `community.notify_admins` | yoqiq | Yangi fikr kelganda «A'zolar fikrlari» huquqi bor adminlarga botda ✅ / ⭐ / 🙈 tugmalari bilan xabar berish |

**`academic.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `academic.promote_groups` | o'chiq | Yangi o'quv yilida guruh raqami ham kurs bilan birga oshirilsinmi (2-kursdagi «201» → «301»). Odatda o'chiq: 1-sentabrda faqat kurs oshadi, guruh raqami o'zgarmaydi |
| `academic.ask_graduates` | yoqiq | Yangi o'quv yilida oxirgi kursdagi a'zolardan «Bitirdingizmi?» deb so'raladi; «Ha» deganlar bitiruvchi (alumni) bo'ladi — klubda qoladi, lekin kurs bo'yicha hisobotlarga kirmaydi |
| `academic.summary_day` | 06-20 | «Yil yakuni»: shu kuni (OO-KK) har bir a'zoga o'quv yili davomidagi natijalari (kitoblar, tadbirlar, testlar, ballar, o'rni, do'stlari) yuboriladi. Bo'sh — yuborilmaydi |
| `academic.year_start` | 09-01 | O'quv yili boshlanadigan kun (OO-KK): shu kuni kurslar bittaga oshadi va yangi mavsum boshlanadi |
| `academic.promote_courses` | yoqiq | Yangi o'quv yilida faol a'zolarning kursi avtomatik bittaga oshirilsin (oxirgi kursdan oshmaydi) |
| `academic.auto_season` | yoqiq | Har o'quv yili uchun alohida mavsum (reyting va hisobotlar yillar bo'yicha aralashmaydi) |
| `academic.current_year` | 0 | Joriy o'quv yili boshlangan yil (avtomatik yoziladi; 0 — hali aniqlanmagan) |

**`membership.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `membership.inactive_days` | 365 | Shuncha kun botga ham, ilovaga ham kirmagan a'zo eslatmadan 7 kun keyin «faol emas» bo'ladi (ma'lumotlari saqlanadi, qaytsa o'zi tiklanadi; 0 — o'chiq) |

**`subscription.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `subscription.required` | yoqiq | Botdan va ilovadan foydalanish uchun kanal(lar)ga obuna majburiy (adminlardan so'ralmaydi; bot o'sha kanallarda administrator bo'lishi kerak, aks holda tekshiruv o'tkazib yuboriladi) |
| `subscription.channels` | — | Obuna bo'lish shart bo'lgan kanallar, vergul bilan: @kanal, https://t.me/kanal yoki yopiq kanal uchun -100…=https://t.me/+taklif (bo'sh — faqat klub kanali) |

**`channel.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `channel.enabled` | o'chiq | Bot klub kanaliga post joylaydi (avval botni kanalga admin qiling) |
| `channel.chat_id` | @FJSTIMutolaaxona | Kanal manzili: ochiq kanal — @username (masalan @FJSTIMutolaaxona); yopiq kanal — -100 bilan boshlanadigan ID raqami. ID'ni bilish: kanaldagi istalgan postni botga forward qiling — bot raqamni aytadi. Eng osoni: botni kanalga admin qiling — bot o'zi «Bu kanal nima uchun?» deb so'raydi |
| `channel.post_events` | yoqiq | Yangi tadbirlar va «ertaga ... o'qib kelamiz» eslatmalari |
| `channel.post_books` | yoqiq | Yangi kitoblar va «asarni tugatay deb qoldingizmi?» postlari |
| `channel.post_quotes` | yoqiq | Kun iqtibosi kanalga ham joylanadi |
| `channel.post_results` | yoqiq | Test g'oliblari, sovg'a o'yinlari va oy peshqadamlari |
| `channel.post_invites` | yoqiq | Har dushanba botga taklif posti |
| `channel.post_reports` | yoqiq | Tadbir hisoboti tasdiqlanganda rasmlari bilan «... davra suhbati bo'lib o'tdi» posti |
| `channel.more_photos_url` | — | Hisobot postidagi «📸 Boshqa rasmlar» tugmasi havolasi (masalan, rasmlar kanali: https://t.me/...) |
| `channel.stickers` | yoqiq | Avtomatik postlardan keyin saqlangan stikerlardan biri |
| `channel.review_minutes` | 5 | Avtomatik post kanalga chiqishidan oldin adminlarga ko'rsatiladi; shu daqiqalarda hech kim javob bermasa, o'zi joylanadi (0 — tekshiruvsiz) |

**`bot.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `bot.name` | — | Botning Telegram'dagi nomi (64 belgigacha). Bo'sh — @BotFather'dagi nom o'zgarmaydi |
| `bot.short_description` | 📚 Kitobxonlar klubi: kitoblar, tadbirlar, testlar, reyting va sertifikatlar — hammasi bitta botda. | Bot profilidagi va ulashilgan havoladagi qisqa matn (120 belgigacha) |
| `bot.description` | 📚 Kitobxon Hub — Farg'ona jamoat salomatligi tibbiyot instituti kitobxonlar klubining rasmiy boti.
«Yaxshi kitob — yaxshi kelajak»

✨ Bu yerda siz:
• klub kitoblarini o'qiysiz va muddatlarni kuzatasiz;
• tadbirlarda QR kod bilan davomat qilasiz;
• kitoblar bo'yicha testlar yechasiz;
• ball, reyting, yutuq va sertifikatlar olasiz;
• o'z Kitobxon pasportingizga ega bo'lasiz.

👇 Boshlash uchun «Start» tugmasini bosing. | Botning bo'sh chatida «Start» ustida ko'rinadigan matn (512 belgigacha) |
| `bot.menu_button` | 📱 Ilova | Chat pastidagi ilovani ochadigan tugma matni |

**`texts.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `texts.rotate` | yoqiq | Bir xil xabar qayta-qayta takrorlanmasin: bir nechta varianti bor xabarlar (salomlashish, eslatmalar, tabriklar, kanal postlari) navbatma-navbat yuboriladi. O'chirilsa — doim birinchi varianti |

**`ranking.*`**

| Sozlama | Odatiy qiymat | Ma'nosi |
|---|---|---|
| `ranking.public_name_format` | SHORT | Umumiy reytingda ism ko'rinishi: FULL = to'liq, SHORT = ism va familiyaning bosh harfi |

## IV. Bot buyruqlari menyusi (Telegram'dagi «Menu»)

| Buyruq | Kim ko'radi | Tavsif |
|---|---|---|
| `/start` | a'zo | 🏠 Bosh menyu |
| `/davomat` | a'zo | ✅ Tadbirda davomat qilish |
| `/pasport` | a'zo | 🪪 Kitobxon pasportim |
| `/oqidim` | a'zo | 📖 Bugun o'qiganimni yozish: /oqidim 25 |
| `/javonim` | a'zo | 📚 Javonim: o'qiyotgan kitoblarim va seriyam |
| `/kartam` | a'zo | 🪪 Kitobxonlik kartam (rasm) |
| `/fikr` | a'zo | 💬 Iqtibos, fikr yoki e'tirof yuborish |
| `/referal` | a'zo | 🎁 Sizning foydangiz: taklif havolasi va do'stlaringiz |
| `/premium` | a'zo | 💎 Premium va klubni qo'llab-quvvatlash |
| `/help` | a'zo | ❓ Yordam va adminga yozish |
| `/paysupport` | a'zo | 💳 To'lov bo'yicha yordam |
| `/stop` | a'zo | ⏹ Jarayonni to'xtatib, menyuga qaytish |
| `/admin` | admin | 🛠 Admin panel |
| `/stiker` | xabar yuborish huquqli admin | 🎨 Kanal postlari uchun stikerlar |
| `/emoji` | xabar yuborish huquqli admin | ✨ Premium emojilarni yuklash |
