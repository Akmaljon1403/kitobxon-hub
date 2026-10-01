# Troubleshooting

> Loyiha egasi uchun bepul serverdagi muammolar: [TEST_HOSTING.md → Muammolar va yechimlar](TEST_HOSTING.md#muammolar-va-yechimlar).

Every API error contains a `request_id`; search the logs for it to find the full server-side trace.

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health/db` → 503 `DATABASE_UNAVAILABLE` | Wrong `DATABASE_URL`, database asleep/unreachable, firewall | Verify the URL with `psql "$DATABASE_URL" -c 'select 1'`; check provider status |
| Log: `Reference data bootstrap failed (are migrations applied?)` | Migrations not run | `cd backend && alembic upgrade head` (the container does it automatically unless `SKIP_MIGRATIONS=1`) |
| Startup error: `SECRET_KEY must be set ...` | Missing/weak secret in production | Set a random value of ≥ 32 characters |
| Bot silent | Webhook not registered, wrong token, or service asleep | Check logs for `Telegram webhook registered`; call `getWebhookInfo`; on free hosting wait ~1 min |
| `getWebhookInfo` shows `401 Unauthorized` as last error | `TELEGRAM_WEBHOOK_SECRET` / `SECRET_KEY` changed without restart | Restart the service (the webhook is re-registered with the current secret) |
| Mini App: `INIT_DATA_INVALID` | Mini App opened from a different bot, or `BOT_TOKEN` changed | Open the Mini App from the bot whose token is configured |
| Mini App: `INIT_DATA_EXPIRED` | The Mini App stayed open for more than 24 h | Close and reopen it |
| Mini App: `USER_NOT_REGISTERED` | The member has not finished registration | Send `/start` to the bot |
| Admin Panel: `ADMIN_SESSION_REQUIRED` | A member token is used on admin endpoints | Log in through `/admin` in the bot |
| `/admin` in the bot: "Admin panel manzili sozlanmagan" | `PUBLIC_BASE_URL` missing | Set it (Render sets `RENDER_EXTERNAL_URL` automatically) |
| 429 `RATE_LIMITED` | Too many attempts | Wait for the `Retry-After` seconds |
| 413 `PAYLOAD_TOO_LARGE` | Upload above 10 MB or request body above 4 MB | Use a smaller photo (reports accept up to 8 MB) |
| `/api/docs` returns 404 in production | API documentation is off in production by default | Set `API_DOCS_ENABLED=true` if you need it |
| *Security audit* workflow is red | A library has a published vulnerability | Update the library named in the log, run CI, deploy |
| `alembic check` fails in CI | Models changed without a migration | `alembic revision --autogenerate -m "..."`, review, commit |
| Tests fail with `DROP SCHEMA` permission error | `TEST_DATABASE_URL` user is not the schema owner | Use a dedicated, disposable database owned by the test user |
