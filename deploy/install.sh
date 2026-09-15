#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

apt-get update
apt-get install -y python3-venv python3-pip

python3 -m venv venv
source venv/bin/activate
pip install flask gunicorn

cp deploy/env.example deploy/.env
cp deploy/courier.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable courier
systemctl restart courier
