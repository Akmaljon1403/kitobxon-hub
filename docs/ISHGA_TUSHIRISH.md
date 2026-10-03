# Kitobxon Hub'ni doimiy (24/7) ishga tushirish

Bu sahifa — bot [sinov serverida](TEST_HOSTING.md) ishlab turganidan keyin, uni klub a'zolariga
**haqiqiy foydalanish uchun** topshirishdan oldingi qadamlar. Har bir qadam 5–15 daqiqa oladi,
kompyuteringizga hech narsa o'rnatish shart emas — hammasi brauzerda.

> 💡 Qaysi qadam bajarilgan, qaysi biri qolganini istalgan vaqtda ko'rish mumkin:
> **Admin panel → Sozlamalar → 🩺 Tizim holati**. U yerda ✅ — joyida, ⚠️ — e'tibor bering,
> ❌ — tuzatish kerak. Muammo bo'lsa, Bosh sahifada ham ogohlantirish chiqadi.

> 📘 Ishga tushgandan keyin kundalik boshqaruv (adminlar, sertifikatlar, hisobotlar, imkoniyatlarni
> yoqish, Premium va daromad) — [BOSHQARUV_QOLLANMA.md](BOSHQARUV_QOLLANMA.md).

---

## 1-qadam. Render asosiy shoxdan (`main`) yangilansin

Barcha kod GitHub'da asosiy shox — `main` ga o'tkazilgan. **Har kungi avtomatik zaxira** va
**haftalik xavfsizlik tekshiruvi** faqat shu shoxda ishlaydi, server ham undan yangilanishi kerak.

1. Render → xizmatingiz (`kitobxon-hub`) → chapda **Settings** → **Build & Deploy** bo'limi.
2. **Branch** qatorida `main` turganini tekshiring. Boshqa nom (`claude/...`) bo'lsa — **Edit** →
   `main` ni tanlang → **Save Changes**.

(Agar serverni hali yaratmagan bo'lsangiz, [TEST_HOSTING.md](TEST_HOSTING.md) dagi 3-qadamda
**Branch** sifatida darhol `main` ni tanlang.)

---

## 2-qadam. Rasmlar va PDF hisobotlar uchun bepul ombor (Cloudflare R2)

Bepul serverda fayllar server diskida turadi va **server qayta yig'ilganda (har yangilanishda)
o'chib ketadi**. R2 — 10 GB gacha bepul doimiy ombor.

1. **https://dash.cloudflare.com** → ro'yxatdan o'ting (bepul).
2. Chap menyuda **R2 Object Storage** → **Create bucket** → nomi: `kitobxon-files` → **Create**.
   (R2 birinchi marta karta so'rashi mumkin — 10 GB gacha pul yechilmaydi.)
3. R2 sahifasida **Manage API tokens** → **Create API token** →
   ruxsat: **Object Read & Write**, faqat `kitobxon-files` → **Create**.
4. Chiqqan oynadan uchta qiymatni nusxalab oling: **Access Key ID**, **Secret Access Key** va
   **S3 endpoint** (`https://....r2.cloudflarestorage.com`). Bu oyna qayta ko'rsatilmaydi!
5. Render → xizmatingiz → **Environment** → **Add Environment Variable** va quyidagilarni qo'shing:

   | Key | Value |
   |---|---|
   | `STORAGE_BACKEND` | `s3` |
   | `STORAGE_ENDPOINT` | 4-banddagi S3 endpoint |
   | `STORAGE_REGION` | `auto` |
   | `STORAGE_BUCKET` | `kitobxon-files` |
   | `STORAGE_ACCESS_KEY` | Access Key ID |
   | `STORAGE_SECRET_KEY` | Secret Access Key |

6. **Save Changes** → server o'zi qayta ishga tushadi (2–5 daqiqa).
7. Tekshirish: **Tizim holati** → "Fayllar ombori" ✅ va "S3 (kitobxon-files)" deb yozilgan bo'lsin.

---

## 3-qadam. Har kungi avtomatik zaxira nusxa (backup)

Har kecha soat 02:13 da ma'lumotlar bazasining **shifrlangan** nusxasi olinadi va GitHub'da
30 kun saqlanadi. Nimadir o'chib ketsa yoki buzilsa — shu nusxadan tiklanadi.

1. Uzun parol o'ylab toping (masalan, 5–6 ta tasodifiy so'z: `qalam daryo yulduz olma kitob 2026`).
   **Uni qog'ozga yozib, xavfsiz joyda saqlang** — parolsiz zaxirani hech kim, hatto siz ham ocha olmaysiz.
