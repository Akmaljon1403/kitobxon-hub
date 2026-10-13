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
| Admin login | No passwords. Inside Telegram (bot → «🛠 Boshqaruv») the panel signs in with the admin's signed Telegram initData (`scope=admin`). On a computer: one-time links from the bot (valid 5 minutes, single use, only a SHA-256 hash is stored, token carried in the URL fragment so it never reaches server logs). |
| Admin vs member tokens | Admin endpoints require an admin-scoped token **and** a currently assigned ADMIN/SUPER_ADMIN role (checked on every request). |
| Bootstrap | Telegram IDs in `SUPER_ADMIN_TELEGRAM_IDS` receive SUPER_ADMIN on their next message to the bot or login; the grant is audited. |

## Authorization (RBAC)

* Roles: `SUPER_ADMIN` (everything), `ADMIN` (only the permissions granted), `USER` (members).
* Admin permissions are granted individually and/or through custom roles.
* Only SUPER_ADMIN manages admins, roles and permissions. The last SUPER_ADMIN cannot be removed.
* Each admin endpoint declares the permissions it needs; a blanket automated test checks that every
  `/api/v1/admin/*` route rejects anonymous (401) and member (403) requests.
* Phone numbers are a separate permission (`USER_CONTACT_VIEW`).
* Settings that move money or speak in the club's name (`payments.*`, `subscription.*`, `channel.chat_id`,
  `certificates.signer_*`, `certificates.seal`, `org.*`, `bot.*`) are changed by SUPER_ADMIN only, even by
  admins holding `SETTINGS_MANAGE` (`403 OWNER_ONLY_SETTING`); the settings list marks them `owner_only`.
  Payment wording in «📝 Matnlar» (card instructions, prices) is likewise SUPER_ADMIN only.
* Every super admin is told at once («🛡 Xavfsizlik», past the quiet hours) when one of those settings
  changes (the card number masked), when bot or channel wording is edited, and when anyone is appointed,
  dismissed, or given or refused permissions. Each of these is also in the audit log.
* A sign-in with a one-time link (a computer) is reported to that admin in the bot with «🔒 Barcha
  seanslarni yopish», which raises `token_version` and ends every session at once.
* The text editor is a regular, audited feature: edits live in `text_overrides`, are validated (only the
  placeholders the message knows, balanced Telegram HTML, at most 5 variants) and fall back to the wording in
  the code if a stored edit can no longer be rendered. There is no hidden or unaudited way in.

## Data integrity

* Score totals are never stored or accepted from clients; the ledger is append-only (database trigger)
  and every business fact has a unique idempotency key.
* Duplicate attendance is impossible at database level (`UNIQUE(event_id, user_id)`), also under
  concurrent requests (covered by a test).
* Correct test answers are never sent to the client before submission; deadlines use the server clock.
* The audit log is append-only (database trigger) and records actor, time, before/after values,
  reason, request id and client IP.

## Abuse protection

| What | Limit |
|---|---|
| `POST /auth/telegram` | 300 requests / minute / IP |
| `POST /auth/admin/exchange` | 30 requests / 5 minutes / IP |
| Every authenticated API call | 300 requests / minute / member |
| QR / code check-in | 10 requests / minute / member |
| Test answers and submission | 120 requests / minute / member |
| Test activity signals | 30 requests / minute / member |
| Telegram bot updates | 40 updates / minute / Telegram user |
| Request body | 4 MB (JSON), 10 MB (file uploads); larger requests get `413` |
| Club-wide messages to one member | `notifications.daily_limit` a day (6 by default) — news, reminders, quote of the day; answers, payments, attendance and admin broadcasts are not counted. Keeps the bot from being reported as spam. |
| A member's own missions | 15 created / hour, 10 kept at once |

Per-IP limits are deliberately generous: a whole lecture hall on the campus Wi-Fi, or many phones
behind a mobile operator's shared address, open the Mini App at the same moment. Guessing does not
help an attacker anyway (signed launch data, one-time admin links); the limits stop floods.
Limits are shared across instances when `REDIS_URL` is set; otherwise they apply per process.

The client IP comes from the platform's proxy (`X-Forwarded-For`, uvicorn `--proxy-headers`).
On a server where clients can reach uvicorn directly, set `FORWARDED_ALLOW_IPS` to the address of
your own reverse proxy (e.g. `127.0.0.1`) so that clients cannot fake their IP.

## HTTP security headers

