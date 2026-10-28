#!/bin/sh
set -e

# Apply migrations on every start. Set RUN_MIGRATIONS=0 to skip (e.g. for extra replicas).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
