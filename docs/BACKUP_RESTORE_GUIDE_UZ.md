# Zaxira nusxa va tiklash qo'llanmasi

Bu hujjat Kitobxon Hub ma'lumotlar bazasining zaxira nusxalarini olish va kerak
bo'lganda tiklash tartibini tushuntiradi. Qo'llanma **bosh administrator** (super
admin) va serverni boshqaradigan texnik xodim uchun.

> Qisqacha: tizim har kecha avtomatik zaxira oladi. Bazani **tiklash** esa — bu
> ehtiyotkor, qo'lda bajariladigan amal: avval yangi zaxira olinadi, so'ng
> `pg_restore` orqali tiklanadi. Admin paneldagi tugma orqali bazani «bosib
> yozib» bo'lmaydi — bu xavfsizlik uchun ataylab shunday qilingan.

---

## 1. Zaxira nusxa nima va qayerda saqlanadi

Har bir zaxira nusxa — `pg_dump` yordamida olingan, siqilgan (`custom format`,
`-Fc`) to'liq nusxa. U `pg_restore` bilan to'liq tiklanadi.

Fayl **tizim sozlamalaridagi fayl xotirasida** saqlanadi (muqova va sertifikatlar
qayerda saqlansa — o'sha yerda):

- **Bulutda (Render + Neon va h.k.):** `STORAGE_BACKEND=s3` bo'lsa, nusxalar S3/R2
  kabi doimiy obyekt xotirasiga tushadi. ⚠️ **Bu majburiy:** Render konteynerining
  diski vaqtinchalik (ephemeral), shuning uchun `local` xotira bilan zaxira nusxalar
  qayta ishga tushirishdan keyin yo'qoladi. Bulutda albatta S3 sozlang.
- **Institut serverida:** `STORAGE_BACKEND=local` bo'lsa, nusxalar doimiy diskdagi
  `STORAGE_LOCAL_PATH` papkasida (`backups/…`) saqlanadi. Bu diskni ham muntazam
  (masalan, tashqi disk yoki tarmoq diskiga) nusxalab turish tavsiya etiladi.

Har bir nusxa uchun `backups` jadvalida yozuv qoladi: turi, vaqti, hajmi, SHA-256
nazorat yig'indisi, holati (muvaffaqiyatli/xato). Yozuvda hech qachon parol yoki
ulanish satri saqlanmaydi.

---

## 2. Avtomatik zaxira (hech narsa qilish shart emas)

Fon ishchi (worker) jadval bo'yicha:

- **Har kecha soat 23:00 (Asia/Tashkent)** — kunlik zaxira (`DAILY`).
- **Har oyning 1-sanasida** — qo'shimcha oylik zaxira (`MONTHLY`), u uzoqroq saqlanadi.

Saqlash muddati (sozlamalardan o'zgartiriladi):

| Sozlama | Standart | Ma'nosi |
|---|---|---|
| `BACKUP_RETENTION_DAILY` | 14 | Oxirgi 14 ta kunlik nusxa saqlanadi |
| `BACKUP_RETENTION_MONTHLY` | 12 | Oxirgi 12 ta oylik nusxa saqlanadi |
| `BACKUPS_ENABLED` | `true` | Avtomatik zaxirani butunlay o'chirish uchun `false` |

Muddatdan oshgan **avtomatik** nusxalar o'zi o'chiriladi. **Qo'lda** olingan nusxalar
hech qachon avtomatik o'chmaydi — ularni faqat bosh admin o'zi o'chiradi.

> Eslatma: worker 23:00 soati ichida ishga tushganda zaxira oladi va o'sha kecha
> uchun takroran olmaydi (idempotent). Agar server kechasi o'chiq tursa, o'sha kungi
> avtomatik nusxa olinmaydi — bunday hollarda admin paneldan qo'lda nusxa oling.

---

## 3. Admin panel: «Zaxira nusxa» bo'limi

Faqat **bosh administrator** ko'radi (chap menyuda 💾 **Zaxira nusxa**).

- **+ Hozir zaxira olish** — shu zahoti qo'lda nusxa oladi.
- **⬇ Yuklab olish** — nusxa faylini kompyuteringizga yuklab oladi (`.dump`).
  Muhim nusxani serverdan tashqarida (masalan, tashkilot diskida yoki ishonchli
  bulutda) ham saqlab qo'ying.
- **O'chirish** — keraksiz nusxani o'chiradi.
- Yuqorida avtomatik zaxira holati, jadvali va oxirgi muvaffaqiyatli nusxa vaqti
  ko'rsatiladi.

---

## 4. Bazani tiklash (qo'lda, ehtiyotkorlik bilan)

Tiklash — bazani **almashtiradigan** amal, shuning uchun uni admin paneldagi tugma
qilmaydi. Quyidagi tartib server (SSH) kirishiga ega texnik xodim tomonidan, bosh
administrator **aniq ruxsati** bilan bajariladi.

### 4.1. Avval — yangi («tiklashdan oldingi») zaxira

Hozirgi holatni yo'qotmaslik uchun, tiklashdan oldin albatta yangi nusxa oling:

```bash
pg_dump --no-owner --no-privileges -Fc "$DATABASE_URL" -f pre_restore.dump
```

(Yoki admin paneldan «Hozir zaxira olish»ni bosing va faylni yuklab oling.)

### 4.2. Avval test bazaga tiklab ko'ring (tavsiya etiladi)

To'g'ridan-to'g'ri ishchi bazaga tiklashdan oldin, nusxaning soz ekanini bo'sh
test bazada tekshiring:

```bash
createdb kitobxon_restore_test
pg_restore --no-owner --no-privileges --clean --if-exists \
    -d "postgresql://USER:PASSWORD@HOST:5432/kitobxon_restore_test" nusxa.dump
# jadvallar va yozuvlar sonini tekshiring, so'ng test bazani o'chiring:
dropdb kitobxon_restore_test
```

### 4.3. Ishchi bazaga tiklash

1. Ilovani (web + worker) to'xtating, hech kim bazaga yozmasin.
2. Bosh administratordan **yozma/aniq ruxsat** oling.
3. Tiklang:

   ```bash
   pg_restore --no-owner --no-privileges --clean --if-exists \
       -d "$DATABASE_URL" nusxa.dump
   ```

4. Migratsiyalar eng so'nggi holatda ekanini tekshiring (`alembic upgrade head` —
   `DATABASE_MIGRATION_GUIDE`ga qarang).
5. Ilovani qayta ishga tushiring va asosiy amallarni (kirish, ro'yxat, davomat)
   tekshiring.

> Agar biror narsa noto'g'ri ketsa — 4.1 da olingan `pre_restore.dump` orqali
> eski holatга qaytasiz.

### 4.4. Admin paneldan tiklash (ilova ichida, xavfsiz)

Admin paneldagi «Zaxira nusxa» bo'limida har bir nusxa yonida **♻️ Tiklash** tugmasi
bor. Bu tugma bosilganda tizim quyidagi **xavfsiz** tartibni bajaradi:

1. Bosh admin tasdiqlash uchun aniq matn (`TIKLASHNI TASDIQLAYMAN`) yozishi kerak.
2. Tizim **avtomatik ravishda hozirgi holatning «tiklashdan oldingi» zaxirasini**
   oladi (agar u muvaffaqiyatsiz bo'lsa — tiklash to'xtaydi).
3. Tanlangan nusxa **tekshiriladi** (shifrlangan bo'lsa, avval `BACKUP_ENCRYPTION_KEY`
   bilan ochiladi; keyin `pg_restore --list` orqali fayl butunligi tasdiqlanadi) —
   bu bosqich hech qanday bazaga tegmaydi.
4. **Jonli bazani almashtirish** esa faqat `ALLOW_IN_APP_RESTORE=true` bo'lsa va
   admin «Jonli bazani almashtirish» katagini belgilagan taqdirda bajariladi. U
   `pg_restore --single-transaction` bilan ishlaydi — ya'ni to'liq o'tadi yoki
   umuman o'tmaydi (yarim-tiklash bo'lmaydi).

> ⚠️ **Standart holatda jonli almashtirish O'CHIRILGAN.** Shunda tugma faqat zaxirani
> tekshiradi va xavfsizlik nusxasini oladi — bu eng xavfsiz holat. Jonli bazani ilova
> ichidan almashtirishni yoqmoqchi bo'lsangiz, buni **kam yuklamali/texnik vaqtda**
> qiling va **tiklashdan so'ng ilovani (web + worker) qayta ishga tushiring**. Katta
> yoki muhim bazalarda 4.1–4.3 dagi server orqali tiklash hamon eng ishonchli yo'l.

---

## 5. Zaxira fayllarini shifrlash (ixtiyoriy, lekin tavsiya etiladi)

`BACKUP_ENCRYPTION_KEY` berilsa, **har bir zaxira fayli saqlashdan oldin
AES-256-GCM bilan shifrlanadi**. Shunda S3/R2/Google Drive’da yotgan fayl kalitsiz
hech kimga foydasiz — uni faqat shu kalit bilan ochib bo'ladi.

**Kalitni qanday yaratish:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Chiqqan satrni muhit o'zgaruvchisiga qo'ying:

```
BACKUP_ENCRYPTION_KEY=<yuqoridagi tasodifiy satr>
```

**Juda muhim qoidalar:**

- Kalitni **zaxiralardan alohida** joyda saqlang (zaxira qaysi diskda/bulutda yotsa,
  kalit o'sha yerda bo'lmasin). Masalan: parol menejeri yoki sejf.
- Kalit **yo'qolsa — shifrlangan zaxiralarni tiklab bo'lmaydi.** Nusxasini ishonchli
  joyda saqlang.
- Kalit **o'zgartirilsa**, eski kalit bilan olingan nusxalar o'sha eski kalitnigina
  talab qiladi — eski kalitni ham saqlab turing.
- Kalit hech qachon kodga, hisobotga yoki zaxira faylining ichiga yozilmaydi.

Admin paneldagi **⬇ Yuklab olish** tugmasi faylni **avtomatik ochib** (deshifrlab)
beradi — ya'ni yuklangan `.dump` to'g'ridan-to'g'ri `pg_restore`’ga tayyor. Faqat
xotiradan to'g'ridan-to'g'ri olingan `.dump.enc` fayli shifrlangan bo'ladi.

Shifrlash yoqilgani admin panelda «🔒 Shifrlash yoqilgan» belgisi bilan ko'rinadi,
har bir shifrlangan nusxa yonida 🔒 turadi.

---

## 6. Google Drive'ga qo'shimcha nusxa (ixtiyoriy)

Asosiy nusxa doim tizim fayl xotirasida (S3/R2/lokal disk) saqlanadi. Qo'shimcha
ravishda **har bir zaxirani Google Drive'ga ham** yuborish mumkin — bu mutlaqo boshqa
joydagi (off-site) ikkinchi nusxa. Shifrlash yoqilgan bo'lsa, Drive'dagi nusxa ham
shifrlangan bo'ladi (xuddi shu baytlar yuboriladi).

**Sozlash (bir marta):**

1. Google Cloud'da **service account** (xizmat hisobi) yarating va unga **JSON kalit**
   oling.
2. Drive'da bitta papka oching va uni service account'ning e-mailiga (`...@...iam.gserviceaccount.com`)
   **ulashing** (Editor huquqi bilan) — shunda u papkaga fayl yuklay oladi.
3. Papkaning ID'sini oling (papka URL'idagi `folders/` dan keyingi qism).
4. **Eng oson yo'l — admin panel:** bosh admin **«Zaxira nusxa» → «☁️ Google Drive nusxa»**
   bo'limida papka ID va service account JSON faylini joylashtiradi, «Yoqilgan» belgisini
   qo'yib **Saqlash**ni bosadi, so'ng **«Ulanishni tekshirish»** bilan ulanishni sinab
   ko'radi. Env o'zgaruvchilari bilan ovora bo'lish shart emas. (Panel sozlamasi env'dan
   ustun turadi.)
