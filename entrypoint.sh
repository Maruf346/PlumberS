#!/bin/sh
set -e

echo "────────────────────────────────────────"
echo "  PlumberS API — Starting up"
echo "────────────────────────────────────────"

# SERVICE_TYPE is set per-container in docker-compose.yml
# Values: "django" | "celery_worker" | "celery_beat"
SERVICE_TYPE="${SERVICE_TYPE:-django}"

# ── Wait for Redis (all services need it) ──────────────────────────────────
echo "⏳ Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."
until redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; do
    echo "   Redis not ready — retrying in 2s..."
    sleep 2
done
echo "✅ Redis is up."

# ── Django only: migrate + collectstatic + serve ───────────────────────────
if [ "$SERVICE_TYPE" = "django" ]; then
    echo "⏳ Running migrations..."
    python manage.py migrate --noinput
    echo "✅ Migrations complete."

    echo "⏳ Collecting static files..."
    python manage.py collectstatic --noinput --clear
    echo "✅ Static files collected."

    echo "🚀 Starting Daphne on 0.0.0.0:8000..."
    exec daphne -b 0.0.0.0 -p 8000 core.asgi:application

# ── Celery Worker ──────────────────────────────────────────────────────────
elif [ "$SERVICE_TYPE" = "celery_worker" ]; then
    echo "🚀 Starting Celery Worker..."
    exec celery -A core worker --loglevel=info --pool=solo

# ── Celery Beat ────────────────────────────────────────────────────────────
elif [ "$SERVICE_TYPE" = "celery_beat" ]; then
    echo "🚀 Starting Celery Beat..."
    exec celery -A core beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

else
    echo "❌ ERROR: Unknown SERVICE_TYPE='${SERVICE_TYPE}'. Must be: django | celery_worker | celery_beat"
    exit 1
fi