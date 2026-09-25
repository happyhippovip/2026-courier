#!/bin/bash
set -e

BIN_DIR="/usr/local/bin"
if [ ! -w "$BIN_DIR" ]; then
    echo "Warning: No write access to $BIN_DIR. Will install to ~/.local/bin"
    BIN_DIR="$HOME/.local/bin"
    mkdir -p "$BIN_DIR"
fi

cp tools/courierctl/courierctl.py "$BIN_DIR/courierctl"
chmod +x "$BIN_DIR/courierctl"

echo "Installed courierctl to $BIN_DIR/courierctl"
echo ""
echo "Please set your environment variables to use it:"
echo "export COURIER_SERVER=http://localhost:8080"
echo "export COURIER_API_KEY=your_secure_api_key_here"
