#!/bin/bash
if [ -f logs/courier_daemon.pid ]; then
    kill $(cat logs/courier_daemon.pid)
    rm logs/courier_daemon.pid
    echo "Courier Server stopped."
else
    echo "No running daemon found."
fi
