# Kitobxon Hub — Architecture

This document is the technical blueprint of Kitobxon Hub. It is written for the developers
who will maintain and deploy the system. A plain-language overview for the project owner
is in the [README](../README.md).

## 1. Goals and constraints

| Constraint | Consequence for the design |
|---|---|
| 500–2,000 registered users, growth possible | One modular monolith + PostgreSQL is enough; every module is isolated so it can be extracted later. |
| Low budget | One backend container + managed PostgreSQL + S3-compatible object storage. Redis is optional. No Kubernetes, no message broker. |
| Owner is not a programmer | Everything is automated: CI runs tests on every push, configuration is only environment variables, docs are step-by-step. |
| Telegram-first product | Telegram identity is the single identity of a member. Bot and Mini App share one backend and one database. |
| Official documents | Report statistics always come from SQL queries over verified records, never from AI. |

## 2. System overview

```
                 ┌────────────────────┐
  Telegram  ───► │  Telegram Bot API  │ ──── webhook (HTTPS) ────┐
  users          └────────────────────┘                          │
     │                                                           ▼
     │  opens   ┌────────────────────┐   REST /api/v1   ┌───────────────────────────────┐
     └────────► │  Mini App (React)  │ ───────────────► │  Backend (FastAPI, one image) │
                └────────────────────┘                  │                               │
                ┌────────────────────┐   REST /api/v1   │  • REST API  (/api/v1)        │
  Club admins ► │ Admin Panel (React)│ ───────────────► │  • Bot handlers (aiogram 3)   │
                └────────────────────┘                  │  • Background worker          │
                                                        │    (notification queue,       │
                                                        │     scheduled jobs)           │
                                                        │  • PDF generation             │
                                                        └──────┬───────────┬────────────┘
                                                               │           │
                                              ┌────────────────▼──┐   ┌────▼──────────────────┐
                                              │ PostgreSQL 16     │   │ S3-compatible storage  │
                                              │ (source of truth) │   │ (photos, PDF reports)  │
                                              └───────────────────┘   └───────────────────────┘
                                                     Optional: Redis (shared rate limits when
                                                     running several backend instances)
                                                     Optional: AI API (report wording only)
```

The **Bot, Mini App and Admin Panel are three user interfaces over the same service layer and
the same database.** There is no second database and no business logic in the frontends.

## 3. Technology decisions

| Area | Choice | Why |
|---|---|---|
| Language (backend) | Python 3.12 (3.11+ supported) | Required by the spec; one language for API, bot and jobs. |
| Web framework | FastAPI + Pydantic v2 | Async, automatic OpenAPI docs, strict validation. |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic | Mature, explicit transactions and locking. |
| DB driver | asyncpg | Fast async driver. Provider URLs (`postgres://…?sslmode=require`) are normalised automatically. |
| Database | PostgreSQL 16 | Constraints, partial indexes, `SKIP LOCKED` queues, triggers. |
| Telegram bot | aiogram 3, **webhook mode inside the backend process** | No separate server to pay for; handlers call the same services as the API. Polling mode exists for local development. |
| Background jobs | PostgreSQL-backed queue (`SELECT … FOR UPDATE SKIP LOCKED`) + in-process scheduler protected by a PostgreSQL advisory lock | Reliable, survives restarts, safe with several instances, no Celery/RabbitMQ to operate. |
| Cache / rate limit | In-memory by default, Redis when `REDIS_URL` is set | Single instance needs nothing extra; multi-instance deployments share limits through Redis. |
| Authentication | Telegram Mini App `initData` HMAC validation → short-lived JWT; Admin Panel login by one-time link sent by the bot | No passwords to leak; identity is always the verified Telegram account. |
| Authorization | RBAC: roles + permissions + per-admin permission grants, checked on every request | Spec section 7. |
| Frontends | React 19 + TypeScript + Vite + Tailwind CSS 4 | Small bundles, fast on low-end Android. Telegram WebApp JS API used directly (no heavy SDK). |
| File storage | S3-compatible API (Cloudflare R2 recommended: free 10 GB, no egress fees); local disk in development | Large files never stored in PostgreSQL. |
| PDF | HTML + CSS → PDF with WeasyPrint | Typographically clean official documents, templates are plain HTML. |
| AI drafting | Anthropic Claude API (optional, `AI_API_KEY`) | Only writes wording around facts supplied by the database. |
| Packaging | Docker image; `docker-compose.yml` for developers | Deployable to any VPS or PaaS. |
| CI | GitHub Actions | Lint + migrations + tests + frontend builds on every push. |