2. GitHub → `kitobxon-hub` → **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret** — ikkita sir qo'shing:

   | Name | Secret |
   |---|---|
   | `BACKUP_DATABASE_URL` | Neon'dagi baza manzili (Render'dagi `DATABASE_URL` bilan bir xil) |
   | `BACKUP_PASSPHRASE` | 1-banddagi parol |

3. Darhol sinab ko'ring: **Actions** → chapda **Database backup** → **Run workflow** → **Run workflow**.
4. 1–2 daqiqadan keyin yashil ✅ chiqadi. Ustiga bosing — pastda **Artifacts** bo'limida
   `kitobxon-...` fayli turadi. Bu — zaxira nusxa.

Tiklash kerak bo'lsa (bazani yo'qotish, xato o'chirish) — menga yoki dasturchiga murojaat qiling:
qadamlar [DEPLOYMENT.md](DEPLOYMENT.md#restore) da yozilgan, faqat parol kerak bo'ladi.

---

## 4-qadam. Server ishlashini kuzatish (UptimeRobot)

Agar hali qilmagan bo'lsangiz ([TEST_HOSTING.md](TEST_HOSTING.md) dagi "serverni uyg'oq saqlash"):

1. **https://uptimerobot.com** → bepul ro'yxatdan o'ting.
2. **New monitor** → **HTTP(s)** → URL: `https://SIZNING-MANZIL.onrender.com/health` → interval **5 daqiqa**.
3. **Alert contacts** da emailingizni (xohlasangiz Telegram'ni ham) belgilang — server to'xtasa xabar keladi.

⚠️ `/health/db` manzilini bepul tarifda **5 daqiqalik** monitorga qo'ymang: u ma'lumotlar bazasini
doim uyg'oq ushlab turadi va Neon'ning oylik bepul limiti tugab qoladi. Baza holatini
**Tizim holati** sahifasida ko'rasiz.

---

## 5-qadam. Ikkinchi bosh administrator

Telegram akkauntingizga kira olmay qolsangiz ham boshqaruv yo'qolmasligi uchun ishonchli
ikkinchi odamni bosh administrator qiling:

1. U odam botda ro'yxatdan o'tsin va botga `/myid` yozib, raqamini sizga yuborsin.
2. Render → xizmatingiz → **Environment** → `SUPER_ADMIN_TELEGRAM_IDS` qiymatiga vergul bilan
   uning raqamini qo'shing, masalan: `123456789,987654321` → **Save Changes**.
3. Server qayta ishga tushgach, u botga `/admin` yozadi — admin panelga kiradi.
4. **Admin panel → Adminlar** ro'yxatida u "Bosh administrator" bo'lib ko'rinadi.

(Oddiy administratorlarni esa **Adminlar → + Admin tayinlash** orqali, faqat kerakli
ruxsatlar bilan tayinlaysiz.)

---

## 6-qadam. Tashkilot ma'lumotlari (rasmiy hisobotlar uchun)

**Admin panel → Sozlamalar → 🏛 Tashkilot** bo'limida institut va klub nomi to'g'ri yozilganini
tekshiring — ular PDF hisobotning sarlavhasida chiqadi. Hisobotdagi mas'ul shaxs — tadbirni
yaratishda tanlangan mas'ul administrator.

---

## 7-qadam (ixtiyoriy). AI yordamchi

AI'siz ham hisobotlar shablon bo'yicha to'liq yoziladi. AI esa matnni chiroyliroq, rasmiy uslubda
yozib beradi (raqamlarni faqat bazadan oladi — o'zidan qo'shsa, tizim tasdiqlashga ruxsat bermaydi).

1. **https://console.anthropic.com** → ro'yxatdan o'ting → **Billing** da hisobni to'ldiring va
   **oylik limit** qo'ying (masalan, 5 $) — shundan ortiq pul sarflanmaydi.
2. **API Keys** → **Create Key** → nusxalang.
3. Render → **Environment** → `AI_API_KEY` = shu kalit → **Save Changes**.
4. **Tizim holati** → "AI yordamchi" ✅.

---

## 8-qadam. Yakuniy sinov (15 daqiqa)

Bir do'stingiz bilan butun yo'lni bir marta o'tib chiqing:

1. Do'stingiz botda ro'yxatdan o'tadi (`/start`).
2. Siz admin panelda kitob, tadbir (holati **E'lon qilingan**) va test qo'shasiz.
3. Tadbir vaqtida **Tadbirlar → Davomat → ▶ Davomatni ochish** — ekrandagi QR kodni do'stingiz Mini App'da skanerlaydi
   (yoki 6 belgili kodni yozadi) → "Davomatingiz qayd etildi!".
4. Do'stingiz testni yechadi → natija va ballar **Natijalarim** da ko'rinadi.
5. Siz **Hisobotlar → + Yangi hisobot** → qoralama → **✓ Tasdiqlash va PDF** → PDF'ni yuklab olasiz.
6. **Tizim holati** da ❌ qolmagan bo'lsin.

Hammasi ishlasa — a'zolarga bot havolasini (`https://t.me/BOT_NOMI`) tarqatishingiz mumkin. 🎉

---

## Xarajatlar

| Xizmat | Tarif | Narxi |
|---|---|---|
| Render (server) | Free | 0 $ (UptimeRobot bilan uxlamaydi) |
| Neon (ma'lumotlar bazasi) | Free | 0 $ (0,5 GB — bir necha ming a'zo uchun yetadi) |
| Cloudflare R2 (fayllar) | Free | 0 $ (10 GB gacha) |
| GitHub (kod, tekshiruvlar, zaxira) | Free | 0 $ (oyiga 2000 daqiqa avtomatik tekshiruv; bitta yangilanish ~15 daqiqa) |
| Anthropic (AI, ixtiyoriy) | oldindan to'lov | o'zingiz qo'ygan limitdan oshmaydi |

**Qachon pullik tarifga o'tish kerak?** Faol a'zolar 300–500 dan oshsa, bot sekinlashsa yoki
Tizim holati "Baza hajmi chegarasiga yaqin" desa. Eng oddiy qadam — Render'ning **Starter**
tarifi (taxminan 7 $/oy): server umuman uxlamaydi; shunda `WORKER_INTERVAL_SECONDS` ni `60` ga
o'zgartiring (eslatmalar har daqiqada tekshiriladi). Katta o'zgarishlar uchun loyihani
professional dasturchiga topshirish mumkin — barcha texnik hujjatlar [DEPLOYMENT.md](DEPLOYMENT.md)
va [ARCHITECTURE.md](ARCHITECTURE.md) da.

---

## Muammo bo'lsa

| Belgisi | Nima qilish kerak |
|---|---|
| Tizim holatida "Fayllar ombori ❌" | R2 qiymatlarida bo'sh joy yoki xato harf bormi — qaytadan nusxalang (2-qadam) |
| "Database backup" qizil ❌ | Ustiga bosing → qizil qatorni menga yuboring. Ko'pincha `BACKUP_DATABASE_URL` noto'g'ri nusxalangan bo'ladi |
| "Security audit" qizil ❌ | Ishlatilayotgan kutubxonalardan birida xavfsizlik yangilanishi chiqqan — menga ayting, yangilab beraman |
| Tizim holatida "Telegram bot ⚠️ … xato qayd etgan" | Server uxlab qolgan bo'lishi mumkin — UptimeRobot ishlayotganini tekshiring |
| Tizim holatida "… ta xabar navbatda kechikmoqda" | Xuddi shu: server uxlagan. UptimeRobot monitorini yoqing (4-qadam) |

Boshqa savollar bo'lsa — [TEST_HOSTING.md](TEST_HOSTING.md#muammolar-va-yechimlar) va
[TROUBLESHOOTING.md](TROUBLESHOOTING.md).