5. **Muqobil — muhit o'zgaruvchilari** (panelga kira olmasangiz):

   ```
   BACKUP_GDRIVE_ENABLED=true
   BACKUP_GDRIVE_FOLDER_ID=<papka ID>
   BACKUP_GDRIVE_SERVICE_ACCOUNT=<service account JSON faylining to'liq matni>
   ```

> Service account JSON — bu **maxfiy** ma'lumot (ichida xususiy kalit bor). Panel orqali
> saqlansa, u bazada **shifrlangan** holda (AES-256-GCM, SECRET_KEY bilan) saqlanadi va
> hech qachon brauzerga qaytarilmaydi; kodga, hisobotga yoki zaxira fayliga yozilmaydi.
> Og'ir Google kutubxonasi ishlatilmaydi — faqat `httpx` + `PyJWT` orqali Drive REST
> API'ga murojaat qilinadi.

Drive nusxasi **ixtiyoriy va «best-effort»**: Drive'ga yuklash muvaffaqiyatsiz bo'lsa
ham, asosiy zaxira (S3/local) baribir olinadi — zaxira olish to'xtamaydi. Zaxira
o'chirilganda yoki muddati o'tib avtomatik tozalanganda, Drive'dagi nusxasi ham
o'chiriladi. Drive nusxasi bor nusxa admin panelda ☁️ belgisi bilan ko'rinadi.

