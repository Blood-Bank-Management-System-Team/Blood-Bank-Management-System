#!/usr/bin/env bash
set -Eeuo pipefail

BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"

if ! [[ "$BACKUP_INTERVAL_SECONDS" =~ ^[0-9]+$ ]] ||
   (( BACKUP_INTERVAL_SECONDS < 60 )); then
    echo "BACKUP_INTERVAL_SECONDS must be an integer of at least 60." >&2
    exit 1
fi

while true; do
    if /scripts/backup.sh; then
        echo "Backup job succeeded."
    else
        echo "Backup job failed; a future attempt will be made." >&2
    fi

    sleep "$BACKUP_INTERVAL_SECONDS"
done