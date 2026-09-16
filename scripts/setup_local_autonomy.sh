#!/bin/bash
# Re-routed to the single supported installer path
set -e

echo "Courier: Local Autonomy Setup"
echo "---------------------------------"

# Prompt for credentials securely and store them in the Mac Keychain
read -p "Enter COURIER_SERVER URL (e.g. http://127.0.0.1:8080): " SERVER_URL
read -s -p "Enter COURIER_API_KEY (Worker): " API_KEY
echo ""
read -s -p "Enter COURIER_VERIFIER_API_KEY (Server): " VERIFIER_KEY
echo ""

if [ -n "$SERVER_URL" ]; then
    security add-generic-password -a "courier_worker" -s "courier_server_url" -w "$SERVER_URL" -U
fi
if [ -n "$API_KEY" ]; then
    security add-generic-password -a "courier_worker" -s "courier_api_key" -w "$API_KEY" -U
fi
if [ -n "$VERIFIER_KEY" ]; then
    security add-generic-password -a "courier_worker" -s "courier_verifier_api_key" -w "$VERIFIER_KEY" -U
fi

echo "Credentials securely stored in Keychain."

# Call the single canonical installer
echo "Delegating to canonical installer..."
cd "$(dirname "$0")/.."
if [ ! -d "../2026-courier" ]; then
    # We might be in a different folder name, so symlink it temporarily for the installer
    CURRENT_DIR_NAME=$(basename $(pwd))
    if [ "$CURRENT_DIR_NAME" != "2026-courier" ]; then
        ln -sfn "./$CURRENT_DIR_NAME" "../2026-courier"
    fi
fi

bash deploy/install_mac_runtime.sh
