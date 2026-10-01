# API

The complete, always up-to-date reference is generated from the code (OpenAPI):

* Swagger UI: `GET /api/docs`
* ReDoc: `GET /api/redoc`
* OpenAPI JSON: `GET /api/openapi.json`

This page explains the conventions and lists the endpoints implemented so far.

## Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1` (health checks live at `/health…`) |
| Format | JSON, UTF-8. Timestamps are ISO-8601 in UTC (`2026-10-01T10:00:00Z`). |
| Authentication | `Authorization: Bearer <access_token>` |
| Success | The resource itself (no envelope). Lists use `{"items": [...], "total", "limit", "offset"}`. |
| Errors | Always the envelope below, with a stable machine-readable `code` and a user-facing Uzbek `message`. |
| Request id | Every response has an `X-Request-ID` header; error bodies repeat it as `request_id`. |
| Rate limits | `429 RATE_LIMITED` with a `Retry-After` header (seconds). Limits are listed in [SECURITY.md](SECURITY.md#abuse-protection). |
| Body size | JSON bodies up to 4 MB, file uploads up to 10 MB; larger requests get `413 PAYLOAD_TOO_LARGE`. |
| Caching | API responses carry `Cache-Control: no-store`. |

```json
{
  "success": false,
  "error": {
    "code": "ATTENDANCE_EXPIRED",
    "message": "Davomat vaqti tugagan.",
    "request_id": "6f1c2d4e9a0b4c55a1f0e2b3c4d5e6f7"
  }
}
```

Validation errors (`422 VALIDATION_ERROR`) add `details: [{"field": "course", "reason": "..."}]`
but never echo the submitted values.

### Status codes

| Code | Meaning |
|---|---|
| 400 | Business rule violated (e.g. `UNKNOWN_PERMISSION`) |
| 401 | Not authenticated or the token/initData is invalid or expired |
| 403 | Authenticated but not allowed (`PERMISSION_DENIED`, `USER_BLOCKED`, `NOT_ADMIN`, …) |
| 404 | Not found |
| 409 | Conflict / already done (`ALREADY_ADMIN`, later `ALREADY_CHECKED_IN`) |
| 422 | Invalid input |
| 429 | Too many requests |
| 503 | A dependency (database, Redis, Telegram configuration) is unavailable |

## Authentication flows

### Mini App (members)

1. Telegram opens the Mini App and provides `window.Telegram.WebApp.initData`.
2. The Mini App sends it: `POST /api/v1/auth/telegram {"init_data": "<initData>"}`.
3. The backend verifies Telegram's HMAC signature with the bot token, checks `auth_date`
   (max age `INIT_DATA_MAX_AGE_SECONDS`, default 24 h), finds the registered member and returns
   `{"access_token", "expires_at", "scope": "member", "user": {...}}`.
4. The Mini App sends the token with every request. When it expires, it repeats step 2.

Error codes: `INIT_DATA_INVALID`, `INIT_DATA_EXPIRED`, `USER_NOT_REGISTERED`, `USER_BLOCKED`,
`USER_PENDING`, `USER_INACTIVE`.

### Admin Panel

Admins never have passwords. Two equivalent ways to obtain an **admin-scoped** token:

* **Login link from the bot:** the admin sends `/admin` to the bot, receives a one-time link
  (`/admin/#/login?token=…`, valid 5 minutes); the panel calls
  `POST /api/v1/auth/admin/exchange {"token": "…"}`.
* **Admin Panel opened inside Telegram:** `POST /api/v1/auth/telegram {"init_data": "…", "scope": "admin"}`.

Member-scoped tokens are rejected by every `/api/v1/admin/*` endpoint (`ADMIN_SESSION_REQUIRED`).

### Logout

`POST /api/v1/auth/logout` invalidates **all** tokens of the user (token version is incremented).
Blocking a user or removing admin rights has the same effect immediately.

## Endpoints

### Public

| Method | Path | Description |
|---|---|---|
| GET | `/health`, `/health/db`, `/health/redis` | Health checks |
| GET | `/api/v1/meta` | App name, version, bot username |

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/telegram` | — (rate limited) | Sign in with Mini App initData |
| POST | `/api/v1/auth/admin/exchange` | — (rate limited) | Exchange a one-time admin login link |
| POST | `/api/v1/auth/logout` | member/admin | Sign out everywhere |

### Member

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/me` | Own profile |
| PATCH | `/api/v1/me` | Correct own faculty, course, group (names are changed by admins) |
| GET / PUT | `/api/v1/me/notification-settings` | Reminder preferences |
| GET | `/api/v1/faculties` | Active faculties (public) |
| GET | `/api/v1/books` | Active and completed books with my reading status |
| GET | `/api/v1/books/{book_id}` | Book details with quotes |
| POST | `/api/v1/books/{book_id}/reading` | `{"action": "start" \| "complete"}` — self-reported reading status |
| GET | `/api/v1/events?scope=upcoming\|past` | Published, completed and cancelled events with my registration / attendance |
| GET | `/api/v1/events/{event_id}` | Event details |
| POST / DELETE | `/api/v1/events/{event_id}/register` | Register ("I intend to come") / cancel before the start |
| POST | `/api/v1/attendance/verify` | `{"token"}` (QR) or `{"code"}` (6 characters), optional `event_id`. Atomic with the points; 10 tries/min per member |
| GET | `/api/v1/tests` | Open, upcoming and closed tests with my attempts (never correct answers) |
| GET | `/api/v1/tests/{test_id}` | One test with my attempts |
| POST | `/api/v1/tests/{test_id}/start` | Start or resume: server fixes start, deadline = min(start + duration, test end) and the random order |
| GET | `/api/v1/tests/{test_id}/attempt` | My running attempt (after a reload) |
| POST | `/api/v1/tests/{test_id}/answer` | `{"question_id", "option_ids"}` — saved immediately; rejected after the deadline (+5 s network grace) |
| POST | `/api/v1/tests/{test_id}/submit` | Optional final `answers`; the server grades. Idempotent. A client-sent score is ignored |
| POST | `/api/v1/tests/{test_id}/activity` | Up to 30 focus/visibility signals (`VISIBILITY_HIDDEN`, `FOCUS_LOST`, ...) — hints, not proof |
| GET | `/api/v1/tests/{test_id}/review` | Correct answers and explanations — only after the test has closed (403 before) |
| GET | `/api/v1/me/scores` | Total, season total, breakdown by category and ledger history |
| GET | `/api/v1/me/ranking` | My place this week, month and overall |
| GET | `/api/v1/rankings?period=week\|month\|season\|all&scope=all\|faculty\|group` | Leaderboard (deterministic tie-breaks, see ARCHITECTURE §8) |
| GET | `/api/v1/rankings/faculties?period=...` | Faculties ranked by average points per member |
| GET | `/api/v1/me/achievements` | All active achievements with my progress and unlock dates |
| GET | `/api/v1/me/rewards` | My rewards (codes are never included in the list) |
| POST | `/api/v1/me/rewards/{id}/code` | Reveal my promo code (only the recipient; marks it delivered) |
| POST | `/api/v1/me/rewards/{id}/redeemed` | "I have used it" |

### Admin: access control

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/me` | any admin — returns roles and effective permissions |
| GET | `/api/v1/admin/permissions` | any admin — permission catalogue |
| GET | `/api/v1/admin/admins` | SUPER_ADMIN |
| POST | `/api/v1/admin/admins` | SUPER_ADMIN — appoint an admin with permissions |
| GET | `/api/v1/admin/admins/{user_id}` | SUPER_ADMIN |
| PUT | `/api/v1/admin/admins/{user_id}/permissions` | SUPER_ADMIN — replace direct permissions |
| PUT | `/api/v1/admin/admins/{user_id}/roles` | SUPER_ADMIN — replace roles |
| POST | `/api/v1/admin/admins/{user_id}/dismiss` | SUPER_ADMIN — remove admin rights (reason required) |
| GET / POST | `/api/v1/admin/roles` | SUPER_ADMIN — list / create custom roles |
| PATCH / DELETE | `/api/v1/admin/roles/{role_id}` | SUPER_ADMIN — update / delete custom roles |
| GET | `/api/v1/admin/audit-logs` | `AUDIT_LOG_VIEW` — filters: `action`, `entity_type`, `entity_id`, `actor_id`, `since`, `until` |

### Admin: members

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/users` | `USER_VIEW` — filters `search`, `status`, `faculty_id`, `course`, `group_name`; phone only with `USER_CONTACT_VIEW` |
| GET | `/api/v1/admin/users/{user_id}` | `USER_VIEW` |
| PATCH | `/api/v1/admin/users/{user_id}` | `USER_VIEW` + `USER_MANAGE` — correct names / study details (audited) |
| POST | `/api/v1/admin/users/{user_id}/status` | `USER_VIEW` + `USER_MANAGE` — `{"status", "reason"}`: approve, block, deactivate (audited) |

### Admin: books and quotes

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/books` | `BOOK_VIEW` |
| POST | `/api/v1/admin/books` | `BOOK_CREATE` |
| GET / PATCH | `/api/v1/admin/books/{book_id}` | `BOOK_VIEW` / `BOOK_EDIT` (status changes publish or archive) |
| DELETE | `/api/v1/admin/books/{book_id}` | `BOOK_DELETE` (soft delete) |
| GET | `/api/v1/admin/books/{book_id}/readers` | `BOOK_VIEW` |
| POST | `/api/v1/admin/books/{book_id}/readers/{user_id}/verify` | `BOOK_EDIT` — confirms reading, awards book points once |
| GET / POST | `/api/v1/admin/quotes` | `BOOK_VIEW` / `BOOK_CREATE` |
| PATCH / DELETE | `/api/v1/admin/quotes/{quote_id}` | `BOOK_EDIT` / `BOOK_DELETE` |

### Admin: events and attendance

| Method | Path | Required |
|---|---|---|
| GET / POST | `/api/v1/admin/events` | `EVENT_VIEW` / `EVENT_CREATE` |
| GET / PATCH | `/api/v1/admin/events/{event_id}` | `EVENT_VIEW` / `EVENT_EDIT` — publishing queues an announcement |
| DELETE | `/api/v1/admin/events/{event_id}` | `EVENT_DELETE` — only without attendance |
| GET | `/api/v1/admin/events/{event_id}/registrations` | `EVENT_VIEW` |
| GET | `/api/v1/admin/events/{event_id}/attendance` | `ATTENDANCE_VIEW` — live list and counts |
| POST | `/api/v1/admin/events/{event_id}/attendance/open` / `close` | `ATTENDANCE_MANAGE` — opening notifies registered members |
| GET | `/api/v1/admin/events/{event_id}/attendance/token` | `ATTENDANCE_MANAGE` — rotating QR payload and 6-character code for the projector |
| POST | `/api/v1/admin/events/{event_id}/attendance/manual` | `ATTENDANCE_MANAGE` — add a member (reason required) |
| PATCH | `/api/v1/admin/attendance/{record_id}` | `ATTENDANCE_MANAGE` — suspicious / revoke (points reversed) / restore |
| GET | `/api/v1/admin/events/{event_id}/attendance.csv` | `ATTENDANCE_VIEW` — Excel-friendly CSV |

### Admin: tests

| Method | Path | Required |
|---|---|---|
| GET / POST | `/api/v1/admin/tests` | `TEST_VIEW` / `TEST_CREATE` |
| GET / PATCH | `/api/v1/admin/tests/{test_id}` | `TEST_VIEW` (includes correct answers) / `TEST_EDIT` — max and passing score are locked once someone started |
| PUT | `/api/v1/admin/tests/{test_id}/questions` | `TEST_EDIT` — replace all questions; locked once someone started |
| POST | `/api/v1/admin/tests/{test_id}/publish` / `unpublish` | `TEST_PUBLISH` — publish validates every question; unpublish only before any attempt |
| POST | `/api/v1/admin/tests/{test_id}/close` | `TEST_PUBLISH` — grades unfinished attempts, awards place bonuses once, queues results |
| DELETE | `/api/v1/admin/tests/{test_id}` | `TEST_DELETE` — only without attempts |
| GET | `/api/v1/admin/tests/{test_id}/results` (`.csv`) | `TEST_VIEW` — places, scores, durations, signal counts |
| GET | `/api/v1/admin/test-attempts/{attempt_id}` | `TEST_VIEW` — answers and activity timeline |

### Admin: scores and seasons

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/scores?user_id=` | `SCORE_VIEW` — ledger (all members or one) |
| GET | `/api/v1/admin/scores/summary?user_id=` | `SCORE_VIEW` |
| POST | `/api/v1/admin/scores/adjust` | `SCORE_VIEW` + `SCORE_MANAGE` — `{"user_id", "amount", "reason"}`, audited with totals before/after |
| POST | `/api/v1/admin/scores/{transaction_id}/reverse` | `SCORE_VIEW` + `SCORE_MANAGE` — adds a REVERSAL entry (the ledger is append-only) |
| GET / POST | `/api/v1/admin/seasons` | `SCORE_VIEW` / `SEASON_MANAGE` |
| POST | `/api/v1/admin/seasons/{season_id}/activate` | `SEASON_MANAGE` |

### Admin: achievements

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/achievements` | any admin — definitions with holder counts |
| POST | `/api/v1/admin/achievements` | `SETTINGS_MANAGE` — new achievement (`code`, `criteria`, `threshold`, `points`, ...) |
| PATCH | `/api/v1/admin/achievements/{id}` | `SETTINGS_MANAGE` — title, description, icon, threshold, points, active, order (code and criteria are fixed) |
| GET | `/api/v1/admin/achievements/{id}/holders` | any admin |
| POST | `/api/v1/admin/achievements/{id}/grant` | `SCORE_VIEW` + `SCORE_MANAGE` — `{"user_id", "reason"}`, audited |
| POST | `/api/v1/admin/user-achievements/{id}/revoke` | `SCORE_VIEW` + `SCORE_MANAGE` — reason required; bonus points are reversed |

### Admin: reports

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/reports` | `REPORT_VIEW` |
| POST | `/api/v1/admin/reports` | `REPORT_VIEW` + `REPORT_CREATE` — `{"event_id"}`; loads the facts snapshot (next version for that event) |
| GET / PATCH | `/api/v1/admin/reports/{id}` | `REPORT_VIEW` / `REPORT_CREATE` — admin fields and `body_text`; detail includes `facts`, `photos`, `number_issues`, `ai_available` |
| POST | `/api/v1/admin/reports/{id}/refresh-facts` | `REPORT_CREATE` — reload facts (before approval) |
| POST | `/api/v1/admin/reports/{id}/generate` | `REPORT_CREATE` — `{"use_ai": true}` Claude draft (503 `AI_NOT_CONFIGURED` without `AI_API_KEY`), `false` template draft |
| POST | `/api/v1/admin/reports/{id}/approve` | `REPORT_APPROVE` — refused with `REPORT_UNVERIFIED_NUMBERS` while the text has numbers not in the facts or admin fields; renders and stores the PDF |
| GET | `/api/v1/admin/reports/{id}/pdf` | `REPORT_VIEW` — official PDF (rebuilt if the stored file is missing) |
| GET | `/api/v1/admin/reports/{id}/preview.pdf` | `REPORT_VIEW` — draft preview with a QORALAMA mark, not stored |
| POST | `/api/v1/admin/reports/{id}/new-version` / `archive` | `REPORT_CREATE` / `REPORT_APPROVE` |
| POST | `/api/v1/admin/reports/{id}/photos` | `REPORT_CREATE` — multipart `file` (JPG/PNG/WEBP ≤ 8 MB, max 8) + `caption` |
| GET / DELETE | `/api/v1/admin/reports/{id}/photos/{photo_id}` | `REPORT_VIEW` / `REPORT_CREATE` |

### Admin: rewards (`REWARD_MANAGE`)

| Method | Path | Notes |
|---|---|---|
| GET / POST | `/api/v1/admin/rewards` | list with code and recipient counts / create (`title`, `type`, `value`, `description`, `expires_at`, `status`) |
| PATCH | `/api/v1/admin/rewards/{id}` | edit |
| POST | `/api/v1/admin/rewards/{id}/codes` | `{"codes": [...], "expires_at"?}` — up to 500 admin-provided codes, encrypted (AES-GCM), duplicates skipped |
| GET | `/api/v1/admin/rewards/{id}/codes` | masked codes (`KI••••••CD`), status, recipient |
| POST | `/api/v1/admin/rewards/{id}/codes/{code_id}/revoke` | withdraw an unused code |
| POST | `/api/v1/admin/rewards/{id}/assign` | `{"user_id", "note"?, "idempotency_key"?}` — gives the next unused code; one active assignment per member and reward; audited; member notified |
| GET | `/api/v1/admin/rewards/{id}/recipients` | |
| POST | `/api/v1/admin/user-rewards/{id}/status` | `DELIVERED` / `REDEEMED` / `REVOKED` (a revoked code is never handed out again) |

### Admin: notifications

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/notifications/summary` | `NOTIFICATION_SEND` — queue state (pending, sent/failed/skipped in 24 h) and recent broadcasts |
| POST | `/api/v1/admin/notifications/broadcast` | `NOTIFICATION_SEND` — `{"message", "faculty_id"?, "course"?, "group_name"?, "with_app_button", "dry_run"}`; `dry_run` only counts recipients. Audited |

### Admin: system

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/settings` | any admin — values, defaults, input kind |
| PUT | `/api/v1/admin/settings/{key}` | `SETTINGS_MANAGE` — validated, audited |
| GET | `/api/v1/admin/statistics` | `ANALYTICS_VIEW` |
| GET | `/api/v1/admin/system/status` | `SETTINGS_MANAGE` — readiness checks `{summary, checked_at, checks: [{key, status: ok\|info\|warning\|error, title, detail}]}` (environment, public URL, migrations, database size, Telegram webhook, storage probe, delayed messages, super admins, AI). Never contains secrets |

### Admin: analytics

Aggregates only. Groups with fewer than 3 members are left out of group statistics.

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/analytics?months=6` | `ANALYTICS_VIEW` — `months` 3–24 (club time zone). Returns headline numbers (members, active / inactive in 30 days, test participants and average result), per-month series (new members, active members, verified attendance, events, completed books), points distribution, per-faculty averages, top groups, latest tests (participants, average %, pass rate) and reading campaigns (readers, completed, verified) |
| GET | `/api/v1/admin/analytics/inactive?days=30` | `ANALYTICS_VIEW` + `USER_VIEW` — active members with no attendance, test or book points for `days` (7–365) days; members who registered within that window are not listed. Max 200 rows |

### Admin: faculties

| Method | Path | Required |
|---|---|---|
| GET | `/api/v1/admin/faculties` | any admin |
| POST | `/api/v1/admin/faculties` | `SETTINGS_MANAGE` |
| PATCH | `/api/v1/admin/faculties/{faculty_id}` | `SETTINGS_MANAGE` — rename, reorder, deactivate (no hard delete) |

### Telegram

| Method | Path | Notes |
|---|---|---|
| POST | `/telegram/webhook` | Called by Telegram only; requires the `X-Telegram-Bot-Api-Secret-Token` header. Not part of the public API schema. |

### Static apps

| Path | Content |
|---|---|
| `/app/` | Telegram Mini App |
| `/admin/` | Admin Panel |

