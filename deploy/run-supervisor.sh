#!/bin/bash
set -eu
: "${COURIER_API_KEY:?COURIER_API_KEY must be set before starting Courier}"
: "${COURIER_VERIFIER_API_KEY:?COURIER_VERIFIER_API_KEY must be set before starting Courier}"
[ "$COURIER_API_KEY" != "$COURIER_VERIFIER_API_KEY" ] || { echo "Worker and verifier API keys must differ" >&2; exit 1; }
source venv/bin/activate

echo "Starting Courier background daemons..."
python3 scripts/courier_verifier.py > logs/courier_verifier.log 2>&1 &
VERIFIER_PID=$!

python3 scripts/courier_github_dispatcher.py > logs/courier_github_dispatcher.log 2>&1 &
DISPATCHER_PID=$!

python3 scripts/courier_watchdog.py > logs/courier_watchdog.log 2>&1 &
WATCHDOG_PID=$!

trap "echo 'Stopping daemons...'; kill $VERIFIER_PID $DISPATCHER_PID $WATCHDOG_PID" EXIT

echo "Starting Gunicorn server..."
# Using -w 1 --threads 4 to avoid file locking issues with state.json
exec gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 server.app:app
