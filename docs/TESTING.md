# Testing

## What runs automatically

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | Checks |
|---|---|
| Backend | `ruff check`, `ruff format --check`, full `pytest` suite against PostgreSQL 16 (including migrations) |
| Frontend (miniapp, admin) | `npm ci`, TypeScript type check, production build |
| Docker | the production image (root `Dockerfile`) builds |

A green check mark on a commit means all of the above passed.

The Mini App and the Admin Panel are additionally checked by hand in headless Chromium at
phone and desktop sizes against a seeded local server (Telegram is simulated with correctly
signed `initData`) before each release.

## Running the backend tests locally

The suite uses a **real PostgreSQL database** because database constraints, row locking and
triggers are part of the behaviour under test (e.g. duplicate attendance protection).

```bash
cd backend
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kitobxon_test
pytest -q
```

The test database is wiped and rebuilt by the suite — never point `TEST_DATABASE_URL` at real data.
At the start of a run the schema is built by the real Alembic migrations (upgrade → downgrade →
upgrade), and before every test all tables are truncated and reference data is re-seeded.

## Test organisation

| File | Covers |
|---|---|
| `tests/test_phase1_foundation.py` | health checks, error format, request ids, log redaction, configuration parsing |
| `tests/test_phase2_database.py` | migrations up/down and drift check, reference data, unique constraints (Telegram ID, phone, attendance), concurrent check-ins, append-only ledger and audit log |
| `tests/test_phase3_auth.py` | initData signature/expiry/tampering, JWT forgery/expiry/`alg=none`, blocked users, logout, admin login links (one-time, expiry), super-admin bootstrap, login rate limit |
| `tests/test_phase4_rbac.py` | every admin route → 401 anonymous / 403 member, permission checks, admin appointment/dismissal with audit records, last super admin protection, custom roles, audit log filters |
| `tests/test_phase5_bot.py` | the real bot dispatcher driven through a fake Telegram connection: full registration, skipped faculty step, state surviving restarts, someone else's contact, typed phone, invalid names, duplicate phone, approval mode, owner bootstrap, main menu, profile, notification toggles, blocked users, `/admin` login link, webhook secret, faculty admin API |
| `tests/test_phase8_9_members_books.py` | profile editing, notification settings, member search (phone privacy, literal wildcards), corrections and status changes with audit, admin protection, typed settings, statistics, book lifecycle and visibility, URL/date validation, book permissions, reading status and one-time verified book points, quotes |
| `tests/test_phase10_11_events_attendance.py` | event CRUD and visibility, registration with capacity under concurrency, attendance by QR token and short code, expired / wrong-event / reused tokens, duplicate check-in (also 6 parallel requests → 1 record), points atomic with attendance, manual check-in, suspicious / revoke (points reversed) / restore, CSV export, bot deep-link check-in, rate limit |
| `tests/test_phase12_tests.py` | test editor validation and publishing, permissions, drafts hidden, correct answers never sent before close, correct → points / wrong → zero, all-or-nothing multiple choice, client-sent score ignored, answer validation, idempotent submit, parallel starts → one attempt, server deadline, **expired attempt rejects late answers** but keeps earlier ones, attempt limit, best attempt counted once, passing score, book verification by test, place bonuses once and review after close, scheduler closing, editing locked after attempts, activity signals, results, CSV |
| `tests/test_phase13_14_scores_rankings.py` | score breakdown, reversals counted against the original category and period, manual adjustment (permission, reason, audit with totals), members cannot submit scores, ranking order and every tie-break, determinism, week/month windows (Tashkent calendar), faculty/group scopes, inactive members excluded, name format, seasons |
| `tests/test_phase15_notifications.py` | sender: delivery with Mini App buttons, inactive members and opt-outs skipped, critical messages always sent, blocked bot / network error / rate limit handling, max attempts, **parallel senders never send twice**, outdated reminders skipped; announcements on publishing events and books, attendance opening, test results with places; event reminder offsets with dedup, test started/ending, reading reminders only in daytime, quote of the day once, switched-off templates, scheduler, broadcast with filters, preview and audit, worker loop |

The critical cases listed in the specification (expired QR, wrong-event QR, duplicate attendance,
expired test submission, wrong/correct answers, manipulated scores, duplicate transactions, 401/403
checks, manual correction permission, audit logging) each have a dedicated test.