---

## 7. Sozlash (server)

Muhit o'zgaruvchilari (`.env` yoki Render/Compose sozlamalari):

```
BACKUPS_ENABLED=true
BACKUP_RETENTION_DAILY=14
BACKUP_RETENTION_MONTHLY=12
# Shifrlash (ixtiyoriy) — berilsa zaxiralar AES-256-GCM bilan shifrlanadi:
# BACKUP_ENCRYPTION_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
# Admin paneldan JONLI bazani almashtirishga ruxsat (standart: false — faqat tekshirish):
# ALLOW_IN_APP_RESTORE=false
# Google Drive'ga qo'shimcha nusxa (ixtiyoriy — 6-bo'limga qarang):
# BACKUP_GDRIVE_ENABLED=false
# BACKUP_GDRIVE_FOLDER_ID=<Drive papka ID>
# BACKUP_GDRIVE_SERVICE_ACCOUNT=<service account JSON matni>
# pg_dump / pg_restore PATH da bo'lmasa, to'liq yo'lni ko'rsating:
# PG_DUMP_PATH=/usr/lib/postgresql/16/bin/pg_dump
# PG_RESTORE_PATH=/usr/lib/postgresql/16/bin/pg_restore
```

- Docker tasviriga `pg_dump`/`pg_restore` **PostgreSQL 18** mijozi (rasmiy PGDG
  ombori orqali) qo'shilган.
