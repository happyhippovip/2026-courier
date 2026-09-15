#!/bin/bash
set -e

echo "Deploying Courier Control Plane (Fresh External Machine Bootstrap)"

# Configuration (Supplied at deployment time or defaults)
REPO_URL=${COURIER_REPO_URL:-"https://github.com/your-org/2026-courier.git"}
INSTALL_DIR=${COURIER_INSTALL_DIR:-"/opt/courier-app"}
STATE_DIR=${COURIER_STATE_DIR:-"/opt/courier-state"}
SERVICE_USER=${COURIER_USER:-"courier"}

# Ensure running as root for system-wide setup
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo) to bootstrap the machine."
    exit 1
fi

# Ensure python3, git, and venv are installed
echo "Checking dependencies..."
apt-get update && apt-get install -y python3 python3-venv git

# Setup Service User
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating service user: $SERVICE_USER"
    useradd -r -s /bin/false $SERVICE_USER
fi

# Setup Durable State Directory
echo "Setting up durable state directory at $STATE_DIR"
mkdir -p "$STATE_DIR"/dispatch
mkdir -p "$STATE_DIR"/handoffs
mkdir -p "$STATE_DIR"/db
chown -R $SERVICE_USER:$SERVICE_USER "$STATE_DIR"

# Shallow Clone / Sparse Fetch
echo "Fetching code to $INSTALL_DIR (Low Bandwidth)"
if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists, pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
chown -R $SERVICE_USER:$SERVICE_USER "$INSTALL_DIR"

# Setup virtual environment
cd "$INSTALL_DIR"
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    sudo -u $SERVICE_USER python3 -m venv $VENV_DIR
fi

# Activate venv and install dependencies
# We run pip as the service user to avoid root pip usage
if [ -f "requirements.txt" ]; then
    sudo -u $SERVICE_USER "$VENV_DIR/bin/pip" install -r requirements.txt
fi

# Configure Systemd Service for Auto-start
SERVICE_FILE="/etc/systemd/system/courier-daemon.service"
echo "Configuring systemd service..."
cat <<EOF > $SERVICE_FILE
[Unit]
Description=Courier Control Plane Daemon
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/$VENV_DIR/bin/python $INSTALL_DIR/linux_daemon.py
Restart=always
RestartSec=5

# Environment variables mapping code to durable external state
Environment="COURIER_HANDOFFS_DISPATCH_DIR=$STATE_DIR/dispatch"
Environment="COURIER_WORKSPACE_ROOT=$STATE_DIR"
# DB can be stored in STATE_DIR
Environment="COURIER_DB_PATH=$STATE_DIR/db/courier.sqlite"

# Limits for low-bandwidth / low-resource nodes
LimitNOFILE=4096
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable courier-daemon.service
systemctl restart courier-daemon.service

echo "=================================================="
echo "Deployment bootstrap complete!"
echo "Service status: systemctl status courier-daemon.service"
echo "Logs: journalctl -u courier-daemon -f -n 50"
echo "State Directory: $STATE_DIR"
echo "To export state: tar -czf courier-state-backup.tar.gz -C /opt courier-state"
echo "=================================================="