## 4. Repository structure

```
kitobxon-hub/
├── backend/                     Python backend (API + bot + worker)
│   ├── app/
│   │   ├── main.py              FastAPI application factory
│   │   ├── core/                config, logging, errors, middleware, database, redis
│   │   ├── api/                 HTTP layer
│   │   │   ├── health.py        /health, /health/db, /health/redis
│   │   │   └── v1/              /api/v1 routers (one module per domain)
│   │   ├── models/              SQLAlchemy models (one module per domain)
│   │   ├── schemas/             Pydantic request/response models
│   │   ├── services/            business logic (the only place that changes data)
│   │   ├── repositories/        reusable query helpers (rankings, statistics)
│   │   ├── security/            Telegram initData validation, JWT, permissions, rate limiting
│   │   ├── bot/                 Telegram bot: handlers, keyboards, middlewares, states, texts
│   │   ├── workers/             notification queue consumer and scheduled jobs
│   │   └── utils/               small helpers (time zones, text normalisation)
│   ├── migrations/              Alembic migrations
│   ├── tests/                   pytest suite (runs against real PostgreSQL)
│   ├── requirements.txt         pinned runtime dependencies
│   ├── requirements-dev.txt     test and lint tools
│   └── Dockerfile
├── miniapp/                     Telegram Mini App (React + TS + Vite + Tailwind)
│   └── src/{components,pages,layouts,hooks,services,store,types,utils}
├── admin/                       Admin web panel (React + TS + Vite + Tailwind)
│   └── src/{components,pages,layouts,hooks,services,store,types,utils}
├── docs/                        ARCHITECTURE, DATABASE, API, SECURITY, TESTING, DEPLOYMENT, ...
├── infra/                       nginx and deployment templates
├── scripts/                     maintenance scripts (backup, seed)
├── .github/workflows/ci.yml     continuous integration
├── docker-compose.yml           developer stack (PostgreSQL, Redis, backend)
└── .env.example                 every configuration variable, documented
```

Folders are created when the phase that needs them is implemented, so the repository never
contains empty placeholder modules.

**Deviation from the original specification:** the spec suggested a separate top-level `bot/`
project. The bot lives in `backend/app/bot/` instead. Reasons: (1) bot handlers must use exactly
the same business rules as the API (registration, attendance, scoring) — importing the service
layer is safer than duplicating it over HTTP; (2) in webhook mode the bot needs no extra server,
which keeps hosting free or cheap; (3) it can still run as its own process
(`python -m app.bot.polling`) if ever needed.

## 5. Layering rules

```
 HTTP routers / bot handlers / scheduled jobs      ← presentation: parse input, call a service
                 │
              services                               ← business rules, permissions, transactions
                 │
      repositories + SQLAlchemy models               ← data access
                 │
             PostgreSQL
```

* Only services change data. Each business operation is one database transaction
  (e.g. *attendance record + score transaction* commit together or not at all).
* Routers never trust client-supplied identities, scores, prices or correct answers.
* Permissions are checked in the API dependency **and** re-checked in services that
  are reachable from the bot.
* Services raise `AppError` subclasses; the API turns them into the standard error body,
  the bot turns them into a friendly Uzbek message.

## 6. Runtime processes

By default one container runs everything, which is the cheapest setup:

| Component | Default | Can be split out by |
|---|---|---|
| REST API | on | — |
| Bot webhook endpoint | on when `BOT_TOKEN` and `PUBLIC_BASE_URL` are set | — |
| Background worker (notification queue, reminders, quote of the day, test-ranking bonuses) | on | running a second container with the worker flag and disabling it in web containers |
| Static Mini App (`/app/`) and Admin Panel (`/admin/`) | served by the backend | a CDN or nginx |

Scheduled jobs take a PostgreSQL advisory lock, so even if several containers run the worker,
each job runs once. Notification sending uses `FOR UPDATE SKIP LOCKED`, so a message is never
sent twice by two workers, and respects Telegram's rate limits (~25 messages/second).

## 7. Key domain designs

### 7.1 Score ledger
`score_transactions` is an append-only ledger. Totals and rankings are always `SUM()` over it;
there is no editable "total score" column. Every transaction has a `category`
(ATTENDANCE, TEST, TEST_RANK_BONUS, BOOK_COMPLETION, CAMPAIGN, ACHIEVEMENT, MANUAL, REVERSAL),
a source reference and a unique `idempotency_key` (for example `attendance:<record id>`), so the
same business event can never award points twice. Corrections are new transactions that
reference the original, with a mandatory reason and an audit log entry.

