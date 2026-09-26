#!/bin/bash

kill_safe() {
    local pid_file=$1
    local script_name=$2
    local label=$3
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" -o args= 2>/dev/null | grep -q "$script_name"; then
            kill "$pid"
            echo "$label stopped."
        else
            echo "Stale PID file for $label (PID $pid did not match $script_name)."
        fi
        rm "$pid_file"
    else
        echo "No running $label found."
    fi
}

kill_safe "logs/courier_daemon.pid" "server/app.py\|run_waitress.py" "Courier Server"
kill_safe "logs/courier_verifier.pid" "courier_verifier.py" "Courier Verifier"
kill_safe "logs/courier_github_dispatcher.pid" "courier_github_dispatcher.py" "Courier GitHub Dispatcher"
kill_safe "logs/courier_watchdog.pid" "run_autonomous_supervisor.py" "Courier Watchdog"
