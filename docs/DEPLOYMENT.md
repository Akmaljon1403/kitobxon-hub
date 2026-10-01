# Deployment

Kitobxon Hub ships as **one Docker image** (root `Dockerfile`) containing the API, the Telegram
bot webhook, the Mini App (`/app/`) and the Admin Panel (`/admin/`). It needs a PostgreSQL
database and, for report photos and PDFs, S3-compatible object storage. Redis is optional.

* Free test hosting for the project owner (Render + Neon): [TEST_HOSTING.md](TEST_HOSTING.md)
* Going live 24/7, step by step for the owner (Uzbek): [ISHGA_TUSHIRISH.md](ISHGA_TUSHIRISH.md)
* This page: production deployment for developers.

## 1. Recommended production setup (low cost, 24/7)

| Component | Recommendation | Approx. cost |
|---|---|---|
| Server | 1 VPS, 2 vCPU / 2–4 GB RAM (Hetzner, DigitalOcean, local UZ hosting) running Docker | $5–10 / month |
| Database | Managed PostgreSQL 16 with daily backups (or PostgreSQL on the same VPS + off-site `pg_dump`) | $0–15 / month |
| Object storage | Cloudflare R2 (10 GB free, no egress fees) or any S3-compatible bucket | $0–1 / month |
| TLS / proxy | nginx + Let's Encrypt (`infra/nginx/kitobxon-hub.conf`) or Caddy | free |
| Redis | Only if you run more than one app container | optional |

500–2,000 members fit comfortably on a single container. The design allows horizontal scaling
later (see §6).

## 2. Configuration

All configuration is environment variables; the full, commented list is in
[`.env.example`](../.env.example). Required in production:

| Variable | Notes |
|---|---|
| `ENVIRONMENT=production` | Enables production safety checks |
| `SECRET_KEY` | ≥ 32 random characters. Changing it logs everybody out. |
| `DATABASE_URL` | Any `postgres://` / `postgresql://` URL; `sslmode` is handled automatically |
| `PUBLIC_BASE_URL` | Public HTTPS origin, e.g. `https://kitobxon.example.uz` (on Render it defaults to `RENDER_EXTERNAL_URL`) |
| `BOT_TOKEN`, `BOT_USERNAME` | From @BotFather |
| `SUPER_ADMIN_TELEGRAM_IDS` | Comma-separated Telegram IDs of the owners |

