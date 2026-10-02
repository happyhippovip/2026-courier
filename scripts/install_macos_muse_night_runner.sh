#!/bin/bash
# Install a per-user launchd job that runs one Muse night batch every 5 minutes.
set -u

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer is for macOS only." >&2
  exit 64
fi

REPO_ROOT="${COURIER_REPO_ROOT:-}"
if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

LABEL="com.couriersymphony.dev.muse-night"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
STATE_DIR="$HOME/.courier/dev-night"
RUNNER="$REPO_ROOT/scripts/macos_muse_night_once.sh"

mkdir -p "$PLIST_DIR" "$STATE_DIR"

if [ ! -f "$RUNNER" ]; then
  echo "Runner not found: $RUNNER" >&2
  exit 66
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$RUNNER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>
  <key>StartInterval</key>
  <integer>300</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>COURIER_REPO_ROOT</key>
    <string>$REPO_ROOT</string>
    <key>COURIER_NIGHT_STATE_DIR</key>
    <string>$STATE_DIR</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$STATE_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$STATE_DIR/launchd.err.log</string>
</dict>
</plist>
EOF

# Replace any older copy. Never create multiple jobs with the same role.
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
if ! launchctl bootstrap "gui/$UID" "$PLIST"; then
  echo "launchctl bootstrap failed. Job file remains at $PLIST" >&2
  exit 70
fi

launchctl kickstart -k "gui/$UID/$LABEL" >/dev/null 2>&1 || true

echo "Installed: $LABEL"
echo "Cadence: every 300 seconds"
echo "State: $STATE_DIR"
echo "Status: launchctl print gui/$UID/$LABEL"
echo "Pause is fail-closed: $STATE_DIR/RESOURCE_PAUSE"
