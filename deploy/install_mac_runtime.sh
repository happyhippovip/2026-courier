#!/bin/bash
set -e

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

echo "1. Creating runtime directory out of protected Downloads folder..."
RUNTIME_DIR="$HOME/.courier_runtime"
mkdir -p "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR/scripts/mac_worker/state"
mkdir -p "$RUNTIME_DIR/scripts/mac_worker/logs"

# Backup state and logs before copying
if [ -d "$RUNTIME_DIR/scripts/mac_worker/state" ]; then
    cp -r "$RUNTIME_DIR/scripts/mac_worker/state" "/tmp/courier_state_backup" 2>/dev/null || true
fi
if [ -d "$RUNTIME_DIR/scripts/mac_worker/logs" ]; then
    cp -r "$RUNTIME_DIR/scripts/mac_worker/logs" "/tmp/courier_logs_backup" 2>/dev/null || true
fi

echo "2. Copying files to runtime..."
# Use rsync to update files without destroying untracked files like state/logs if possible, but cp -r will overwrite
mkdir -p "$RUNTIME_DIR/scripts"
cp -R "$PROJECT_ROOT/scripts/mac_worker" "$RUNTIME_DIR/scripts/"

# Restore state and logs
if [ -d "/tmp/courier_state_backup" ]; then
    cp -r "/tmp/courier_state_backup/"* "$RUNTIME_DIR/scripts/mac_worker/state/" 2>/dev/null || true
    rm -rf "/tmp/courier_state_backup"
fi
if [ -d "/tmp/courier_logs_backup" ]; then
    cp -r "/tmp/courier_logs_backup/"* "$RUNTIME_DIR/scripts/mac_worker/logs/" 2>/dev/null || true
    rm -rf "/tmp/courier_logs_backup"
fi

cd "$RUNTIME_DIR"

echo "3. Rebuilding virtual environment in runtime..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install requests keyring >/dev/null 2>&1

echo "4. Setting up Mac LaunchAgents with new paths..."

# Worker Plist
sed -e "s|TARGET_DIR|$RUNTIME_DIR|g" scripts/mac_worker/com.courier.mac_worker.plist > ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "5. Starting fully automated local daemons..."
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "Runtime deployment complete! The Mac worker is now running from $RUNTIME_DIR."
