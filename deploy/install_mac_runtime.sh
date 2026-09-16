#!/bin/bash
set -e

echo "1. Creating runtime directory out of protected Downloads folder..."
RUNTIME_DIR="$HOME/.courier_runtime"
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR"

echo "2. Copying files to runtime..."
cp -r ../2026-courier/* "$RUNTIME_DIR/"
cp -r ../2026-courier/.env* "$RUNTIME_DIR/" 2>/dev/null || true

cd "$RUNTIME_DIR"

echo "3. Rebuilding virtual environment in runtime..."
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install flask gunicorn requests >/dev/null 2>&1

echo "4. Setting up Mac LaunchAgents with new paths..."
# Server Plist
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
        <string>$RUNTIME_DIR/deploy/run-supervisor.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$RUNTIME_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$RUNTIME_DIR/logs/server_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$RUNTIME_DIR/logs/server_launchd.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:$HOME/.local/bin</string>
        <key>GITHUB_WORKER_ID</key>
        <string>GITHUB-DISPATCHER</string>
    </dict>
</dict>
</plist>
PLIST

# Worker Plist
sed -e "s|TARGET_DIR|$RUNTIME_DIR|g" scripts/mac_worker/com.courier.mac_worker.plist > ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "5. Starting fully automated local daemons..."
launchctl unload ~/Library/LaunchAgents/com.courier.server.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.courier.server.plist

launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist

echo "Runtime deployment complete! The server is now running from $RUNTIME_DIR."
