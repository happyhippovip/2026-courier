#!/bin/bash
set -e

echo "1. Creating runtime directory out of protected Downloads folder..."
RUNTIME_DIR="$HOME/.courier_runtime"
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR"

echo "2. Copying files to runtime..."
cp -r ../2026-courier/* "$RUNTIME_DIR/"

cd "$RUNTIME_DIR"

echo "3. Rebuilding virtual environment in runtime..."
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install flask gunicorn requests keyring >/dev/null 2>&1

echo "4. Setting up Mac LaunchAgents with new paths..."

# Worker Plist
sed -e "s|TARGET_DIR|$RUNTIME_DIR|g" scripts/mac_worker/com.courier.mac_worker.plist > ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "5. Starting fully automated local daemons..."
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "Runtime deployment complete! The Mac worker is now running from $RUNTIME_DIR."
