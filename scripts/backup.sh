#!/bin/sh
# Автоматический бэкап PostgreSQL
# Запускается контейнером backup в docker-compose

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/backups/db_${TIMESTAMP}.sql.gz"

echo "[$(date)] Starting backup..."

pg_dump -h "$POSTGRES_HOST" -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup saved: $BACKUP_FILE"
else
    echo "[$(date)] ERROR: Backup failed!" >&2
    exit 1
fi

# Удалить бэкапы старше 7 дней
find /backups -name "db_*.sql.gz" -mtime +7 -delete
echo "[$(date)] Old backups cleaned."
