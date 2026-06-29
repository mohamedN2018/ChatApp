# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Multi-stage build for the ChatApp backend.
#   builder  -> compiles wheels for all Python deps
#   runtime  -> slim final image with only runtime libs + ffmpeg, non-root user
# Build arg REQUIREMENTS selects dev vs prod dependency set.
# ---------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12-slim

# ----------------------------- builder -------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system deps for compiling wheels (psycopg, Pillow, argon2, etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ARG REQUIREMENTS=production
WORKDIR /wheels
COPY requirements/ ./requirements/
RUN pip wheel --wheel-dir /wheels/dist -r requirements/${REQUIREMENTS}.txt

# ----------------------------- runtime -------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Runtime system deps: libpq (psycopg), ffmpeg (media processing), curl (healthcheck).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user.
RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

# Install pre-built wheels (no compilers in the final image).
ARG REQUIREMENTS=production
COPY --from=builder /wheels/dist /wheels/dist
COPY requirements/ ./requirements/
RUN pip install --no-index --find-links=/wheels/dist -r requirements/${REQUIREMENTS}.txt \
    && rm -rf /wheels

# Application code.
COPY --chown=app:app . .

# Entrypoint waits for services; CMD is provided by docker-compose per role.
COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER app

EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["gunicorn", "config.asgi:application", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
