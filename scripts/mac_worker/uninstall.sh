#!/bin/bash
# Do not report the worker uninstalled while its plist is still present.
# launchctl is used only when it exists; a missing binary is not an unload.
plist="${HOME}/Library/LaunchAgents/com.courier.mac_worker.plist"
if [ -e "$plist" ]; then
    if command -v launchctl >/dev/null 2>&1; then
        if ! launchctl unload "$plist"; then
            echo "Mac worker uninstall not proven: launchctl unload failed." >&2
            exit 1
        fi
    fi
    if ! rm "$plist"; then
        echo "Mac worker uninstall not proven: plist was not removed." >&2
        exit 1
    fi
fi
if [ -e "$plist" ]; then
    echo "Mac worker uninstall not proven." >&2
    exit 1
fi
echo "Mac worker uninstalled."
