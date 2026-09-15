#!/bin/bash
if [ -f logs/courier_daemon.pid ]; then
    kill $(cat logs/courier_daemon.pid)
    rm logs/courier_daemon.pid
    echo "Courier Server stopped."
else
    echo "No running daemon found."
fi

if [ -f logs/courier_verifier.pid ]; then
    kill $(cat logs/courier_verifier.pid)
    rm logs/courier_verifier.pid
    echo "Courier Verifier stopped."
fi

if [ -f logs/courier_github_dispatcher.pid ]; then
    kill $(cat logs/courier_github_dispatcher.pid)
    rm logs/courier_github_dispatcher.pid
    echo "Courier GitHub Dispatcher stopped."
fi
