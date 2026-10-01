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
| 2. Ma'lumotlar bazasi | ⏳ Navbatda |
| 3–23. Qolgan bosqichlar | ⏳ Navbatda |

Har bir yangi kod GitHub'da avtomatik tekshiriladi (**Actions** bo'limi). Yashil ✅ belgisi — hamma testlar o'tdi degani.

## Hujjatlar

* [docs/SETUP.md](docs/SETUP.md) — loyihani ishga tushirish (egasi va dasturchilar uchun)
* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — texnik arxitektura (dasturchilar uchun, ingliz tilida)
* [docs/TESTING.md](docs/TESTING.md) — avtomatik testlar

---

## For developers (quick start)

```bash
cp .env.example .env              # then edit values
docker compose up --build          # PostgreSQL + Redis + backend on http://localhost:8000
```

Without Docker (Python 3.11+, PostgreSQL 16):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload      # API docs: http://localhost:8000/api/docs
pytest                             # needs TEST_DATABASE_URL pointing to an empty database
```

Frontends (Node.js 22):

```bash
cd miniapp && npm ci && npm run dev    # http://localhost:5173/app/
cd admin   && npm ci && npm run dev    # http://localhost:5174/admin/
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and all technical decisions.
