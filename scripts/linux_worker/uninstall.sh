#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

REMOVE_DATA=0
REMOVE_CREDS=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --remove-data) REMOVE_DATA=1 ;;
        --remove-credentials) REMOVE_CREDS=1 ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

echo "Stopping service..."
systemctl stop courier || true
systemctl disable courier || true
rm -f /etc/systemd/system/courier.service
systemctl daemon-reload

echo "Removing runtime files..."
# Remove runtime but keep data if requested
if [ "$REMOVE_DATA" -eq 1 ]; then
    rm -rf /opt/courier
else
    echo "Preserving /opt/courier (customer data). Use --remove-data to delete."
    # Remove binary/script files but not data
    rm -f /opt/courier/start.sh /opt/courier/daemon.py || true
fi

if [ "$REMOVE_CREDS" -eq 1 ]; then
    echo "Removing credentials..."
    rm -rf /etc/courier
else
    echo "Preserving credentials in /etc/courier. Use --remove-credentials to delete."
fi

echo "Uninstall complete."
