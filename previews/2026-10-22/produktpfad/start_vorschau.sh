#!/bin/sh
# Startet die lokale Vorschau auf http://127.0.0.1:8766 (nur localhost, kein Netz nötig).
cd "$(dirname "$0")" && exec python3 -m http.server 8766 --bind 127.0.0.1
