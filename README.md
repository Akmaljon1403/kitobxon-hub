# 📚 Kitobxon Hub

Kitobxonlar klubi uchun raqamli boshqaruv platformasi: **Telegram bot + Telegram Mini App + Admin panel**.

## Bu nima? (oddiy tilda)

| Qism | Kim ishlatadi | Nima qiladi |
|---|---|---|
| **Telegram bot** | Klub a'zolari | Ro'yxatdan o'tish, eslatmalar, kun iqtiboslari, tezkor menyu |
| **Mini App** (Telegram ichidagi ilova) | Klub a'zolari | Kitoblar, tadbirlar, QR orqali davomat, testlar, reyting, yutuqlar |
| **Admin panel** (brauzerda) | Klub rahbarlari | Kitob/tadbir/test qo'shish, davomatni kuzatish, ballar, rasmiy PDF hisobotlar |
| **Backend (server)** | Hammasi uchun | Barcha qoidalar shu yerda tekshiriladi; ma'lumotlar bitta bazada saqlanadi |

Barcha qismlar **bitta server** va **bitta ma'lumotlar bazasi** bilan ishlaydi.

## Loyiha holati

| Bosqich | Holat |
|---|---|
| 1. Loyiha skeleti | ✅ Tayyor |
| 2. Ma'lumotlar bazasi | ✅ Tayyor |
| 3. Telegram orqali xavfsiz kirish | ✅ Tayyor |
| 4. Rollar va ruxsatlar (adminlar) | ✅ Tayyor |
| 5. Telegram bot (ro'yxatdan o'tish, menyu, admin havolasi) | ✅ Tayyor |
| 6. Mini App (Telegram ichidagi ilova) | ✅ Tayyor |
| 7. Admin panel | ✅ Tayyor |
| 8. A'zolar va profillar | ✅ Tayyor |
| 9. Kitoblar va iqtiboslar | ✅ Tayyor |
| 10. Tadbirlar | ✅ Tayyor |
| 11. QR davomat | ✅ Tayyor |
| 12. Testlar (taymer, avtomatik baholash) | ✅ Tayyor |
| 13. Ballar tizimi | ✅ Tayyor |
| 14. Reyting va mavsumlar | ✅ Tayyor |
| 15. Bildirishnomalar va eslatmalar | ✅ Tayyor |
| 16. Yutuqlar | ⏳ Keyingi |
| 17–23. Hisobotlar (PDF), AI yordamchi, sovg'alar, tahlillar, xavfsizlik, yakuniy tayyorgarlik | ⏳ Navbatda |

🚀 **Botni bepul serverda sinab ko'rish:** [docs/TEST_HOSTING.md](docs/TEST_HOSTING.md) — qadam-baqadam qo'llanma.

Har bir yangi kod GitHub'da avtomatik tekshiriladi (**Actions** bo'limi). Yashil ✅ belgisi — hamma testlar o'tdi degani.

## Hujjatlar

* [docs/TEST_HOSTING.md](docs/TEST_HOSTING.md) — botni bepul serverga joylab sinash (egasi uchun)
* [docs/SETUP.md](docs/SETUP.md) — loyihani ishga tushirish (egasi va dasturchilar uchun)
* [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — doimiy serverga joylash (dasturchilar uchun)
* [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — muammolar va yechimlar
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — texnik arxitektura (dasturchilar uchun, ingliz tilida)
* [docs/DATABASE.md](docs/DATABASE.md) — ma'lumotlar bazasi tuzilishi va ER-diagramma
* [docs/API.md](docs/API.md) — API qoidalari va endpointlar ro'yxati
* [docs/SECURITY.md](docs/SECURITY.md) — xavfsizlik
* [docs/TESTING.md](docs/TESTING.md) — avtomatik testlar

---

## For developers (quick start)

```bash
cp .env.example .env              # then edit values
docker compose up --build          # PostgreSQL + Redis + app on http://localhost:8000
                                   # Mini App: /app/   Admin Panel: /admin/   API docs: /api/docs
```

Without Docker (Python 3.11+, PostgreSQL 16):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload      # API docs: http://localhost:8000/api/docs
BOT_MODE=polling python -m app.bot.polling   # bot without a public URL (development)
pytest                             # needs TEST_DATABASE_URL pointing to an empty database
```

Frontends (Node.js 22):

```bash
cd miniapp && npm ci && npm run dev    # http://localhost:5173/app/
cd admin   && npm ci && npm run dev    # http://localhost:5174/admin/
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and all technical decisions.
