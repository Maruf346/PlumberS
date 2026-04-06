#!/bin/bash
set -e

echo "=== PlumberS Production Entrypoint ==="
echo "Service: $SERVICE_TYPE"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
while ! nc -z "$DB_HOST" "${DB_PORT:-5432}" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

# Wait for Redis
echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
while ! nc -z "$REDIS_HOST" "${REDIS_PORT:-6379}" 2>/dev/null; do
    sleep 1
done
echo "Redis is ready."

if [ "$SERVICE_TYPE" = "django" ]; then
    echo "Running migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear

    echo "Starting Daphne ASGI server..."
    exec daphne -b 0.0.0.0 -p 8000 core.asgi:application

elif [ "$SERVICE_TYPE" = "celery_worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A core worker --loglevel=info --concurrency=2

elif [ "$SERVICE_TYPE" = "celery_beat" ]; then
    echo "Clearing stale beat schedule..."
    rm -f /app/celerybeat-schedule
    echo "Starting Celery beat..."
    exec celery -A core beat --loglevel=info

else
    echo "ERROR: Unknown SERVICE_TYPE='$SERVICE_TYPE'"
    exit 1
fi