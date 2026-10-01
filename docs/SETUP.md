# Ishga tushirish / Setup

## 1. Loyiha egasi uchun (kompyuteringizga hech narsa o'rnatish shart emas)

Siz hech qanday dastur o'rnatmaysiz. Kod yozish, tekshirish va saqlash bulutda bajariladi:

* **Kod** shu GitHub repository'da saqlanadi.
* **Avtomatik tekshiruv:** har safar kod yangilanganda GitHub o'zi testlarni ishga tushiradi.
  Tekshirish uchun: repository sahifasida **Actions** bo'limini oching.
  * ✅ yashil belgi — hammasi joyida;
  * ❌ qizil belgi — xatolik bor (buni dasturchi/AI tuzatadi).
* **Botni sinab ko'rish** uchun bepul serverga joylashtirish qo'llanmasi bot tayyor bo'lganda
  (5-bosqich) shu yerga qo'shiladi: [DEPLOYMENT.md](DEPLOYMENT.md).

Sizdan faqat quyidagilar so'raladi (vaqti kelganda, oddiy savol shaklida):

1. Telegram'da **@BotFather** orqali bot yaratish va uning tokenini berish.
2. Universitetingizdagi **fakultetlar ro'yxati**.
3. Bepul xizmatlarda (ma'lumotlar bazasi, server) ro'yxatdan o'tish — qadam-baqadam ko'rsatiladi.

## 2. For developers

### Requirements
* Python 3.11+ (3.12 recommended)
* PostgreSQL 16 (or Docker)
* Node.js 22 (only to build the frontends)
* Redis is optional

### Option A — Docker
```bash
cp .env.example .env
docker compose up --build
curl http://localhost:8000/health
```

### Option B — Python virtual environment
```bash
cd backend
python -m venv .venv
. .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp ../.env.example ../.env       # set DATABASE_URL and SECRET_KEY
uvicorn app.main:app --reload
```

Useful URLs:

| URL | Purpose |
|---|---|
| `GET /health` | liveness |
| `GET /health/db` | database connectivity |
| `GET /health/redis` | Redis connectivity (`not_configured` when Redis is not used) |
| `/api/docs` | interactive OpenAPI documentation |

### Frontends
```bash
cd miniapp && npm ci && npm run dev    # proxies /api to http://localhost:8000
cd admin   && npm ci && npm run dev
```