| Area | Headers |
|---|---|
| Everything | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (camera, microphone, geolocation, payment, USB off); `Strict-Transport-Security` in production |
| API (`/api`, `/telegram`, `/health`) | `Cache-Control: no-store` (personal data never cached), `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` |
| Admin Panel (`/admin`) | Content-Security-Policy: scripts from the same origin and Telegram's `telegram-web-app.js`, API calls only to the same origin, `frame-ancestors https://web.telegram.org` (the panel opens inside Telegram from the bot; no other site may embed it), `object-src 'none'`, `base-uri 'none'` |
| QR verification page (`/v/<code>`) | `default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'`, `no-store`, `noindex`. Passport codes are HMAC-signed member numbers; certificate codes are 10 random characters (32^10). The page shows only what is printed on the document itself |
| Mini App (`/app`) | Same policy, plus Telegram's `telegram-web-app.js`. It may be framed, because Telegram Web shows Mini Apps in an iframe; a framed copy is useless to an attacker since signing in needs launch data signed by Telegram |

Images may come from any `https:` address (book covers are external links). Book links accept only
`http(s)` URLs, so a `javascript:` link cannot be stored.

## Files, exports and messages

* Report photos: only JPG/PNG/WEBP, at most 8 MB and 40 megapixels (checked from the header
  before decoding, so a small "image bomb" cannot exhaust memory), re-encoded, metadata (GPS)
  removed.
* CSV exports (attendance, test results) prefix cells that start with `=`, `+`, `-` or `@` with an
  apostrophe, so Excel never runs member-provided text as a formula.
* Every value placed into a Telegram message is HTML-escaped; an admin broadcast is escaped too.
* Promo codes never travel in messages; see *Promo codes* below.

## Secrets

* All secrets come from environment variables; `.env` files are git-ignored and `.env.example`
  contains no real values.
* In production the application refuses to start with a missing or weak `SECRET_KEY` (< 32 chars).
* Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
* Rotating `SECRET_KEY` logs everybody out (all tokens become invalid) — that is expected.
* Rotating `BOT_TOKEN` (via @BotFather) requires updating the variable and re-registering the webhook.

## Logging and privacy

* Logs are structured JSON with a request id. Query strings are never logged.
* A redaction filter removes bot tokens, bearer/JWT tokens, initData signatures, `password=`/
  `secret=`/`token=` values, the values inside PostgreSQL constraint errors
  (`Key (phone)=(...)`) and Uzbek phone numbers from every log line and stack trace.
* Error responses never contain stack traces, SQL or internal paths.
* Public rankings show a shortened name by default (`ranking.public_name_format = SHORT`);
  phone numbers and Telegram IDs are never public.
* Analytics show aggregates only; groups with fewer than three members are hidden, and the
  only list with names (inactive members) needs `USER_VIEW`.

## Dependencies

* Versions are pinned (`requirements.txt`, `package-lock.json`); the Docker image installs exactly
  those versions.
* `.github/workflows/security.yml` checks every library against public vulnerability databases
  each Monday (and when a dependency file changes in a pull request). Run it any time from the
  **Actions** tab → *Security audit* → *Run workflow*. Locally:
  `pip-audit -r backend/requirements.txt` and `npm audit --omit=dev` in `miniapp/` and `admin/`.

## Operator checklist (production)

1. `ENVIRONMENT=production`, strong `SECRET_KEY` (the app refuses to start otherwise).
2. HTTPS only (TLS terminated by the platform or nginx); HSTS is sent automatically.
3. API documentation (`/api/docs`) is off in production unless `API_DOCS_ENABLED=true` is set.
4. `TELEGRAM_WEBHOOK_SECRET` set, or left empty to derive it from `SECRET_KEY` (webhook calls
   without the right secret header are rejected).
5. Database user with access only to the Kitobxon Hub database; automatic backups enabled. Our own
   backups are encrypted (GnuPG AES-256) before they leave the runner; keep `BACKUP_PASSPHRASE`
   outside GitHub too.
6. Object storage bucket private (report files are only served through the authenticated API).
7. Restrict who can read production logs and database dumps.
8. Keep the *Security audit* workflow green; update a library when it turns red.
9. Give admins only the permissions they need (Admin Panel → Adminlar); review the audit log.

## Reporting a vulnerability

Contact the project owner privately; do not open a public GitHub issue for security problems.

## Promo codes

Codes are entered by administrators only (the system never generates "working" codes). They are
stored encrypted with AES-256-GCM using a key derived from `SECRET_KEY`, admins see them masked,
and a code is decrypted only for the member it was assigned to. A revoked assignment burns its
code. Note: changing `SECRET_KEY` makes stored codes unreadable — re-enter unused codes after a
key rotation.
