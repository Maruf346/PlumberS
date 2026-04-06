#!/bin/bash
set -e

echo "Starting service: $SERVICE_TYPE"

if [ "$SERVICE_TYPE" = "django" ]; then
    echo "Running migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Starting Daphne..."
    exec daphne -b 0.0.0.0 -p 8000 core.asgi:application

elif [ "$SERVICE_TYPE" = "celery_worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A core worker -l info

elif [ "$SERVICE_TYPE" = "celery_beat" ]; then
    echo "Starting Celery beat..."
    rm -f /app/celerybeat-schedule
    exec celery -A core beat -l info

else
    echo "ERROR: Unknown SERVICE_TYPE=$SERVICE_TYPE"
    exit 1
fi