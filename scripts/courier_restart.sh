#!/bin/bash
# Do not report a restart when launchctl did not unload the courier jobs.
if ! command -v launchctl >/dev/null 2>&1; then
    echo "Restart not proven: launchctl is not available." >&2
    exit 1
fi

echo 'Quiescing...'
set -o pipefail
if ! launchctl list | grep com.courier | awk '{print $3}' | xargs -I {} launchctl unload "$HOME/Library/LaunchAgents/{}.plist"; then
    echo "Restart not proven." >&2
    exit 1
fi
echo 'Restarted.'
