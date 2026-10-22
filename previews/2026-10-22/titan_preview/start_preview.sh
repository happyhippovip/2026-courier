#!/bin/sh
# Startet die TITAN-Vorschau lokal: ./start_preview.sh /pfad/zu/2026-courier
# Der Checkout braucht integration/v1 mit PR #776 und #777 (toBeamGraph, Evidence-Anker).
set -eu
REPO="${1:?Pfad zum 2026-courier-Checkout angeben}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SERVE="$(mktemp -d)"
ln -s "$REPO/courier_hub" "$SERVE/courier_hub"
ln -s "$HERE" "$SERVE/titan"
echo "Vorschau: http://127.0.0.1:18777/titan/index.html  (Strg+C beendet)"
cd "$SERVE" && exec python3 -m http.server 18777 --bind 127.0.0.1
