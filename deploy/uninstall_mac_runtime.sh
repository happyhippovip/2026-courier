#!/bin/bash
set -e

echo "1. Stopping and unloading Mac Worker launchd service..."
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
rm -f ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "2. Removing runtime directory..."
rm -rf "$HOME/.courier_runtime"

echo "Uninstall complete! Keychain credentials (if any) have been preserved."
