#!/bin/bash
set -e

echo "WARNING: scripts/setup_local_autonomy.sh is deprecated as a product installer."
echo "Delegating to the canonical Mac runtime installer..."

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "$SRC_DIR/deploy/install_mac_runtime.sh"
