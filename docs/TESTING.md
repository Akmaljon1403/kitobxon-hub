# Testing

## What runs automatically

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | Checks |
|---|---|
| Backend | `ruff check`, `ruff format --check`, full `pytest` suite against PostgreSQL 16 (including migrations), **coverage at least 90 %** of `app/` (currently ~94 %) |
| Frontend (miniapp, admin) | `npm ci`, TypeScript type check, production build |
| Browser journeys | the built Mini App and Admin Panel served by a real backend and PostgreSQL, driven by Chromium (Playwright): see below; afterwards the database is backed up with `scripts/backup.sh`, restored into a new database and row counts are compared |
| Docker | the production image (root `Dockerfile`) builds |

A green check mark on a commit means all of the above passed. A separate weekly workflow,
*Security audit* (`.github/workflows/security.yml`), checks third-party libraries for published
vulnerabilities.

## Browser journeys (end-to-end)

`e2e/tests/journeys.spec.ts` runs in order, against the real application:

1. An admin signs in with a one-time link (API) and creates a book, a published event and a
   published two-question test through the admin API.
2. A registered member opens the Mini App (Telegram is replaced by a stand-in that hands over
   correctly signed launch data): home screen, current book, books list.
3. The admin opens attendance; the member types the short code and is checked in.
4. The member takes the test (questions are shuffled; answers are chosen by question text), gets
   2/2 and sees the results page.
5. The server-side totals add up (test 20 points, attendance points, total = sum of categories).
6. The admin signs in to the Admin Panel with another one-time link, sees the attendance list,
   the test results and the analytics page; the used link is refused a second time.
7. A stranger is sent to the bot to register; outside Telegram the Mini App says so.

Every page also fails the run on any browser error (including Content-Security-Policy
violations). On failure, CI keeps the Playwright report and traces as a downloadable artifact
for 7 days (*Actions* → the run → *Artifacts*).

Run locally (after building both apps and copying `dist/` into `backend/static/miniapp` and
`backend/static/admin`):

```bash
createdb kitobxon_e2e
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kitobxon_e2e \
  SECRET_KEY=e2e-only-secret-key-that-is-long-enough-0123456789 \
  BOT_TOKEN=123456789:E2E-fake-bot-token-AAAAAAAAAAAAAAAAAAAAAAAAAA BOT_MODE=disabled WORKER_ENABLED=false
cd backend && alembic upgrade head && PYTHONPATH=. python ../e2e/seed.py
cd ../e2e && npm ci && npx playwright install chromium && npx playwright test
```

The seed uses one-time admin links, so recreate the database before running again.

## Running the backend tests locally

The suite uses a **real PostgreSQL database** because database constraints, row locking and
triggers are part of the behaviour under test (e.g. duplicate attendance protection).

