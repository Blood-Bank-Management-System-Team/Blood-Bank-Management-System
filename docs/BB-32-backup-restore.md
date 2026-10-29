# BB-32: Automated Database Backups

## Automated backups
The backup service uses PostgreSQL `pg_dump` to create timestamped
custom-format database backups in the `backups/` directory.

The service creates a backup after PostgreSQL becomes healthy and
then attempts another backup every 24 hours.

## Restore procedure

1. Identify the required `.dump` file inside `backups/`.
2. Stop the Django web service:

   docker compose stop web

3. Restore the chosen backup into the configured database:

   docker compose exec -T db pg_restore \
     --clean --if-exists --no-owner --no-privileges \
     -U "$DB_USER" -d "$DB_NAME" \
     < backups/REPLACE_WITH_BACKUP_FILE.dump

4. Start the web service again:

   docker compose start web

**Warning:** Restoring with `--clean` replaces existing database objects.
Verify the backup filename and protect current data before restoring.
