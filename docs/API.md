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
| Rate limits | `429 RATE_LIMITED` with a `Retry-After` header (seconds). |

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

More endpoints (books, events, attendance, tests, scores, rankings, notifications, reports,
rewards, analytics) are added in the following phases.
