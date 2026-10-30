# Ishga tushirishdan oldingi tekshiruv ro'yxati (handoff)

Klub tizimini haqiqiy foydalanuvchilarга ochishdan oldin shu ro'yxatni bosqichma-bosqich
belgilang. Har bir band — bir martalik tekshiruv.

## 1. Server va sozlamalar

- [ ] `DATABASE_URL` to'g'ri (parol bilan, oxirigacha) va baza PostgreSQL 16+.
- [ ] `SECRET_KEY` — kuchli, tasodifiy (test qiymati emas).
- [ ] `BOT_TOKEN` — haqiqiy bot tokeni; `BOT_USERNAME` to'g'ri.
- [ ] `SUPER_ADMIN_TELEGRAM_IDS` — bosh admin(lar)ning ID'lari kiritilgan.
- [ ] `PUBLIC_BASE_URL` — ilovaning haqiqiy HTTPS manzili.
- [ ] `/health` manzili `200` qaytaryapti.
- [ ] `python -m app.cli preflight` xatosiz o'tdi (deployda avtomatik).

## 2. Baza

- [ ] `alembic current` eng so'nggi migratsiyani ko'rsatyapti (`alembic heads` bilan bir xil).
- [ ] Boshlang'ich ma'lumot (fakultetlar, sozlamalar) kiritilgan.
- [ ] Baza ulanishi ishlab chiqarish rejimida barqaror (pool sozlamalari).

## 3. Telegram

- [ ] Bot `webhook` rejimida va webhook URL to'g'ri o'rnatilgan.
- [ ] `TELEGRAM_WEBHOOK_SECRET` o'rnatilgan.
- [ ] Mini App URL BotFather'da ko'rsatilgan; ilova Telegram ichida ochilyapti.
- [ ] Botга `/start` → ro'yxatdan o'tish ishlayapti.
- [ ] (Agar kanal bor bo'lsa) kanal ID va bot kanalда admin ekani tekshirilgan.

## 4. Fayl xotirasi va zaxira

- [ ] Bulutда: `STORAGE_BACKEND=s3` va S3 sozlamalari to'g'ri (muqova/sertifikat/zaxira
      uchun **doimiy** xotira). Institut serverida: doimiy disk ulangan.
- [ ] `BACKUPS_ENABLED=true`; admin panelда «Zaxira nusxa» → «Hozir zaxira olish»
      bir marta sinab ko'rildi va fayl yuklab olindi.
- [ ] Tiklash tartibi o'qib chiqildi: [`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md).
- [ ] Muhim zaxira nusxasi serverdan tashqarida ham saqlanadigan joy belgilangan.

## 5. Adminlar va ruxsatlar

- [ ] Bosh admin panelга kira oladi.
- [ ] Oddiy adminlar kerakli rollar/ruxsatlar bilan qo'shilган.
- [ ] «Ishonch markazi» / «Audit jurnali» ishlayapti (amallar yozilyapti).

## 6. Asosiy jarayonlar (bir marta sinab ko'ring)

- [ ] Kitob qo'shish → Mini App'da ko'rinadi.
- [ ] A'zo kitob taklif qildi → admin «A'zolar takliflari»da ko'rib, e'lon qildi.
- [ ] Tadbir yaratish → e'lon → QR orqali davomat → «Javoblar» (RSVP) ko'rinadi.
- [ ] Test yaratish → a'zo ishlaydi → natija/reyting chiqadi.
- [ ] Rasmiy PDF hisobot yaratilyapti (Pango/shriftlar o'rnatilgan).

## 7. Ishonchlilik

- [ ] Fon ishchi (`WORKER_ENABLED=true`) ishlayapti; eslatmalar jo'nayapti.
- [ ] Loglar kuzatilyapti; xatolar ko'rinadigan joyga tushadi.
- [ ] CI (GitHub Actions) yashil — testlar, migratsiyalar, buildlar o'tgan.
- [ ] Qayta ishga tushirishдан keyin ma'lumotlar joyida (baza doimiy, disk doimiy).

## 8. Topshirishda hujjatlar

- [ ] [`DEPLOYMENT_GUIDE_UZ.md`](DEPLOYMENT_GUIDE_UZ.md) — qayerга va qanday qo'yilgani.
- [ ] [`DATABASE_MIGRATION_GUIDE_UZ.md`](DATABASE_MIGRATION_GUIDE_UZ.md) — bazani yangilash.
- [ ] [`BACKUP_RESTORE_GUIDE_UZ.md`](BACKUP_RESTORE_GUIDE_UZ.md) — zaxira va tiklash.
- [ ] [`BOSHQARUV_QOLLANMA.md`](BOSHQARUV_QOLLANMA.md) — kundalik boshqaruv (adminlar uchun).
- [ ] Barcha maxfiy ma'lumotlar (token, parollar) **xavfsiz** joyда, kodда emas.
