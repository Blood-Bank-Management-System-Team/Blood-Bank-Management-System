
#!/bin/sh
set -eu

# BB-32: Automated PostgreSQL database backup

: "${DB_NAME:?DB_NAME must be set}"
: "${DB_USER:?DB_USER must be set}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"

DB_HOST="${DB_HOST:-db}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/bbms_${TIMESTAMP}.dump"
TEMP_FILE="${BACKUP_FILE}.tmp"

mkdir -p "$BACKUP_DIR"

export PGPASSWORD="$DB_PASSWORD"
trap 'unset PGPASSWORD; rm -f "$TEMP_FILE"' EXIT HUP INT TERM

echo "Starting PostgreSQL backup..."

pg_dump \
  --host="$DB_HOST" \
  --username="$DB_USER" \
  --dbname="$DB_NAME" \
  --format=custom \
  --file="$TEMP_FILE"

mv "$TEMP_FILE" "$BACKUP_FILE"

unset PGPASSWORD
trap - EXIT HUP INT TERM

echo "Backup completed successfully: $BACKUP_FILE"
