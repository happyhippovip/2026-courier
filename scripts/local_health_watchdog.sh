#!/bin/bash
# Local Health Watchdog
# Prueft, ob der Courier-Server und die Hintergrundprozesse lokal laufen,
# und startet sie bei Bedarf leise neu.

cd "$(dirname "$0")/.." || exit 1

# Leise pruefen, ob Gunicorn laeuft
if ! pgrep -f "gunicorn.*server.app:app" > /dev/null; then
    echo "$(date): Courier Server laeuft nicht. Starte neu..." >> logs/health_watchdog.log
    
    # Alte Reste zur Sicherheit aufraeumen
    if [ -f "logs/.supervisor.pid" ]; then
        for pid in $(cat logs/.supervisor.pid); do
            kill -9 $pid 2>/dev/null || true
        done
        rm -f logs/.supervisor.pid
    fi
    
    # Neu starten im Hintergrund, Ausgaben ins Nirvana
    nohup ./deploy/run-supervisor.sh > /dev/null 2>&1 &
else
    # Nur ein kurzes OK loggen
    echo "$(date): Health Check OK - Server laeuft." >> logs/health_watchdog.log
fi
