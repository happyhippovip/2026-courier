#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"
echo "======================================================"
echo "  Antigravity CLI 1 (Hauptkonto / Autonom)"
echo "  Modus: Autonom mit Fine-Grained Permissions"
echo "  Arbeitsverzeichnis: $DIR"
echo "======================================================"
if [ -f "$HOME/.local/bin/agy" ]; then
    "$HOME/.local/bin/agy" --dangerously-skip-permissions
else
    agy --dangerously-skip-permissions
fi
