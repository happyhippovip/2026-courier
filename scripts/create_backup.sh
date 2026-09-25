#!/bin/bash
# Backup script for Courier working state

cd "$(dirname "$0")/.." || exit 1

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/courier_backup_${TIMESTAMP}.tar.gz"

echo "Creating backup: $BACKUP_FILE"

# Backup the core logic, state, deployment configs, and environment files
tar -czf "$BACKUP_FILE" \
    server/ \
    scripts/ \
    deploy/ \
    .env* \
    *.py \
    *.sh \
    2>/dev/null || true

echo "Backup completed successfully!"
ls -lh "$BACKUP_FILE"
