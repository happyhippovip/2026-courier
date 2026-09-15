#!/bin/bash
mkdir -p logs goals/pending results/incoming tasks/dispatched
if [ -f logs/courier_daemon.pid ]; then
    if ps -p $(cat logs/courier_daemon.pid) > /dev/null; then
        echo "Daemon already running."
        exit 0
    fi
fi
nohup bash -c 'while true; do python3 scripts/courier_control_plane.py; sleep 3; done' > logs/courier_daemon.log 2>&1 &
echo $! > logs/courier_daemon.pid
echo "Courier Server Daemon started in background (PID $(cat logs/courier_daemon.pid))."
