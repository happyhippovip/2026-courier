#!/bin/bash
if [ -f logs/courier_daemon.pid ]; then
    PID=$(cat logs/courier_daemon.pid)
    kill $PID
    rm logs/courier_daemon.pid
    echo "Daemon stopped."
else
    echo "Daemon not running."
fi
