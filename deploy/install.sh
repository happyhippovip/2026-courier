#!/bin/bash
set -e
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi
cd "$(dirname "$0")/.."

apt-get update
apt-get install -y python3-venv python3-pip

python3 -m venv venv
source venv/bin/activate
# requests is needed by the verifier, GitHub dispatcher and watchdog.
pip install flask gunicorn requests

# Never overwrite an existing configuration (it holds the real keys).
if [ ! -f deploy/.env ]; then
  cp deploy/env.example deploy/.env
  chmod 600 deploy/.env
  echo "Created deploy/.env from env.example: set COURIER_API_KEY and COURIER_VERIFIER_API_KEY."
fi
cp deploy/courier.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable courier
# Not started here: with placeholder keys the supervisor fails closed and
# systemd would restart-loop. Start it once deploy/.env holds real keys.
echo "Installed. After editing deploy/.env run: systemctl restart courier"
