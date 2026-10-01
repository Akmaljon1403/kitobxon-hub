# Testing

## What runs automatically

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | Checks |
|---|---|
| Backend | `ruff check`, `ruff format --check`, full `pytest` suite against PostgreSQL 16 (including migrations) |
| Frontend (miniapp, admin) | `npm ci`, TypeScript type check, production build |
| Docker | the production image (root `Dockerfile`) builds |

A green check mark on a commit means all of the above passed.

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

New test modules are added with every phase (authentication, RBAC, attendance, tests, scoring, ...).
The critical cases listed in the specification (expired QR, wrong-event QR, duplicate attendance,
expired test submission, manipulated scores, 401/403 checks, audit logging) each get a dedicated test.
