# syntax=docker/dockerfile:1.7

###############################################################################
# Stage 1 — builder: install Python deps into an isolated virtualenv
###############################################################################
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build dependencies for any native wheels (psycopg[binary] ships wheels, but
# keep build-essential so source-builds don't break CI on arch mismatches)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

###############################################################################
# Stage 2 — runtime: minimal image with only the virtualenv + app code
###############################################################################
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings \
    PORT=5000

# Runtime OS deps: libpq for psycopg, curl for healthcheck, tini for PID 1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home --home-dir /home/app app

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy app source (respects .dockerignore)
COPY --chown=app:app . .

# Ensure entrypoint is executable and has LF line endings (Windows-safe)
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh \
    && chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app

USER app

# Collect static at build time so the image is self-contained.
# SECRET_KEY is only needed by Django's import machinery here — use a throwaway.
RUN DJANGO_SECRET_KEY=build-time-dummy DJANGO_DEBUG=False \
    python manage.py collectstatic --noinput

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/health/" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "3", \
     "--threads", "2", \
     "--worker-class", "gthread", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
