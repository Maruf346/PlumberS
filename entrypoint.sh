#!/bin/sh
set -e

echo "──────────────────────────────────────"
echo " PlumberS API — Starting up"
echo "──────────────────────────────────────"

# Wait for Redis to be ready (Celery and Channels depend on it)
echo "⏳ Waiting for Redis..."
until python -c "import redis; r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT); r.ping()" 2>/dev/null; do
    echo "   Redis not ready — retrying in 2s..."
    sleep 2
done
echo "✅ Redis is up."

# Run database migrations
echo "⏳ Running migrations..."
python manage.py migrate --noinput
echo "✅ Migrations complete."

# Collect static files
echo "⏳ Collecting static files..."
python manage.py collectstatic --noinput --clear
echo "✅ Static files collected."

# Start Daphne ASGI server
echo "🚀 Starting Daphne on 0.0.0.0:8000..."
exec daphne -b 0.0.0.0 -p 8000 core.asgi:application
