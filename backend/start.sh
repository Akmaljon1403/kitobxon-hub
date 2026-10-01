#!/bin/sh
# Container entry point: apply database migrations, then start the web server.
# Set SKIP_MIGRATIONS=1 when migrations are run as a separate deployment step.
set -e
# Stop early with a plain explanation if a variable is missing or wrong.
python -m app.cli preflight
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
    if ! alembic upgrade head; then
        echo "❌ Ma'lumotlar bazasiga ulanib yoki uni yangilab bo'lmadi. DATABASE_URL to'g'ri nusxalanganini" >&2
        echo "   (parol bilan, oxirigacha) va Neon loyihasi mavjudligini tekshiring. Yuqoridagi xato matnini" >&2
        echo "   dasturchiga yuboring." >&2
        exit 1
    fi
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-*}"
