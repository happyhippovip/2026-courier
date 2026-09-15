#!/bin/bash
mkdir -p logs server/state
if [ -f logs/courier_daemon.pid ]; then
    if ps -p $(cat logs/courier_daemon.pid) > /dev/null; then
        echo "Daemon already running."
        exit 0
    fi
fi
export COURIER_API_KEY="prod-secret-12345"
nohup python3 server/app.py > logs/courier_daemon.log 2>&1 &
echo $! > logs/courier_daemon.pid
echo "Courier Server (HTTP) started in background (PID $(cat logs/courier_daemon.pid))."

nohup python3 scripts/courier_verifier.py > logs/courier_verifier.log 2>&1 &
echo $! > logs/courier_verifier.pid
echo "Courier Verifier started in background (PID $(cat logs/courier_verifier.pid))."

nohup python3 scripts/courier_github_dispatcher.py > logs/courier_github_dispatcher.log 2>&1 &
echo $! > logs/courier_github_dispatcher.pid
echo "Courier GitHub Dispatcher started in background (PID $(cat logs/courier_github_dispatcher.pid))."
