# Botni bepul serverga joylashtirib sinab ko'rish

Bu qo'llanma loyiha egasi uchun. Kompyuteringizga hech narsa o'rnatmaysiz — hammasi brauzer va
Telegram orqali qilinadi. Taxminan **30–40 daqiqa** vaqt oladi.

## Nimalar kerak bo'ladi

| Xizmat | Nima uchun | Narxi |
|---|---|---|
| **Telegram @BotFather** | Bot yaratish va uning tokenini (maxfiy kalitini) olish | Bepul |
| **Neon** (neon.tech) | Ma'lumotlar bazasi (a'zolar, ballar va h.k. shu yerda saqlanadi) | Bepul, muddatsiz (0.5 GB) |
| **Render** (render.com) | Server: bot, Mini App va admin panel shu yerda ishlaydi | Bepul |
| **GitHub** | Kod saqlanadigan joy (sizda bor) | Bepul |

> ⚠️ **Bepul serverning cheklovi:** Render bepul serveri 15 daqiqa hech kim yozmasa "uxlab qoladi".
> Shundan keyin botga yozilgan birinchi xabarga javob **~1 daqiqa** kechikib keladi, keyingi
> xabarlar odatdagidek tez ishlaydi. Sinov uchun bu yetarli. Haqiqiy ishga tushirishda dasturchilar
> doimiy ishlaydigan serverga o'tkazadi (`docs/DEPLOYMENT.md`).

---

## 1-qadam. Telegram'da bot yaratish

1. Telegram'da **@BotFather** ni oching va **Start** ni bosing.
2. `/newbot` buyrug'ini yuboring.
3. Bot nomini yozing, masalan: `Kitobxon Hub`
4. Bot manzilini (username) yozing. U **`bot` bilan tugashi shart**, masalan: `kitobxon_hub_bot`.
   Agar band bo'lsa, boshqasini o'ylab toping (masalan `kitobxonhub_tdtu_bot`).
5. BotFather sizga shunga o'xshash **token** yuboradi:
   `7123456789:AAH...uzun...harflar`
6. Tokenni va bot manzilini (`@` belgisisiz) eslatmalar ilovasiga vaqtincha saqlab qo'ying.

> 🔒 **Token — bu botning paroli.** Uni hech kimga yubormang, GitHub'ga yozmang, skrinshot
> qilmang. Agar tasodifan oshkor bo'lsa: @BotFather → `/revoke` → yangi token oling va Render'da
> almashtiring.

---

## 2-qadam. Ma'lumotlar bazasini yaratish (Neon)

1. **https://neon.tech** saytini oching → **Sign up** → GitHub yoki Google hisobingiz bilan kiring.
2. Yangi loyiha (**Create project**) oynasida:
   * **Project name:** `kitobxon-hub`
   * **Postgres version:** taklif qilinganini qoldiring
   * **Region:** **AWS Europe Central 1 (Frankfurt)** — O'zbekistonga eng yaqinlaridan biri
3. **Create project** ni bosing.
4. Ochilgan sahifada **Connect** (yoki **Connection string**) tugmasini bosing.
5. `postgresql://...` bilan boshlanadigan uzun manzilni **Copy** qiling. U taxminan shunday ko'rinadi:
   `postgresql://neondb_owner:AbC123...@ep-cool-name-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require`
6. Bu manzilni ham vaqtincha saqlab qo'ying — bu ham **maxfiy** (ichida parol bor).

---

## 3-qadam. Serverni ishga tushirish (Render)

1. **https://render.com** saytini oching → **Get Started** → **GitHub** orqali kiring.
   Render GitHub'ga kirish ruxsatini so'raydi — `kitobxon-hub` repository'siga ruxsat bering.
2. Yuqoridagi **New +** tugmasini bosing → **Blueprint** ni tanlang.
3. Ro'yxatdan **kitobxon-hub** repository'sini tanlang (**Connect**).
4. **Branch** maydonida kod turgan shoxni tanlang:
   * agar kod `main` shoxiga birlashtirilgan bo'lsa — `main`;
   * aks holda — `claude/amazing-noether-vlg12l`.
