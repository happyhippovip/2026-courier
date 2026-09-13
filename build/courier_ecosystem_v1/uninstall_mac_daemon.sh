#!/usr/bin/env bash
# Courier Ecosystem - macOS LaunchAgent Uninstaller

set -e

PLIST_PATH="$HOME/Library/LaunchAgents/com.courier.ecosystem.plist"

echo "[*] Unloading LaunchAgent from launchd..."

if [ -f "$PLIST_PATH" ]; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
    echo "[+] Successfully unloaded and removed $PLIST_PATH"
else
    echo "[-] $PLIST_PATH does not exist. Was it installed?"
fi

# Kill processes via pid files to avoid broad pkill -f matches
echo "[*] Shutting down Courier processes safely..."

for PID_FILE in /tmp/courier_*.pid; do
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "[*] Terminating process $PID..."
            kill $PID || true
        fi
        rm -f "$PID_FILE"
    fi
done

echo "[+] Courier Ecosystem has been safely stopped."

echo "[+] Courier Ecosystem has been completely stopped and uninstalled from launchd."
echo "[+] You can now safely delete the directory if you wish to remove the software."
