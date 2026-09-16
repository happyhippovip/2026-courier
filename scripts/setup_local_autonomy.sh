#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
TARGET_DIR=$(pwd)

echo "1. Setting up Courier Server LaunchAgent..."
cat << PLIST > ~/Library/LaunchAgents/com.courier.server.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.courier.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$TARGET_DIR/deploy/run-supervisor.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$TARGET_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$TARGET_DIR/logs/server_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$TARGET_DIR/logs/server_launchd.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/Users/user/.local/bin</string>
        <key>GITHUB_WORKER_ID</key>
        <string>GITHUB-DISPATCHER</string>
    </dict>
</dict>
</plist>
PLIST

mkdir -p logs

launchctl unload ~/Library/LaunchAgents/com.courier.server.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.courier.server.plist

echo "2. Setting up Mac Worker LaunchAgent..."
./scripts/mac_worker/install.sh

echo "Vollautomatik Background Services installed and running!"
