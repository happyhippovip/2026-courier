#!/usr/bin/env bash
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Stopping service..."
systemctl stop courier || true
systemctl disable courier || true
rm -f /etc/systemd/system/courier.service
systemctl daemon-reload

echo "Removing directories and secrets..."
rm -rf /opt/courier
rm -rf /etc/courier

echo "Uninstall complete."
