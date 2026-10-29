# Database Backup and Restore

## Overview

The BBMS Docker deployment uses PostgreSQL 16. A dedicated backup service runs a database dump immediately after startup and repeats at the configured interval.

Backups use PostgreSQL's custom dump format and are stored in a separate Docker volume named `backupdata`.

## Configuration

The following environment variables control backup behavior:

| Variable | Default | Purpose |
|---|---|---|
| `BACKUP_INTERVAL_SECONDS` | `86400` | Time between backup attempts |
| `BACKUP_RETENTION_DAYS` | `7` | Age after which old backups are removed |
| `BACKUP_DIR` | `/backups` | Directory for backup files |

## Verify the backup service

Start the stack:

```bash
docker compose up -d --build
```

Check the service logs:

```bash
docker compose logs backup
```

List available backup files:

```bash
docker compose exec backup ls -lh /backups
```

A completed backup has a filename similar to:

`bbms_20261029T120000Z.dump`

The actual filename depends on the database name and UTC time.

## Restore a backup

**Warning:** A restore can overwrite database contents. Always verify the selected backup and target database before restoring. Test recovery in a separate database first.

### 1. List and inspect available backups

```bash
docker compose exec backup ls -lh /backups
```

Inspect the selected archive:

```bash
docker compose run --rm --entrypoint /bin/bash backup -c \
  'pg_restore --list /backups/REPLACE_WITH_BACKUP_FILENAME.dump'
```

Replace `REPLACE_WITH_BACKUP_FILENAME.dump` with the actual backup filename.

### 2. Create a separate test database

```bash
docker compose exec -T db psql -U "$DB_USER" -d postgres \
  -c "CREATE DATABASE bbms_restore_test OWNER bbms;"
```

Run this command from a shell where the database username is configured, or replace `$DB_USER` with the PostgreSQL username. If the test database already exists, use a different test database name rather than deleting it blindly.

### 3. Restore the backup into the test database

```bash
docker compose run --rm --entrypoint /bin/bash backup -c \
  'export PGPASSWORD="$DB_PASSWORD"; pg_restore --exit-on-error --no-owner --no-privileges --host="$DB_HOST" --port="${DB_PORT:-5432}" --username="$DB_USER" --dbname=bbms_restore_test /backups/REPLACE_WITH_BACKUP_FILENAME.dump'
```

Replace the placeholder with the actual backup filename. The restore command exits with an error if a restore operation fails.

### 4. Verify the restored database

List the restored tables:

```bash
docker compose exec -T db psql -U bbms -d bbms_restore_test -c "\dt"
```

For additional verification, check the table counts or application data expected from the backup.

### 5. Restore the production database only when necessary

For a recovery that replaces the existing database contents:

1. Confirm the backup filename and target database.
2. Stop the web application to prevent writes:
   ```bash
   docker compose stop web
   ```
3. Ensure a separate, verified backup of the current database is available if its data must be preserved.
4. Follow the approved recovery procedure to restore the selected dump into the intended database. Use `pg_restore --clean --if-exists` only when replacing existing objects is intended.
5. Verify the restored database, restart the application, and check its logs:
   ```bash
   docker compose up -d web
   docker compose logs --tail=100 web
   ```
6. Perform a basic application health and functionality check.

## Operational and security notes

- A backup stored on the same host is not sufficient protection against host or disk loss. Copy important backups to secure external storage.
- Restrict access to backup files because they may contain sensitive donor and hospital data.
- Protect database credentials and never commit `.env` files or dump files.
- Test recovery periodically in a separate, non-production database.
- Monitor backup logs and ensure failed backups are investigated.
- The retention policy deletes older local backups; it does not replace an off-host retention policy.