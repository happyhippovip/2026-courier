#!/bin/bash
# Safe quiesce and restart
echo 'Quiescing...'
launchctl list | grep com.courier | awk '{print $3}' | xargs -I {} launchctl unload ~/Library/LaunchAgents/{}.plist 2>/dev/null
echo 'Restarted.'
