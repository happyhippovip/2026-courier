#!/bin/bash
set -eu
: "${COURIER_API_KEY:?COURIER_API_KEY must be set before starting Courier}"
: "${COURIER_VERIFIER_API_KEY:?COURIER_VERIFIER_API_KEY must be set before starting Courier}"
[ "$COURIER_API_KEY" != "$COURIER_VERIFIER_API_KEY" ] || { echo "Worker and verifier API keys must differ" >&2; exit 1; }
mkdir -p logs server/state

# pid and the ps start time, tab-separated. Stop refuses a file without both.
record_pid() {
    file=$1
    pid=$2
    ident=$(ps -p "$pid" -o lstart= | tr -s ' ' | sed 's/^ *//;s/ *$//')
    if [ -z "$ident" ]; then
        kill "$pid" 2>/dev/null || true
        echo "Process $pid identity was not recorded; not leaving it running." >&2
        exit 1
    fi
    printf '%s\t%s\n' "$pid" "$ident" > "$file"
}

if [ -f logs/courier_daemon.pid ]; then
    line=$(cat logs/courier_daemon.pid)
    pid=${line%%$'\t'*}
    ident=${line#*$'\t'}
    if [ "$pid" = "$line" ]; then
        ident=
    fi
    if kill -0 "$pid" 2>/dev/null; then
        live=$(ps -p "$pid" -o lstart= | tr -s ' ' | sed 's/^ *//;s/ *$//')
        if [ -n "$ident" ] && [ "$live" = "$ident" ]; then
            echo "Daemon already running."
            exit 0
        fi
        echo "Daemon pid is live but identity does not match; not starting another and not signaling." >&2
        exit 1
    fi
fi

nohup python3 server/app.py > logs/courier_daemon.log 2>&1 &
record_pid logs/courier_daemon.pid "$!"
echo "Courier Server (HTTP) started in background (PID $(cut -f1 logs/courier_daemon.pid))."

nohup python3 scripts/courier_verifier.py > logs/courier_verifier.log 2>&1 &
record_pid logs/courier_verifier.pid "$!"
echo "Courier Verifier started in background (PID $(cut -f1 logs/courier_verifier.pid))."

nohup python3 scripts/courier_github_dispatcher.py > logs/courier_github_dispatcher.log 2>&1 &
record_pid logs/courier_github_dispatcher.pid "$!"
echo "Courier GitHub Dispatcher started in background (PID $(cut -f1 logs/courier_github_dispatcher.pid))."

nohup python3 scripts/courier_watchdog.py > logs/courier_watchdog.log 2>&1 &
record_pid logs/courier_watchdog.pid "$!"
echo "Courier Watchdog started in background (PID $(cut -f1 logs/courier_watchdog.pid))."
