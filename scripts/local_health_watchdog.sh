#!/bin/bash
# Local Health Watchdog
# Prueft, ob der Courier-Server und die Hintergrundprozesse lokal laufen,
# und startet sie bei Bedarf leise neu.

cd "$(dirname "$0")/.." || exit 1

SUPERVISOR_RUNNING=0
if [ -f run/supervisor.pid ]; then
    if kill -0 $(cat run/supervisor.pid) 2>/dev/null; then
        SUPERVISOR_RUNNING=1
    fi
fi

if [ $SUPERVISOR_RUNNING -eq 0 ]; then
    echo "$(date): Courier Server laeuft nicht. Starte neu..." >> logs/health_watchdog.log
    
    # Alte Reste zur Sicherheit aufraeumen
    if [ -f run/supervisor.pid ]; then
        kill -TERM $(cat run/supervisor.pid) 2>/dev/null || true
        sleep 1
    fi
    
    # Neu starten im Hintergrund, Ausgaben ins Nirvana
    nohup ./deploy/run-supervisor.sh > /dev/null 2>&1 &
else
    # Nur ein kurzes OK loggen
    echo "$(date): Health Check OK - Server laeuft." >> logs/health_watchdog.log
fi
