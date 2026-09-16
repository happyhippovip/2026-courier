#!/bin/bash
TARGET_DIR=$(cd ../.. && pwd)
mkdir -p "$TARGET_DIR/scripts/mac_worker/logs"
sed -e "s|TARGET_DIR|$TARGET_DIR|g" com.courier.mac_worker.plist > ~/Library/LaunchAgents/com.courier.mac_worker.plist
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist
echo "Mac worker installed to launchd and started."
