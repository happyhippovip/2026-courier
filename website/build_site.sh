#!/bin/sh
# Baut website/public/ aus website/src/. Kein Netzwerk.
# COURIER_CONTACT_EMAIL wird nur eingesetzt, wenn sie gesetzt ist und wie eine
# schlichte Adresse aussieht. Sonst bleibt der Kontakt bei GitHub Issues.
set -eu
cd "$(dirname "$0")"
rm -rf public
mkdir -p public/media
cp src/*.html src/*.css src/*.js public/
cp src/media/*.jpg public/media/
if [ -n "${COURIER_CONTACT_EMAIL:-}" ]; then
  case "$COURIER_CONTACT_EMAIL" in
    *"<"*|*"&"*|*"'"*|*" "*)
      echo "contact email refused" >&2
      exit 1
      ;;
  esac
  printf '%s\n' "$COURIER_CONTACT_EMAIL" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$' \
    || { echo "contact email refused" >&2; exit 1; }
  printf '\n<p>Zusätzlicher Kontakt, nur wenn beim Deploy gesetzt: %s</p>\n' "$COURIER_CONTACT_EMAIL" >> public/index.html
fi
echo "build ok: $(find public -type f | wc -l | tr -d ' ') files"
