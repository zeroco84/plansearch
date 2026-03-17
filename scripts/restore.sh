#!/bin/bash
# PlanSearch — Restore Database from Backup
#
# Usage: ./restore.sh /path/to/backup.sql.gz
#
# WARNING: This will restore the database, potentially overwriting existing data.

set -euo pipefail

BACKUP_FILE="${1:-}"
DB_CONTAINER="plansearch-postgres-1"
DB_NAME="plansearch"
DB_USER="plansearch"

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: ./restore.sh /path/to/backup.sql.gz"
    echo ""
    echo "Available backups:"
    ls -lh /data/backups/plansearch/plansearch_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "WARNING: This will restore the database from: ${BACKUP_FILE}"
echo "This may overwrite existing data."
read -p "Are you sure? (y/N) " confirm

if [ "${confirm}" != "y" ] && [ "${confirm}" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

echo "[$(date)] Restoring database from ${BACKUP_FILE}..."

cat "${BACKUP_FILE}" | docker exec -i "${DB_CONTAINER}" pg_restore \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges

if [ $? -eq 0 ]; then
    echo "[$(date)] Restore successful!"
else
    echo "[$(date)] Restore completed with warnings (some errors may be expected)."
fi
