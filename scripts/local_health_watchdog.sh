#!/bin/bash
# Local Health Watchdog
# Prueft, ob der Courier-Server und die Hintergrundprozesse lokal laufen,
# und startet sie bei Bedarf leise neu.

cd "$(dirname "$0")/.." || exit 1
OWNED="run/owned_processes.json"

# Leise pruefen, ob Gunicorn laeuft
if ! pgrep -f "gunicorn.*server.app:app" > /dev/null; then
    echo "$(date): Courier Server laeuft nicht. Starte neu..." >> logs/health_watchdog.log
    
    # Nur den Prozessbaum stoppen, den dieser Watchdog selbst gestartet und
    # registriert hat (PID + Startzeit). Nie nach Namen killen: pkill -f traf
    # auch fremde gunicorn-/Python-Prozesse.
    python3 -m courier_runtime.ownership stop --registry "$OWNED" --workkey local-supervisor >> logs/health_watchdog.log 2>&1 || true

    # Neu starten im Hintergrund, Ausgaben ins Nirvana, und als eigenen Baum registrieren
    nohup ./deploy/run-supervisor.sh > /dev/null 2>&1 &
    python3 -m courier_runtime.ownership record --registry "$OWNED" --pid $! --workkey local-supervisor --owner local_health_watchdog >> logs/health_watchdog.log 2>&1 || true
else
    # Nur ein kurzes OK loggen
    echo "$(date): Health Check OK - Server laeuft." >> logs/health_watchdog.log
fi
