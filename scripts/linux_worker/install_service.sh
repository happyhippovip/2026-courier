#!/usr/bin/env bash
set -e

# Must run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Creating courier user..."
useradd -r -s /bin/false courier || true

echo "Setting up directories..."
mkdir -p /opt/courier
mkdir -p /etc/courier
chown -R courier:courier /opt/courier
chown courier:courier /etc/courier

# Store credentials
if [ -n "$1" ]; then
  echo "$1" > /etc/courier/api_key
  chmod 600 /etc/courier/api_key
  chown courier:courier /etc/courier/api_key
fi

echo "Installing systemd service..."
cat << 'EOF' > /etc/systemd/system/courier.service
[Unit]
Description=Courier Worker Daemon
After=network.target

[Service]
Type=simple
User=courier
Group=courier
WorkingDirectory=/opt/courier
ExecStart=/opt/courier/start.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable courier
systemctl start courier

echo "Linux installer complete."
