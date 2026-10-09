#!/bin/sh
# Baut website/public/ aus website/src/. Kein Netzwerk, keine Abhängigkeiten.
# COURIER_CONTACT_EMAIL (optional): wird NUR eingesetzt, wenn gesetzt und
# nicht leer. Sonst bleibt der GitHub-Issues-Kontakt (fail-closed, keine
# persönlichen Daten im Build).
set -eu
cd "$(dirname "$0")"
rm -rf public
mkdir -p public
cp src/index.html src/404.html public/
if [ -n "${COURIER_CONTACT_EMAIL:-}" ]; then
  # Kontakt-E-Mail zusätzlich einhängen (einfacher, sichtbarer Einzeiler).
  sed -i "s#GitHub Issues</a>.#GitHub Issues</a> oder ${COURIER_CONTACT_EMAIL}.#" public/index.html
fi
echo "build ok: $(ls public | tr '\n' ' ')"
