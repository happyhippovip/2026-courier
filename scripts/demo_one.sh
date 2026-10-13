#!/usr/bin/env bash
# Courier Ein-Befehl-Demo (MOCK) - macOS/Linux
set -euo pipefail
cd "$(dirname "$0")/.."
PY="$(command -v python3.12 || command -v python3)"
exec "$PY" scripts/demo_one.py "$@"