5. Render loyihadagi `render.yaml` faylini o'qiydi va bir nechta qiymatni so'raydi. Ularni kiriting:

   | Maydon | Nima yoziladi |
   |---|---|
   | `DATABASE_URL` | 2-qadamda Neon'dan nusxa olgan manzil |
   | `BOT_TOKEN` | 1-qadamdagi token |
   | `BOT_USERNAME` | bot manzili `@` belgisisiz, masalan `kitobxon_hub_bot` |
   | `SUPER_ADMIN_TELEGRAM_IDS` | hozircha `0` yozing (5-qadamda o'zgartiramiz) |

   `SECRET_KEY` ni Render o'zi avtomatik yaratadi — unga tegmang.
6. **Apply** (yoki **Deploy Blueprint**) tugmasini bosing.
7. Kuting: birinchi marta yig'ish (**build**) **5–10 daqiqa** davom etadi. Holat **Live** bo'lishi kerak.
8. Xizmat sahifasining yuqorisida manzil paydo bo'ladi, masalan:
   `https://kitobxon-hub.onrender.com` (sizniki biroz boshqacha bo'lishi mumkin).

---

## 4-qadam. Tekshirish

Brauzerda quyidagilarni oching (`kitobxon-hub.onrender.com` o'rniga o'z manzilingizni yozing):

| Manzil | Kutilgan natija |
|---|---|
| `https://kitobxon-hub.onrender.com/health` | `{"status":"ok", ...}` |
| `https://kitobxon-hub.onrender.com/health/db` | `{"status":"ok","service":"database"}` |
| `https://kitobxon-hub.onrender.com/app/` | "Kitobxon Hub" sahifasi va "✅ Server bilan aloqa bor" |

Keyin Telegram'da botingizni oching va **/start** ni bosing:

- [ ] Bot salomlashib, ismingizni so'radi
- [ ] Ism → familiya → telefon (tugma orqali) → kurs → guruh so'raldi
- [ ] Ma'lumotlar ko'rsatildi va **✅ Tasdiqlash** dan keyin "Tabriklaymiz" xabari keldi
- [ ] Pastda 9 ta tugmali menyu paydo bo'ldi (📚 Kitoblar, 👤 Profilim, ...)
- [ ] **👤 Profilim** ma'lumotlaringizni ko'rsatdi
- [ ] **🔔 Bildirishnomalar** da tugmalar ✅/❌ ga almashadi
- [ ] Yozish maydoni yonidagi **📚 Kitobxon Hub** tugmasi Mini App'ni ochadi

> Agar bot javob bermasa — 1 daqiqa kuting (server uyg'onyapti) va yana yozing.

---

## 5-qadam. O'zingizni bosh administrator qilish

1. Botga **/myid** yuboring. Bot raqam yuboradi, masalan `123456789`.
2. Render'da xizmatingizni oching → chapdagi **Environment** bo'limi.
3. `SUPER_ADMIN_TELEGRAM_IDS` qiymatini `0` dan o'zingizning raqamingizga almashtiring.
   Bir nechta odam bo'lsa — vergul bilan: `123456789,987654321`
4. **Save Changes** ni bosing. Server avtomatik qayta ishga tushadi (1–3 daqiqa).
5. Botga **/admin** yuboring → "🔐 Admin panelga kirish" tugmasi keladi. Bosing — admin panel ochiladi.
   (Admin panelning sahifalari keyingi bosqichlarda to'ldiriladi; hozircha tizim holatini ko'rsatadi.)

---

## Ixtiyoriy: serverni "uyg'oq" saqlash

Bot har doim tez javob berishi uchun bepul **UptimeRobot** (uptimerobot.com) xizmatida monitor
yarating: turi **HTTP(s)**, manzili `https://SIZNING-MANZIL.onrender.com/health`, oraliq **5 daqiqa**.
U har 5 daqiqada serverga murojaat qiladi va server uxlamaydi (Render'ning oylik 750 soatlik bepul
limiti bitta server uchun yetarli). Bundan tashqari, server ishlamay qolsa sizga email yuboradi.

---

## Kod yangilanganda

Har safar GitHub'dagi tanlangan shoxga yangi kod yuklanganda Render uni **avtomatik** qayta
joylashtiradi. Siz hech narsa qilishingiz shart emas — faqat **Events** bo'limida "Deploy live"
yozuvini ko'rasiz.

---

## Muammolar va yechimlar

| Belgisi | Sababi | Nima qilish kerak |
|---|---|---|
| Bot umuman javob bermaydi, 2–3 daqiqadan keyin ham | Token noto'g'ri yoki server ishlamayapti | Render → **Logs** bo'limini oching. `Could not configure the Telegram bot` yozuvi bo'lsa — `BOT_TOKEN` ni tekshiring (bo'sh joy qolmaganiga e'tibor bering) va **Save** qiling |
| `/health/db` xato beradi | `DATABASE_URL` noto'g'ri | Neon'dan manzilni qaytadan nusxalang (to'liq, `postgresql://` dan oxirigacha) |
| Render'da **Build failed** | Kodda xatolik | GitHub → **Actions** bo'limida yashil ✅ bor-yo'qligini tekshiring va menga Logs'dagi oxirgi qizil qatorlarni yuboring |
| Mini App "Internet aloqasi yo'q" deydi | Server uxlayapti | 1 daqiqa kutib, **Qayta urinish** ni bosing |
| `/admin` "faqat administratorlar uchun" deydi | Telegram ID kiritilmagan | 5-qadamni bajaring; `/myid` dagi raqam bilan bir xil ekanini tekshiring |

Boshqa muammo bo'lsa — Render **Logs** dagi oxirgi 20–30 qatorni nusxalab menga yuboring
(u yerda parol va tokenlar avtomatik yashiriladi).
