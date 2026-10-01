# Security

Kitobxon Hub stores personal data of students. This document describes how the system
protects it and what operators must do. Principle: **the frontend is only a user interface;
the backend verifies everything.**

## Identity and authentication

| Mechanism | Details |
|---|---|
| Member identity | The Telegram account. `telegram_id` is unique; the backend never accepts a Telegram ID sent by JavaScript. |
| Mini App login | Telegram `initData` is verified with HMAC-SHA256 (key derived from the bot token), compared in constant time; `auth_date` older than 24 h (configurable) or in the future is rejected. |
| Sessions | JWT (HS256), 24 h for members, 12 h for admins. The signing key is derived from `SECRET_KEY` for this purpose only. Tokens contain the user's `token_version`; logout, blocking or dismissal increments it and invalidates every token at once. |
| Admin login | No passwords. One-time links from the bot (valid 5 minutes, single use, only a SHA-256 hash is stored, token carried in the URL fragment so it never reaches server logs) or Telegram initData with `scope=admin`. |
| Admin vs member tokens | Admin endpoints require an admin-scoped token **and** a currently assigned ADMIN/SUPER_ADMIN role (checked on every request). |
| Bootstrap | Telegram IDs in `SUPER_ADMIN_TELEGRAM_IDS` receive SUPER_ADMIN on their next login; the grant is audited. |

## Authorization (RBAC)

* Roles: `SUPER_ADMIN` (everything), `ADMIN` (only the permissions granted), `USER` (members).
* Admin permissions are granted individually and/or through custom roles.
* Only SUPER_ADMIN manages admins, roles and permissions. The last SUPER_ADMIN cannot be removed.
* Each admin endpoint declares the permissions it needs; a blanket automated test checks that every
  `/api/v1/admin/*` route rejects anonymous (401) and member (403) requests.
* Phone numbers are a separate permission (`USER_CONTACT_VIEW`).

## Data integrity

* Score totals are never stored or accepted from clients; the ledger is append-only (database trigger)
  and every business fact has a unique idempotency key.
* Duplicate attendance is impossible at database level (`UNIQUE(event_id, user_id)`), also under
  concurrent requests (covered by a test).
* Correct test answers are never sent to the client before submission; deadlines use the server clock.
* The audit log is append-only (database trigger) and records actor, time, before/after values,
  reason, request id and client IP.

## Abuse protection

| Endpoint group | Limit |
|---|---|
| `POST /auth/telegram` | 20 requests / minute / IP |
| `POST /auth/admin/exchange` | 10 requests / 5 minutes / IP |

Limits are shared across instances when `REDIS_URL` is set; otherwise they apply per process.
Attendance verification, test submission and notification sending get their own limits in their phases.

## Secrets

* All secrets come from environment variables; `.env` files are git-ignored and `.env.example`
  contains no real values.
* In production the application refuses to start with a missing or weak `SECRET_KEY` (< 32 chars).
* Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
* Rotating `SECRET_KEY` logs everybody out (all tokens become invalid) — that is expected.
* Rotating `BOT_TOKEN` (via @BotFather) requires updating the variable and re-registering the webhook.

## Logging and privacy

* Logs are structured JSON with a request id. Query strings are never logged.
* A redaction filter removes bot tokens, bearer/JWT tokens, initData signatures and `password=`/
  `secret=`/`token=` values from every log line and stack trace.
* Error responses never contain stack traces, SQL or internal paths.
* Public rankings show a shortened name by default (`ranking.public_name_format = SHORT`);
  phone numbers and Telegram IDs are never public.

## Operator checklist (production)

1. `ENVIRONMENT=production`, strong `SECRET_KEY`, `API_DOCS_ENABLED` as desired.
2. HTTPS only (TLS terminated by the platform or nginx).
3. `TELEGRAM_WEBHOOK_SECRET` set (verifies that webhook calls come from Telegram).
4. Database user with access only to the Kitobxon Hub database; automatic backups enabled.
5. Object storage bucket private (files are served through short-lived signed URLs).
6. Restrict who can read production logs and database dumps.

## Reporting a vulnerability

Contact the project owner privately; do not open a public GitHub issue for security problems.
