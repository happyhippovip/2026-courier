#!/bin/bash
set -eu
: "${COURIER_API_KEY:?COURIER_API_KEY must be set before starting Courier}"
: "${COURIER_VERIFIER_API_KEY:?COURIER_VERIFIER_API_KEY must be set before starting Courier}"
[ "$COURIER_API_KEY" != "$COURIER_VERIFIER_API_KEY" ] || { echo "Worker and verifier API keys must differ" >&2; exit 1; }
source venv/bin/activate

mkdir -p logs

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

# Cross-platform wait for any child process to exit (fallback if wait -n is not supported)
if help wait | grep -q '\[-n\]'; then
    wait -n || true
else
    # Fallback polling for older bash (like macOS default)
    while kill -0 $VERIFIER_PID 2>/dev/null && \
          kill -0 $DISPATCHER_PID 2>/dev/null && \
          kill -0 $WATCHDOG_PID 2>/dev/null && \
          kill -0 $GUNICORN_PID 2>/dev/null; do
        sleep 2
    done
fi

echo "A critical daemon exited. Supervisor stopping..."
kill $VERIFIER_PID $DISPATCHER_PID $WATCHDOG_PID $GUNICORN_PID 2>/dev/null || true
exit 1
