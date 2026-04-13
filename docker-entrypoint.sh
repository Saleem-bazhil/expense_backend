#!/usr/bin/env sh
set -e

# Wait for PostgreSQL to be reachable (only when configured)
if [ "${DB_ENGINE:-sqlite}" = "postgres" ] || [ "${DB_ENGINE:-sqlite}" = "postgresql" ]; then
    echo "[entrypoint] Waiting for PostgreSQL at ${DB_HOST:-localhost}:${DB_PORT:-5432}..."
    python - <<'PY'
import os, socket, sys, time
host = os.getenv("DB_HOST", "localhost")
port = int(os.getenv("DB_PORT", "5432"))
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"[entrypoint] PostgreSQL reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1)
print(f"[entrypoint] ERROR: timed out waiting for {host}:{port}", file=sys.stderr)
sys.exit(1)
PY
fi

# Apply database migrations
echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

# Optional: auto-create a superuser from env vars (handy for first deploy)
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "[entrypoint] Ensuring superuser ${DJANGO_SUPERUSER_USERNAME} exists..."
    python manage.py createsuperuser --noinput --username "${DJANGO_SUPERUSER_USERNAME}" \
        --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

echo "[entrypoint] Starting: $*"
exec "$@"
