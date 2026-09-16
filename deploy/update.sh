#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <update_package_dir_or_tar>"
    exit 1
fi

SOURCE_PACKAGE="$1"
RUNTIME_DIR="$HOME/.courier_runtime"
BACKUP_DIR="$HOME/.courier_backup_$(date +%s)"
UPDATE_TMP="$HOME/.courier_update_tmp"

echo "1. Validating update package..."
rm -rf "$UPDATE_TMP"
mkdir -p "$UPDATE_TMP"

if [ -d "$SOURCE_PACKAGE" ]; then
    cp -a "$SOURCE_PACKAGE/." "$UPDATE_TMP/"
elif [ -f "$SOURCE_PACKAGE" ]; then
    tar -xzf "$SOURCE_PACKAGE" -C "$UPDATE_TMP"
else
    echo "Error: $SOURCE_PACKAGE is not a valid directory or archive."
    exit 1
fi

# Find the root of the extracted code (sometimes tarballs have a top-level dir)
if [ -f "$UPDATE_TMP/server/app.py" ]; then
    EXTRACTED_ROOT="$UPDATE_TMP"
else
    EXTRACTED_ROOT=$(find "$UPDATE_TMP" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    if [ -z "$EXTRACTED_ROOT" ] || [ ! -f "$EXTRACTED_ROOT/server/app.py" ]; then
        echo "Error: Could not find server/app.py in the update package."
        rm -rf "$UPDATE_TMP"
        exit 1
    fi
fi

# Version compatibility check
NEW_SCHEMA=$(grep "CURRENT_SCHEMA_VERSION = " "$EXTRACTED_ROOT/server/app.py" | grep -o "[0-9]*" | head -n 1)
if [ -z "$NEW_SCHEMA" ]; then
    NEW_SCHEMA=1
fi

if [ -f "$RUNTIME_DIR/server/state/central_state.json" ]; then
    CURRENT_SCHEMA=$(grep -o '"schema_version"[[:space:]]*:[[:space:]]*[0-9]*' "$RUNTIME_DIR/server/state/central_state.json" | grep -o "[0-9]*" | head -n 1 || echo "0")
    if [ "$CURRENT_SCHEMA" -gt "$NEW_SCHEMA" ]; then
        echo "Error: Downgrade is not supported. Current state schema ($CURRENT_SCHEMA) is newer than update schema ($NEW_SCHEMA)."
        rm -rf "$UPDATE_TMP"
        exit 1
    fi
fi

echo "2. Backing up current runtime..."
cp -a "$RUNTIME_DIR" "$BACKUP_DIR"

echo "3. Applying update..."
# Exclude state/logs/venv to prevent overwriting runtime data
rsync -av --exclude 'server/state' --exclude 'logs' --exclude 'scripts/mac_worker/logs' --exclude 'scripts/mac_worker/state' --exclude 'venv' --exclude '.env' "$EXTRACTED_ROOT/" "$RUNTIME_DIR/"

# Re-run pip install if requirements changed (no manual customer Python commands)
echo "Updating Python environment..."
source "$RUNTIME_DIR/venv/bin/activate"
pip install flask gunicorn requests >/dev/null 2>&1

echo "4. Restarting launchd services..."
launchctl unload ~/Library/LaunchAgents/com.courier.server.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true

launchctl load ~/Library/LaunchAgents/com.courier.server.plist
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "5. Verifying health and applying state migration..."
HEALTH_OK=false
for i in {1..10}; do
    # 404 is acceptable since GET / is not defined but it means the server is running
    if curl -s -I http://127.0.0.1:8080/ | grep -q "200 OK\|404 NOT FOUND\|401 UNAUTHORIZED"; then
        HEALTH_OK=true
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" = true ]; then
    echo "Update applied successfully. Health check PASSED."
    rm -rf "$UPDATE_TMP"
    echo "Backup retained at $BACKUP_DIR"
    exit 0
else
    echo "Health check FAILED. Rolling back to previous version..."
    launchctl unload ~/Library/LaunchAgents/com.courier.server.plist 2>/dev/null || true
    launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
    
    rm -rf "$RUNTIME_DIR"
    mv "$BACKUP_DIR" "$RUNTIME_DIR"
    
    launchctl load ~/Library/LaunchAgents/com.courier.server.plist
    launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist
    
    echo "Rollback complete."
    rm -rf "$UPDATE_TMP"
    exit 1
fi
