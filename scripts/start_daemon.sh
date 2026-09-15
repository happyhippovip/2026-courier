#!/bin/bash
mkdir -p logs intakes/pending intakes/processed
if [ -f logs/courier_daemon.pid ]; then
    if ps -p $(cat logs/courier_daemon.pid) > /dev/null; then
        echo "Daemon already running."
        exit 0
    fi
fi
nohup bash -c 'while true; do python3 scripts/queue_processor.py; sleep 10; done' > logs/courier_daemon.log 2>&1 &
echo $! > logs/courier_daemon.pid
echo "Courier Vollautomatik daemon started in background (PID $(cat logs/courier_daemon.pid)). Survives terminal exit."