Optional: `TELEGRAM_WEBHOOK_SECRET` (derived from `SECRET_KEY` when unset), `TELEGRAM_WEBAPP_URL`
(defaults to `PUBLIC_BASE_URL/app/`), `REDIS_URL`, `BOT_MODE` (`webhook` | `polling` | `disabled`),
`API_DOCS_ENABLED` (off in production unless set to `true`), `FORWARDED_ALLOW_IPS` (default `*`, right
for Render/Railway; on your own server set it to the reverse proxy's address, e.g. `127.0.0.1`), `LOG_LEVEL`, `STORAGE_*`, `AI_*`, `WORKER_ENABLED` (default `true`),
`WORKER_INTERVAL_SECONDS` (default `60`; how often reminders and test closing are checked),
`STORAGE_BACKEND` (`local` | `s3`) with `STORAGE_*` for report photos and PDFs — use `s3`
(e.g. Cloudflare R2) in production, because local files disappear when a container is rebuilt;
`AI_API_KEY` / `AI_MODEL` for optional AI report drafting (without a key the template draft is
used). The Docker image already contains Pango and the fonts needed for PDF rendering.

## 3. Deploying on a VPS with Docker

```bash
# on the server
git clone https://github.com/Akmaljon1403/kitobxon-hub.git && cd kitobxon-hub
cp .env.example .env && nano .env          # fill in the production values
docker build -t kitobxon-hub .
docker run -d --name kitobxon-hub --restart unless-stopped \
  --env-file .env -p 127.0.0.1:8000:8000 kitobxon-hub
curl -fsS http://127.0.0.1:8000/health
```

Then install nginx with `infra/nginx/kitobxon-hub.conf` (replace the domain) and obtain a
certificate with certbot. On start-up the container:

1. runs `alembic upgrade head` (skip with `SKIP_MIGRATIONS=1`; an advisory lock makes concurrent
   starts safe);
2. synchronises reference data (permissions, roles, default settings);
3. registers the Telegram webhook `PUBLIC_BASE_URL/telegram/webhook`, the bot commands and the
   Mini App menu button;
4. starts the background worker (unless `WORKER_ENABLED=false`): it sends queued Telegram
   messages (≤ 25/s, retries with backoff, honours Telegram's `retry_after`) and, every
   `WORKER_INTERVAL_SECONDS`, runs the scheduled checks — closing ended tests and awarding place
   bonuses, event reminders (`notifications.event_reminder_minutes`), "test started / closing
   soon", reading-deadline reminders (08:00–21:30 only) and the quote of the day.

On an always-on database keep the interval at 60 s. On a serverless database that bills compute
time (e.g. Neon's free plan) use a longer interval (the Render blueprint uses 1800 s) so the
database can scale to zero between checks; messages triggered by admins (attendance opened,
broadcasts, test results after a manual close) are still sent immediately.

### Updating

```bash
git pull && docker build -t kitobxon-hub . \
  && docker stop kitobxon-hub && docker rm kitobxon-hub \
  && docker run -d --name kitobxon-hub --restart unless-stopped --env-file .env -p 127.0.0.1:8000:8000 kitobxon-hub
```

Migrations are forward-only and applied automatically. Always take a database backup before
upgrading across several releases.

## 4. Telegram configuration

* The webhook is registered automatically on every start (idempotent). Telegram calls it with the
  `X-Telegram-Bot-Api-Secret-Token` header; requests without the correct secret are rejected (401).
* Check webhook status: `https://api.telegram.org/bot<TOKEN>/getWebhookInfo`.
* Local development without a public URL: `BOT_MODE=polling python -m app.bot.polling`
  (this removes the webhook; restart the production service afterwards to restore it).
* Optionally set the Mini App as the bot's main app in @BotFather (`/mybots → Bot Settings →
  Configure Mini App`) with the URL `PUBLIC_BASE_URL/app/`.

## 5. Backups and restore

Two independent layers:

1. **Provider backups.** Managed PostgreSQL providers keep their own history (Neon: point-in-time
   restore within the plan's history window). Enable the longest window your plan allows.
2. **Encrypted daily copies you own**, made by `scripts/backup.sh`:
   `pg_dump` (custom format) → GnuPG AES-256 with `PASSPHRASE` → integrity check
   (`pg_restore --list` on the decrypted stream). Backup files are created with mode 600.

### Automatic: GitHub Actions (no server needed)

`.github/workflows/backup.yml` runs every night at 02:13 Tashkent time (and on demand from the
**Actions** tab) and keeps each encrypted file for 30 days as a run artifact. Configure two
repository secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `BACKUP_DATABASE_URL` | the production `DATABASE_URL` (for Neon, the direct — not pooled — address is best) |
| `BACKUP_PASSPHRASE` | a long random password, also stored outside GitHub (password manager / sealed envelope) |

Until both exist the workflow stays green and prints a reminder. Scheduled workflows run on the
repository's **default branch**, so merge the code into it. `pg_dump` runs from the
`postgres:18` image (must not be older than the server; override with `PG_IMAGE`). CI exercises
the whole cycle (backup → verify → restore into a new database → compare row counts) on every push.

### On your own server (cron)

```bash
# /etc/cron.d/kitobxon-backup  — daily at 02:30, keep 14 days
30 2 * * * deploy cd /srv/kitobxon-hub && DATABASE_URL=... PASSPHRASE=... OUT_DIR=/srv/backups \
  scripts/backup.sh backup && find /srv/backups -name '*.dump.gpg' -mtime +14 -delete
```

Copy the files off the server as well (e.g. `rclone` to an R2 bucket with versioning).

### Restore

```bash
# 1. create a NEW empty database (provider dashboard or: createdb kitobxon_restored)
# 2. restore into it (asks for confirmation unless CONFIRM=yes)
export PASSPHRASE='...' TARGET_DATABASE_URL='postgresql://.../kitobxon_restored'
scripts/backup.sh restore kitobxon-2026-10-01-2113.dump.gpg
# 3. point DATABASE_URL of the service at the restored database and restart
```

`scripts/backup.sh verify FILE` only checks that a file decrypts into a valid dump. Practise a
restore once per semester. Report photos and PDFs live in object storage: enable bucket
versioning there (R2: lifecycle rules / object versioning).

## 5a. Files (Cloudflare R2)

Without object storage, report photos and PDFs are kept on the container disk and **disappear
when the service is rebuilt** (the Admin Panel's *Tizim holati* warns about it). With
Cloudflare R2 (10 GB free):

1. Cloudflare dashboard → R2 → *Create bucket* (e.g. `kitobxon-files`), location automatic.
2. R2 → *Manage API tokens* → *Create API token*, permission **Object Read & Write**, limited
   to that bucket. Copy the *Access Key ID*, *Secret Access Key* and the S3 endpoint
   (`https://<account-id>.r2.cloudflarestorage.com`).
3. Set on the service: `STORAGE_BACKEND=s3`, `STORAGE_ENDPOINT=<endpoint>`,
   `STORAGE_REGION=auto`, `STORAGE_BUCKET=kitobxon-files`, `STORAGE_ACCESS_KEY=…`,
   `STORAGE_SECRET_KEY=…`, then redeploy. The bucket stays private: files are only served
   through the authenticated API.

## 5b. Readiness check

* Admin Panel → **Sozlamalar** → *Tizim holati* (users with `SETTINGS_MANAGE`): environment,
  public URL, database and migration version, database size, Telegram webhook (including the
  last delivery error Telegram reports), file storage (write/read/delete probe), message queue
  delays, number of super admins, AI. Problems also appear as a banner on the dashboard.
* Command line (same checks, exit code 1 on errors):
  `docker exec kitobxon-hub python -m app.cli check` (or `python -m app.cli check` in `backend/`).

## 6. Scaling beyond one container

* Set `REDIS_URL` so rate limits are shared between instances.
* Bot conversation state is stored in PostgreSQL, so any instance can handle any update.
* The worker claims messages with `FOR UPDATE SKIP LOCKED` (plus a 5-minute lease) and runs each
  scheduled job under a transaction-level advisory lock (safe behind PgBouncer), so running it
  in several containers never duplicates work. For clarity you can run it in one dedicated
  container with `python -m app.workers` and set `WORKER_ENABLED=false` on the web containers.
* Put a connection pooler (PgBouncer, or the provider's pooled endpoint) in front of PostgreSQL;
  the app already disables prepared-statement caching for this.

## 7. Monitoring

| Check | How |
|---|---|
| Liveness | `GET /health` (also used by the Docker `HEALTHCHECK`) |
| Database | `GET /health/db` |
| Redis | `GET /health/redis` (`not_configured` when unused) |
| Logs | JSON lines on stdout with `request_id`; ship them to any log service. Secrets are redacted. |
| Uptime | Any HTTP monitor (UptimeRobot, Better Stack) on `/health` and `/health/db` |

## 8. Go-live checklist

- [ ] `ENVIRONMENT=production`, strong `SECRET_KEY`, `PUBLIC_BASE_URL` with HTTPS
- [ ] `BOT_TOKEN` set; *Tizim holati* shows the bot as receiving updates
- [ ] At least two super admins (`SUPER_ADMIN_TELEGRAM_IDS`, then Admin Panel → Adminlar)
- [ ] Object storage configured (`STORAGE_BACKEND=s3`), bucket private, versioning on
- [ ] Backup secrets configured; one manual *Database backup* run succeeded; one restore practised
- [ ] Uptime monitor on `/health` and `/health/db` (alerts by e-mail/Telegram)
- [ ] Organisation details filled in (Admin Panel → Sozlamalar → Tashkilot) for official reports
- [ ] Faculties checked, first book, event and test created; a test member went through the
      registration → check-in → test flow
- [ ] CI green on the deployed commit; *Security audit* workflow green

## 9. Handover notes for developers

* Read [ARCHITECTURE.md](ARCHITECTURE.md) first (layers, key designs and the decisions taken where
  the specification was ambiguous), then [DATABASE.md](DATABASE.md) and [API.md](API.md).
* Business rules live only in `backend/app/services/`; endpoints and bot handlers are thin.
  Points are only ever written through `services/scoring.award_points` (append-only ledger with
  idempotency keys); every admin change goes through `services/audit.record_audit`.
* Every pull request runs lint, the backend suite against PostgreSQL with a 90 % coverage gate,
  both frontend builds, the browser journeys (`e2e/`), a backup round trip and the Docker build
  ([TESTING.md](TESTING.md)).
* Schema changes: add an Alembic migration (`alembic revision --autogenerate`), review it; CI fails
  on model/migration drift. Migrations run automatically on start-up.
* Configuration is environment-only ([`.env.example`](../.env.example)); never commit secrets.
* Moving to a VPS: build the same image, run it behind nginx (`infra/nginx/`), point `DATABASE_URL`
  at the restored database, set `FORWARDED_ALLOW_IPS=127.0.0.1`.
