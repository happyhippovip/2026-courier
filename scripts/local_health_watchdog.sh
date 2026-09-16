#!/bin/bash
# Local Health Watchdog
# Prueft, ob der Courier-Server und die Hintergrundprozesse lokal laufen,
# und startet sie bei Bedarf leise neu.

cd "$(dirname "$0")/.." || exit 1

# Leise pruefen, ob Gunicorn laeuft
if ! pgrep -f "gunicorn.*server.app:app" > /dev/null; then
    echo "$(date): Courier Server laeuft nicht. Starte neu..." >> logs/health_watchdog.log
    
    # Alte Reste zur Sicherheit aufraeumen
    pkill -9 -f courier_verifier.py 2>/dev/null || true
    pkill -9 -f courier_github_dispatcher.py 2>/dev/null || true
    pkill -9 -f courier_watchdog.py 2>/dev/null || true
    pkill -9 -f gunicorn 2>/dev/null || true
    
    # Neu starten im Hintergrund, Ausgaben ins Nirvana
    nohup ./deploy/run-supervisor.sh >> logs/server_launchd.error.log 2>&1 &
else
    # Nur ein kurzes OK loggen
    echo "$(date): Health Check OK - Server laeuft." >> logs/health_watchdog.log
fi
