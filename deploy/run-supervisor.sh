#!/bin/bash
set -eu
# Fetch from Mac Keychain if not in env
if [ -z "${COURIER_API_KEY:-}" ]; then
    COURIER_API_KEY=$(security find-generic-password -a "courier_worker" -s "courier_api_key" -w 2>/dev/null) || true
fi
if [ -z "${COURIER_VERIFIER_API_KEY:-}" ]; then
    COURIER_VERIFIER_API_KEY=$(security find-generic-password -a "courier_worker" -s "courier_verifier_api_key" -w 2>/dev/null) || true
fi

: "${COURIER_API_KEY:?COURIER_API_KEY must be set before starting Courier}"
: "${COURIER_VERIFIER_API_KEY:?COURIER_VERIFIER_API_KEY must be set before starting Courier}"
export COURIER_API_KEY
export COURIER_VERIFIER_API_KEY
[ "$COURIER_API_KEY" != "$COURIER_VERIFIER_API_KEY" ] || { echo "Worker and verifier API keys must differ" >&2; exit 1; }
source venv/bin/activate

echo "Starting Courier background daemons..."
python3 scripts/courier_verifier.py > logs/courier_verifier.log 2>&1 &
VERIFIER_PID=$!

python3 scripts/courier_github_dispatcher.py > logs/courier_github_dispatcher.log 2>&1 &
DISPATCHER_PID=$!

python3 scripts/courier_watchdog.py > logs/courier_watchdog.log 2>&1 &
WATCHDOG_PID=$!



echo "Starting Gunicorn server..."
# Using -w 1 --threads 4 to avoid file locking issues with state.json

gunicorn -w 1 --threads 4 -b 0.0.0.0:8080 server.app:app &
GUNICORN_PID=$!

trap "echo 'Stopping all...'; kill $VERIFIER_PID $DISPATCHER_PID $WATCHDOG_PID $GUNICORN_PID 2>/dev/null; exit 0" EXIT SIGINT SIGTERM

wait $GUNICORN_PID
