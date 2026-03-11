# ──────────────────────────────────────────────
#  Stage 1: Builder
# ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps needed to compile certain packages (Pillow, psycopg2, phonenumbers, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libjpeg-dev libmagic1 zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ──────────────────────────────────────────────
#  Stage 2: Runtime
# ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# redis-tools provides redis-cli, used in entrypoint.sh to wait for Redis
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev libjpeg-dev libmagic1 zlib1g-dev redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy project source
COPY . .

# Copy entrypoint to /entrypoint.sh (container root, OUTSIDE /app).
# The .:/app volume mount cannot overwrite it there.
# sed strips Windows \r\n as a safety net.
RUN sed -i 's/\r//' /app/entrypoint.sh \
    && cp /app/entrypoint.sh /entrypoint.sh \
    && chmod +x /entrypoint.sh

RUN mkdir -p /app/staticfiles /app/media

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]