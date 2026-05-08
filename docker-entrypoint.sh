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

# Print key runtime settings that commonly cause deploy-only browser failures.
python - <<'PY'
import django

django.setup()

from django.conf import settings

print(f"[entrypoint] CORS_ALLOW_ALL_ORIGINS={settings.CORS_ALLOW_ALL_ORIGINS}")
print("[entrypoint] CORS_ALLOWED_ORIGINS=" + ",".join(settings.CORS_ALLOWED_ORIGINS))
PY

# Optional: auto-create a superuser from env vars (handy for first deploy)
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    echo "[entrypoint] Ensuring superuser ${DJANGO_SUPERUSER_USERNAME} exists..."
    python - <<'PY'
import os

import django

django.setup()

from django.contrib.auth import get_user_model

username = os.environ["DJANGO_SUPERUSER_USERNAME"]
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]
email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

User = get_user_model()
user, created = User.objects.get_or_create(
    username=username,
    defaults={
        "email": email,
        "is_staff": True,
        "is_superuser": True,
    },
)

if created:
    user.set_password(password)
    user.save(update_fields=["password"])
    print(f"[entrypoint] Created superuser {username}")
else:
    changed_fields = []
    if email and not user.email:
        user.email = email
        changed_fields.append("email")
    if not user.is_staff:
        user.is_staff = True
        changed_fields.append("is_staff")
    if not user.is_superuser:
        user.is_superuser = True
        changed_fields.append("is_superuser")
    if changed_fields:
        user.save(update_fields=changed_fields)
        print(f"[entrypoint] Updated superuser {username}: {', '.join(changed_fields)}")
    else:
        print(f"[entrypoint] Superuser {username} already exists")
PY
fi

echo "[entrypoint] Starting: $*"
exec "$@"
