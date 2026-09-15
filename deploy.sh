#!/bin/bash
set -e

echo "Deploying Courier Control Plane (External Linux Headless Mode)"

# Ensure python3 and pip are installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 not found. Please install python3 and python3-venv."
    exit 1
fi

# Setup virtual environment
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
fi

# Activate venv
source $VENV_DIR/bin/activate

# Install dependencies (if requirements.txt exists)
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# Configure Systemd Service for Auto-start
SERVICE_FILE="/etc/systemd/system/courier-daemon.service"
if [ "$EUID" -eq 0 ]; then
    echo "Configuring systemd service..."
    cat <<EOF > $SERVICE_FILE
[Unit]
Description=Courier Control Plane Daemon
After=network.target

[Service]
Type=simple
User=$(logname)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/$VENV_DIR/bin/python $(pwd)/linux_daemon.py --interval 10
Restart=always
RestartSec=5
# External config overrides can go here
# Environment="COURIER_HANDOFFS_DISPATCH_DIR=/mnt/courier/dispatch"

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable courier-daemon.service
    echo "Service enabled. To start: sudo systemctl start courier-daemon.service"
else
    echo "Not running as root. Skipping systemd service installation."
    echo "To run manually: source $VENV_DIR/bin/activate && python linux_daemon.py"
fi

echo "Deployment preparation complete."