```bash
cd backend
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/kitobxon_test
pytest -q
pytest -q --cov --cov-report=term   # with coverage (as in CI)
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
| `tests/test_phase17_18_reports.py` | facts snapshot numbers from the database, permissions (create vs. approve), template draft → approval → official PDF content, **unknown numbers block approval** (admin-typed numbers allowed), AI draft with a fake client (only facts sent, fallback enabled, invented number caught), AI refusal, locking after approval, new versions, archive, PDF rebuilt when the file is lost, photo upload validation and resizing, draft preview with the photo embedded |
| `tests/test_phase19_rewards.py` | AES-GCM roundtrip and tamper detection, permission, codes stored encrypted / shown masked / deduplicated, assignment picks a valid unexpired code, duplicate and empty-pool errors, codes never in notifications or lists, only the recipient can reveal, delivered/redeemed tracking, revoked codes never reused, rewards without codes, idempotency key, inactive reward/member, **parallel assignments → one reward** |
| `tests/test_phase20_analytics.py` | Month windows across year boundaries in the club time zone, per-month series, headline numbers, points distribution, faculty averages, small groups hidden (privacy), test and book campaign rates, no names in aggregates; inactive list needs `USER_VIEW`, skips newcomers and active members, picks up members whose last activity is old |
| `tests/test_phase21_security.py` | Security headers on API and error responses, per-area header policy (admin not frameable, Mini App frameable for Telegram Web, HSTS only in production), oversized bodies rejected with 413 (declared and streamed), per-member API budget, CSV formula injection, broadcast escaping without a template, image bombs refused before decoding, phone numbers and constraint values redacted from logs, API docs off in production by default |
| `tests/test_phase22_consistency.py` | **all-or-nothing writes**: if awarding points fails, neither the attendance record nor the graded test is saved, the client gets a plain 500 without internals, and a retry succeeds |
| `tests/test_phase22_integrations.py` | AI service failures (bad key, rate limit, server error, no connection) become clear Uzbek messages, refusal / empty / cut-off answers, prompt contains only facts and admin notes; S3-compatible storage round trip; both web apps served with their security policies |
| `tests/test_phase23_system_status.py` | readiness checks: permission and no secrets in the output, a healthy production setup (local file storage flagged), missing public URL / unregistered webhook / no super admin / delayed messages explained, Telegram delivery errors and outages, CLI output and exit code |
| `tests/test_phase24_bot_sections.py` | bot menu: personal summaries (results with places, monthly top 3, current book with days left, next event, open test, achievements), old keyboard buttons; attendance opened automatically at the event time (once, not after an early close, finished sessions closed), code typed in the bot (lower case, spaces), open-attendance API; member → admin messages (only admins with `SUPPORT_MANAGE` notified, anonymous answers from the bot and the Admin Panel, photos, hourly limit, closed conversations), notification buttons |
| `tests/test_phase25_documents.py` | Kitobxon passport PNG (size, long names, broken photos, member number, Telegram photo fetched once and cached), QR verification page (forged codes, CSP), bot picture + file; certificates for test places 1–3 (only attendees for event tests, idempotent, switchable), monthly top 3 (time window, start month), manual issue/revoke, owner-only PDFs, PDF attached by the sender and redrawn when the file is lost; signed 5-minute download links; "send to chat" errors |
| `tests/test_phase16_achievements.py` | first attendance → achievement + message, idempotent unlocking with bonus points, book achievements only for verified reading, test master, longest weekly streak, monthly top three (first week only, once), inactive definitions, admin create / grant / revoke with permissions and audit, editing thresholds |
| `tests/test_phase15_notifications.py` | sender: delivery with Mini App buttons, inactive members and opt-outs skipped, critical messages always sent, blocked bot / network error / rate limit handling, max attempts, **parallel senders never send twice**, outdated reminders skipped; announcements on publishing events and books, attendance opening, test results with places; event reminder offsets with dedup, test started/ending, reading reminders only in daytime, quote of the day once, switched-off templates, scheduler, broadcast with filters, preview and audit, worker loop |

The critical cases listed in the specification each have a dedicated test:

| Case | Test |
|---|---|
| Expired QR → rejected | `test_phase10_11…::test_expired_qr_rejected` |
| Wrong event QR → rejected | `test_phase10_11…::test_wrong_event_qr_rejected` |
| Duplicate attendance → rejected | `test_phase10_11…::test_duplicate_check_in_rejected`, `test_phase2_database::test_duplicate_attendance_rejected_by_database` |
| Unauthenticated / invalid token → rejected | `test_phase10_11…::test_unauthenticated_check_in_rejected`, `::test_invalid_token_rejected` |
| Expired test → submission rejected | `test_phase12_tests::test_expired_attempt_rejects_answers_but_keeps_earlier_ones` |
| Wrong answer → zero, correct → points | `test_phase12_tests::test_correct_answers_earn_points_and_wrong_earn_zero` |
| Frontend-manipulated score → ignored | `test_phase12_tests::test_client_supplied_score_is_ignored` |
| Unauthorized admin endpoint → 403, unauthenticated → 401 | `test_phase4_rbac` (every admin route, automatically) |
| Duplicate transaction prevention | `test_phase2_database::test_score_idempotency_key_prevents_double_award`, `test_phase12_tests::test_submit_is_idempotent`, `::test_best_attempt_counts_once`, reward and achievement idempotency tests |
| Manual correction requires permission, audit record | `test_phase13_14…::test_manual_adjustment_requires_permission_reason_and_is_audited` |
| Attendance and points are atomic | `test_phase22_consistency::test_attendance_is_not_saved_when_points_fail` |
