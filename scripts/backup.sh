#!/usr/bin/env bash
set -Eeuo pipefail

: "${DB_HOST:?DB_HOST must be set}"
: "${DB_NAME:?DB_NAME must be set}"
: "${DB_USER:?DB_USER must be set}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
    echo "BACKUP_RETENTION_DAYS must be a non-negative integer." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +'%Y%m%dT%H%M%SZ')"
backup_file="${BACKUP_DIR}/${DB_NAME}_${timestamp}.dump"
temporary_file="${backup_file}.tmp"

cleanup() {
    rm -f "$temporary_file"
}
trap cleanup EXIT

export PGPASSWORD="$DB_PASSWORD"

echo "Starting PostgreSQL backup: ${DB_NAME}"

pg_dump \
    --host="$DB_HOST" \
    --port="${DB_PORT:-5432}" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=custom \
    --no-password \
    --file="$temporary_file"

# Verify that the generated custom-format archive is readable.
pg_restore --list "$temporary_file" >/dev/null

# Publish the backup only after successful validation.
mv "$temporary_file" "$backup_file"
trap - EXIT

echo "Backup completed: ${backup_file}"

# Delete old backups only after the new backup succeeds.
find "$BACKUP_DIR" \
    -maxdepth 1 \
    -type f \
    -name "${DB_NAME}_*.dump" \
    -mtime "+${RETENTION_DAYS}" \
    -delete

unset PGPASSWORD