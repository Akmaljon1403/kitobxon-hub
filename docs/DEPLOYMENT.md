# Deployment

Kitobxon Hub ships as **one Docker image** (root `Dockerfile`) containing the API, the Telegram
bot webhook, the Mini App (`/app/`) and the Admin Panel (`/admin/`). It needs a PostgreSQL
database and, for photos/PDFs (later phases), S3-compatible object storage. Redis is optional.

* Free test hosting for the project owner (Render + Neon): [TEST_HOSTING.md](TEST_HOSTING.md)
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
`API_DOCS_ENABLED`, `LOG_LEVEL`, `STORAGE_*`, `AI_*`, `WORKER_ENABLED` (default `true`),
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

* Enable automatic daily backups of the managed database (and point-in-time recovery if available).
* Additionally keep an off-site logical backup, e.g. a daily cron job on any machine:

```bash
pg_dump --format=custom --no-owner "$DATABASE_URL" > "kitobxon-$(date +%F).dump"
# keep 14 daily + 8 weekly copies in object storage
```

* Restore into an empty database:

```bash
pg_restore --no-owner --clean --if-exists --dbname "$TARGET_DATABASE_URL" kitobxon-YYYY-MM-DD.dump
```

* Test a restore at least once per semester. Object storage buckets should have versioning enabled.

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
