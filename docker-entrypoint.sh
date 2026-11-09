#!/bin/sh
set -e

# Apply migrations on every start. Set RUN_MIGRATIONS=0 to skip (e.g. for extra replicas).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
    # Create the first admin when DJANGO_SUPERUSER_USERNAME/PASSWORD are set (no-op otherwise).
    python manage.py ensure_admin
fi

exec "$@"
