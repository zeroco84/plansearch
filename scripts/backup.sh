#!/bin/bash
# PlanSearch — Daily Database Backup Script
#
# Run via cron: 0 4 * * * /path/to/backup.sh
#
# Backs up PostgreSQL to a compressed file in the backup directory.
# Retains 7 days of backups and removes older ones.

set -euo pipefail

# Configuration
BACKUP_DIR="/data/backups/plansearch"
DB_CONTAINER="plansearch-postgres-1"
DB_NAME="plansearch"
DB_USER="plansearch"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/plansearch_${TIMESTAMP}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting PlanSearch database backup..."

# Perform backup using pg_dump inside the Docker container
docker exec "${DB_CONTAINER}" pg_dump \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    > "${BACKUP_FILE}"

# Check if backup was successful
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Backup successful: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    echo "[$(date)] ERROR: Backup failed!"
    exit 1
fi

# Remove old backups (older than RETENTION_DAYS)
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "plansearch_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

# List remaining backups
echo "[$(date)] Current backups:"
ls -lh "${BACKUP_DIR}"/plansearch_*.sql.gz 2>/dev/null || echo "No backups found"

echo "[$(date)] Backup complete."
