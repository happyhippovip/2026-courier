#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
TARGET_DIR=$(pwd)

# Credentials must come from the environment; never hard-code them here.
if [ -z "${COURIER_API_KEY// /}" ] || [ -z "${COURIER_VERIFIER_API_KEY// /}" ]; then
    echo "ERROR: COURIER_API_KEY and COURIER_VERIFIER_API_KEY must be set; aborting before any changes." >&2
    exit 1
fi

# Do not report the services running unless launchctl actually loaded them.
if ! command -v launchctl >/dev/null 2>&1; then
    echo "Background services not proven: launchctl is not available." >&2
    exit 1
fi

echo "1. Setting up Courier Server LaunchAgent..."
mkdir -p "$HOME/Library/LaunchAgents" logs
cat << PLIST > "$HOME/Library/LaunchAgents/com.courier.server.plist"
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
        <key>COURIER_API_KEY</key>
        <string>${COURIER_API_KEY}</string>
        <key>COURIER_VERIFIER_API_KEY</key>
        <string>${COURIER_VERIFIER_API_KEY}</string>
        <key>GITHUB_WORKER_ID</key>
        <string>GITHUB-DISPATCHER</string>
    </dict>
</dict>
</plist>
PLIST

# Nothing to unload on a first install. A failed load is not "running".
launchctl unload "$HOME/Library/LaunchAgents/com.courier.server.plist" 2>/dev/null || true
if ! launchctl load "$HOME/Library/LaunchAgents/com.courier.server.plist"; then
    echo "Background services not proven: server LaunchAgent did not load." >&2
    exit 1
fi

echo "2. Setting up Mac Worker LaunchAgent..."
export COURIER_API_KEY
if ! ./scripts/mac_worker/install.sh; then
    echo "Background services not proven: mac worker install failed." >&2
    exit 1
fi

echo "Vollautomatik Background Services installed and running!"
