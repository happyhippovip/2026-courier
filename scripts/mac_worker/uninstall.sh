#!/bin/bash
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null
rm ~/Library/LaunchAgents/com.courier.mac_worker.plist
echo "Mac worker uninstalled."
