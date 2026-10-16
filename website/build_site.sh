#!/bin/sh
# Baut website/public/ aus website/src/. Kein Netzwerk, keine Abhängigkeiten.
# COURIER_CONTACT_EMAIL (optional): wird NUR eingesetzt, wenn gesetzt und
# nicht leer. Sonst bleibt der GitHub-Issues-Kontakt (fail-closed, keine
# persönlichen Daten im Build).
set -eu
cd "$(dirname "$0")"

# Validate before touching public. The value is interpolated into sed.
if [ -n "${COURIER_CONTACT_EMAIL:-}" ]; then
  case $COURIER_CONTACT_EMAIL in
    *[!A-Za-z0-9._%+-@]*)
      echo "contact email rejected" >&2
      exit 1
      ;;
  esac
  case $COURIER_CONTACT_EMAIL in
    *@*.*) ;;
    *)
      echo "contact email rejected" >&2
      exit 1
      ;;
  esac
  rest=${COURIER_CONTACT_EMAIL#*@}
  case $rest in
    *@*)
      echo "contact email rejected" >&2
      exit 1
      ;;
  esac
fi

rm -rf public
mkdir -p public
cp src/*.html public/
if [ -n "${COURIER_CONTACT_EMAIL:-}" ]; then
  # Insert beside the existing link. Do not consume the next character.
  marker='GitHub Issues</a>'
  if ! grep -F -q "$marker" public/index.html; then
    echo "contact marker missing" >&2
    exit 1
  fi
  sed "s#${marker}#${marker} oder ${COURIER_CONTACT_EMAIL}#" public/index.html > public/index.html.tmp
  mv public/index.html.tmp public/index.html
  if ! grep -F -q "oder ${COURIER_CONTACT_EMAIL}" public/index.html; then
    echo "contact email was not inserted" >&2
    exit 1
  fi
fi
echo "build ok: $(ls public | tr '\n' ' ')"
