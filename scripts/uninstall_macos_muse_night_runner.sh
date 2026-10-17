#!/bin/bash
set -u

# Do not report the launchd job removed while its plist is still present.
LABEL="com.couriersymphony.dev.muse-night"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This uninstaller is for macOS only." >&2
  exit 64
fi

if [ -e "$PLIST" ]; then
  if command -v launchctl >/dev/null 2>&1; then
    if ! launchctl bootout "gui/$UID" "$PLIST"; then
      echo "Muse night uninstall not proven: launchctl bootout failed." >&2
      exit 1
    fi
  fi
  if ! rm -f "$PLIST"; then
    echo "Muse night uninstall not proven: plist was not removed." >&2
    exit 1
  fi
fi

if [ -e "$PLIST" ]; then
  echo "Muse night uninstall not proven." >&2
  exit 1
fi

echo "Removed launchd job: $LABEL"
echo "State/logs preserved at: $HOME/.courier/dev-night"