### 7.2 Attendance
An admin opens an *attendance session* for an event. The admin screen shows a QR code and a
6-character code that rotate every ~30 seconds (each token valid ~60 seconds). Tokens are
128-bit random values; only their HMAC is stored. A member scans the QR in the Mini App (or types
the code). The backend checks: authenticated → event exists → session open → token valid,
for this event, not expired → member not yet checked in → rate limit. It then inserts the
attendance record and the score transaction in one transaction. `UNIQUE(event_id, user_id)`
guarantees a single record even under concurrent requests.

Honest limitation: a member physically present can send a photo of the QR to an absent friend
within its short lifetime. Mitigations: very short token lifetime, optional admin verification,
`SUSPICIOUS` marking, live attendance list for the admin, and the audit trail.

### 7.3 Tests
Correct answers never leave the server before submission. Starting a test creates an attempt with
a server timestamp and deadline; randomised question/option order is stored per attempt.
Answers after the deadline are rejected regardless of the client timer. Scores are computed only
on the server. Focus/visibility events are stored in `test_activity_logs` as *signals*, never
treated as proof.

### 7.4 Reports
Facts (dates, counts, names, percentages) are loaded by SQL into a snapshot stored with the report.
The AI only receives that snapshot plus the admin's own text and returns wording; numbers in the
draft are cross-checked against the snapshot before an admin can approve it. The PDF is rendered
from the approved text.

## 8. Decisions on gaps and contradictions in the specification

| Topic | Decision |
|---|---|
| In-app reading and reading timer | Removed by the owner. Books have title, author, cover and an external link. Reading status (READING / COMPLETED) is self-reported. |
| Book completion points (+10) vs. self-reported reading | Points are awarded only after verification (passing a related test or admin confirmation). Configurable in system settings. |
| READING_STREAK_7 / READING_STREAK_30 achievements | Cannot be measured without in-app reading. Replaced by streaks of verified activity (consecutive weeks with attendance or a passed test); the achievement engine stays configurable. |
| `ADMIN_SECRET` variable | Replaced by `SUPER_ADMIN_TELEGRAM_IDS` (bootstrap) and Telegram-based admin login — no shared password exists that could leak. |
| User status `PENDING` | New members become `ACTIVE` after registration. A setting can require admin approval, in which case they stay `PENDING`. |
| Faculty values | Stored in an admin-managed `faculties` table so faculty rankings are consistent; groups are normalised (trimmed, upper-case). |
| Test points vs. ledger points | The test's `max_score` (default 20 from settings) is what enters the ledger: `round(correct_points / total_points × max_score)`. Multiple-choice questions are all-or-nothing. If several attempts are allowed, the best attempt counts. |
| Attendance token reuse | A token is shared by everyone in the room during its short lifetime; each member can still check in only once per event. |
| Registration vs. attendance | Registration is not required to check in (walk-ins happen), but reports show both numbers separately. Configurable. |
| Ranking tie-break | 1) total points, 2) attendance points, 3) test points, 4) earlier time of reaching the total (time of last scoring transaction), 5) earlier registration. Weekly and monthly windows use the `Asia/Tashkent` calendar. |

## 9. Development phases

1. Project skeleton ✅ — 2. Database ✅ — 3. Authentication — 4. RBAC — 5. Telegram bot —
6. Mini App foundation — 7. Admin Panel foundation — 8. Users and profiles — 9. Books —
10. Events — 11. Attendance — 12. Tests — 13. Scoring — 14. Rankings — 15. Notifications —
16. Achievements — 17. Reports — 18. AI report drafting — 19. Rewards — 20. Analytics —
21. Security hardening — 22. Automated testing — 23. Deployment preparation.

## 10. Main technical risks

| Risk | Mitigation |
|---|---|
| Free hosting puts the server to sleep → slow first bot reply, scheduled reminders delayed | Acceptable for testing only; production uses an always-on server (documented in DEPLOYMENT.md). |
| Telegram broadcast limits (≈30 msg/s) | Queue with throttling and retries; no synchronous mass sending. |
| QR code forwarded to absent members | Short-lived rotating tokens, admin verification, suspicious marking. |
| AI inventing facts | Facts only from DB snapshot, numeric cross-check, mandatory human approval. |
| Personal data leakage | Permissions on every admin endpoint, phone/Telegram ID never public, privacy-aware logging, encrypted promo codes. |
| Data loss | Managed PostgreSQL backups + documented `pg_dump` procedure; object storage for files. |
| Dependency drift | Pinned versions, CI on every push. |
