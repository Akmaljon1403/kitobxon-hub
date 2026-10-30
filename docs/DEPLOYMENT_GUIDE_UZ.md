# Ishga tushirish (deployment) qo'llanmasi

Kitobxon Hub — bitta Docker tasviri (backend + Mini App + Admin panel bir joyda) va
bitta PostgreSQL bazasi. Ikki xil joyga qo'yish mumkin:

1. **Bulut:** Render (ilova) + Neon (baza) — tez va bepul boshlash uchun.
2. **Institut serveri:** o'z serveringizda Docker orqali — to'liq nazorat uchun.

Batafsil, bosqichma-bosqich qo'llanmalar allaqachon bor — bu hujjat ularga yo'l
ko'rsatadi va eng muhim sozlamalarни bir joyga yig'adi:

- Bulut (bepul test): [`TEST_HOSTING.md`](TEST_HOSTING.md)
- Institut serveri: [`INSTITUT_SERVERI.md`](INSTITUT_SERVERI.md)
- Umumiy texnik tafsilot: [`DEPLOYMENT.md`](DEPLOYMENT.md)

---

## 1. Nima kerak (oldindan)

- **Telegram bot tokeni** — [@BotFather](https://t.me/BotFather) dan.
- **PostgreSQL bazasi** — Neon (bulut) yoki serveringizdagi PostgreSQL 16+.
- **Bosh administrator Telegram ID(lar)i** — [@userinfobot](https://t.me/userinfobot) dan raqam.
- **Domen / HTTPS manzil** — bot webhook va Mini App uchun (Render o'zi beradi).

---

## 2. Muhit o'zgaruvchilari (env)

Majburiylari (ularsiz ishga tushmaydi — `python -m app.cli preflight` tekshiradi):

| O'zgaruvchi | Ma'nosi |
|---|---|
| `DATABASE_URL` | PostgreSQL manzili, paroli bilan to'liq (`postgresql://...`) |
| `SECRET_KEY` | Tasodifiy uzun maxfiy satr (Render `generateValue` bilan o'zi yaratadi) |
| `BOT_TOKEN` | BotFather tokeni |
| `SUPER_ADMIN_TELEGRAM_IDS` | Bosh adminlar ID'lari (vergul bilan) |

Muhimlari:

| O'zgaruvchi | Standart | Ma'nosi |
|---|---|---|
| `PUBLIC_BASE_URL` | — | Ilovaning HTTPS manzili (webhook/Mini App uchun) |
| `BOT_USERNAME` | — | Bot @username'i (havolalarда ishlatiladi) |
| `BOT_MODE` | `webhook` | `webhook` (ishlab chiqarish) / `polling` (lokal) / `disabled` |
| `TELEGRAM_WEBHOOK_SECRET` | — | Webhook'ni himoyalash uchun sir |
| `WORKER_ENABLED` | `true` | Fon ishchi (eslatma, zaxira) yoqilganmi |
| `WORKER_INTERVAL_SECONDS` | `60` | Tekshiruvlar oralig'i (Neon bepul uchun `1800`) |

Fayl xotirasi (muqova, sertifikat, **zaxira nusxalar** shu yerда saqlanadi):

| O'zgaruvchi | Ma'nosi |
|---|---|
| `STORAGE_BACKEND` | `local` (server diski) yoki `s3` (bulut obyekt xotirasi) |
| `STORAGE_LOCAL_PATH` | `local` uchun papka (standart `./storage`) |
| `STORAGE_ENDPOINT` / `STORAGE_BUCKET` / `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` / `STORAGE_REGION` | `s3` uchun |

> ⚠️ **Bulutda zaxira nusxalar uchun `s3` majburiy.** Render diski vaqtinchalik —
> `local` bo'lsa zaxira nusxalar qayta ishga tushishdan keyin yo'qoladi.
> Batafsil: [`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md).

Zaxira sozlamalari: `BACKUPS_ENABLED`, `BACKUP_RETENTION_DAILY`,
`BACKUP_RETENTION_MONTHLY`, `PG_DUMP_PATH`, `PG_RESTORE_PATH`.

Qo'shimcha zaxira imkoniyatlari (hammasi **ixtiyoriy**, berilmasa o'chiq turadi —
ilovaga xalal bermaydi):

| O'zgaruvchi | Ma'nosi |
|---|---|
| `BACKUP_ENCRYPTION_KEY` | Berilsa, zaxiralar AES-256-GCM bilan shifrlanadi. Kalit zaxiralardan **alohida** saqlanadi |
| `ALLOW_IN_APP_RESTORE` | `true` bo'lsa, bosh admin paneldan jonli bazani tiklay oladi (standart `false` — faqat tekshirish) |
| `BACKUP_GDRIVE_ENABLED` / `BACKUP_GDRIVE_FOLDER_ID` / `BACKUP_GDRIVE_SERVICE_ACCOUNT` | Google Drive'ga qo'shimcha nusxa |

> Batafsil (kalit yaratish, service account sozlash, tiklash tartibi):
> [`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md).

Ixtiyoriy: `REDIS_URL` (kesh/rate-limit), `AI_API_KEY` + `AI_MODEL` (hisobot
qoralamasi), `STARS_API_BASE_URL` + `STARS_API_KEY` (Stars avtomatik), `LICENCE_*`
(faqat boshqa tashkilotlarга ijaraga berilgan nusxalar uchun).

---

## 3. Render + Neon (bulut)

1. Neon’da bepul PostgreSQL loyihasini yarating, ulanish satrini (`DATABASE_URL`)
   nusxalang.
2. Bu repozitoriyni GitHub’ga qo'ying. Render’da **New → Blueprint** orqali
   [`render.yaml`](../render.yaml) ni tanlang.
3. Render so'ragan `DATABASE_URL`, `BOT_TOKEN`, `SUPER_ADMIN_TELEGRAM_IDS` ni
   kiriting (`SECRET_KEY` o'zi yaratiladi).
4. Deploy tugagach, bot webhook’ini o'rnating va Mini App URL’ini BotFather’da
   ko'rsating (qadamlar [`TEST_HOSTING.md`](TEST_HOSTING.md) da).

`start.sh` har deployda avval `preflight` (sozlama tekshiruvi), so'ng
`alembic upgrade head` (baza yangilash), keyin serverni ishga tushiradi.

---

## 4. Institut serveri (Docker)

To'liq qo'llanma: [`INSTITUT_SERVERI.md`](INSTITUT_SERVERI.md). Qisqacha:

```bash
docker build -t kitobxon-hub .
docker run -d --name kitobxon-hub --restart unless-stopped \
    -p 8000:8000 --env-file .env kitobxon-hub
```

- `.env` da yuqoridagi o'zgaruvchilar bo'ladi.
- `STORAGE_BACKEND=local` va doimiy diskni (`-v /data/storage:/srv/backend/storage`)
  ulang; shu diskda zaxira nusxalar ham saqlanadi.
- Tasvirga `pg_dump`/`pg_restore` (postgresql-client) kiritilган.
- Oldiga HTTPS teskari proksi (nginx/Caddy) qo'ying.

---

## 5. Deploydan keyin

- `/health` manzili `200` qaytarishi kerak.
- Botга `/start` yuboring — ro'yxatdan o'tish ishlashi kerak.
- Admin panelga bosh admin sifatida kiring (bot → admin havolasi).
- To'liq ro'yxat: [`PRODUCTION_HANDOFF_CHECKLIST_UZ.md`](PRODUCTION_HANDOFF_CHECKLIST_UZ.md).

**Bog'liq:** [`DATABASE_MIGRATION_GUIDE_UZ.md`](DATABASE_MIGRATION_GUIDE_UZ.md),
[`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md),
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
