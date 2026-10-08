#!/bin/bash
# Backup script for Courier working state.
# A tar error, including a partial archive, is not a completed backup.

cd "$(dirname "$0")/.." || exit 1

BACKUP_DIR="backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/courier_backup_${TIMESTAMP}.tar.gz"

echo "Creating backup: $BACKUP_FILE"

# Absent optional names are not passed to tar. A literal missing glob
# used to make tar fail while the script still reported success.
paths=()
for path in server scripts deploy; do
    if [ -e "$path" ]; then
        paths+=("$path")
    fi
done
shopt -s nullglob
for path in .env* *.py *.sh; do
    paths+=("$path")
done
shopt -u nullglob

if [ "${#paths[@]}" -eq 0 ]; then
    echo "Backup not proven: nothing to archive." >&2
    exit 1
fi

if ! tar -czf "$BACKUP_FILE" "${paths[@]}"; then
    rm -f "$BACKUP_FILE"
    echo "Backup not proven." >&2
    exit 1
fi

echo "Backup completed successfully!"
ls -lh "$BACKUP_FILE"
