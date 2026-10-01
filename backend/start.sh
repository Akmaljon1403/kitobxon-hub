#!/bin/sh
# Container entry point: apply database migrations, then start the web server.
# Set SKIP_MIGRATIONS=1 when migrations are run as a separate deployment step.
set -e
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
    alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
