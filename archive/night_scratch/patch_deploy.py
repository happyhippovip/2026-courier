import sys

content = open("deploy/install_mac_runtime.sh").read()

new_logic = """
# Worker Plist
sed -e "s|TARGET_DIR|$RUNTIME_DIR|g" scripts/mac_worker/com.courier.mac_worker.plist > ~/Library/LaunchAgents/com.courier.mac_worker.plist

# Motor Plist (Runs from the project root)
mkdir -p "$PROJECT_ROOT/logs"
sed -e "s|TARGET_DIR|$PROJECT_ROOT|g" -e "s|TARGET_PYTHON|$(which python3)|g" -e "s|TARGET_SCRIPT|$PROJECT_ROOT/scripts/courier_continue.py|g" "$PROJECT_ROOT/scripts/com.courier.motor.plist" > ~/Library/LaunchAgents/com.courier.motor.plist

echo "5. Starting fully automated local daemons..."
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist

launchctl unload ~/Library/LaunchAgents/com.courier.motor.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.courier.motor.plist
"""

import re
content = re.sub(r'# Worker Plist.*launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist', new_logic.strip(), content, flags=re.DOTALL)

open("deploy/install_mac_runtime.sh", "w").write(content)