- ⚠️ **Muhim:** `pg_dump` versiyasi baza serveri versiyasidan **past bo'lmasligi**
  shart — aks holda `server version mismatch` xatosi chiqadi. Standart tasvir 18-versiya
  mijozini o'rnatadi (server 18.x uchun). Agar serveringiz boshqa (masalan 19) bo'lsa,
  tasvirni mos versiya bilan quring:

  ```bash
  docker build --build-arg PG_MAJOR=19 -t kitobxon-hub .
  ```

---

## 8. Egasi hal qiladigan masalalar

- **Shifrlash ✅ (tayyor):** `BACKUP_ENCRYPTION_KEY` berilsa zaxiralar AES-256-GCM
  bilan shifrlanadi (5-bo'limga qarang). Kalit zaxiralardan alohida saqlanadi.
- **Google Drive nusxa ✅ (tayyor):** `BACKUP_GDRIVE_*` berilsa, har bir zaxira
  Google Drive'ga ham yuboriladi (6-bo'limga qarang). Service account JSON maxfiy
  ma'lumot — alohida (sir sifatida) beriladi, hech qachon kodga yozilmaydi. Shuningdek
  `STORAGE_BACKEND=s3` bo'lsa, asosiy nusxa allaqachon tashqi doimiy xotirada bo'ladi.
- **Admin paneldan tiklash tugmasi ✅ (tayyor):** 4.4-bo'limga qarang. Tugma har doim
  tasdiq matnini so'raydi, avtomatik «tiklashdan oldingi» zaxira oladi va faylni
  tekshiradi; jonli bazani almashtirish esa faqat `ALLOW_IN_APP_RESTORE=true` bo'lsa
  ishlaydi (standart — o'chirilgan).

---

**Bog'liq hujjatlar:** `DEPLOYMENT_GUIDE_UZ.md`, `DATABASE_MIGRATION_GUIDE_UZ.md`,
`PRODUCTION_HANDOFF_CHECKLIST_UZ.md`.
