#!/bin/bash
# Signal only a pid whose recorded start time still matches. A bare pid, a
# reused pid, or a kill that does not make the process exit is not "stopped".
status=0

stop_recorded() {
    file=$1
    label=$2
    if [ ! -f "$file" ]; then
        return 0
    fi
    line=$(cat "$file")
    pid=${line%%$'\t'*}
    ident=${line#*$'\t'}
    if [ "$pid" = "$line" ]; then
        ident=
    fi
    case "$pid" in
        ''|*[!0-9]*)
            echo "$label pid file is not a recorded process; termination not proven." >&2
            return 1
            ;;
    esac
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$file"
        echo "$label is not running."
        return 0
    fi
    if [ -z "$ident" ]; then
        echo "$label is still running and its identity was not recorded; termination not proven." >&2
        return 1
    fi
    live=$(ps -p "$pid" -o lstart= 2>/dev/null | tr -s ' ' | sed 's/^ *//;s/ *$//')
    if [ "$live" != "$ident" ]; then
        echo "$label identity does not match the recorded process; not signaling." >&2
        return 1
    fi
    if ! kill "$pid" 2>/dev/null; then
        echo "$label termination not proven." >&2
        return 1
    fi
    proven=0
    for _ in 1 2 3 4 5; do
        if ! kill -0 "$pid" 2>/dev/null; then
            proven=1
            break
        fi
        state=$(ps -p "$pid" -o stat= 2>/dev/null | tr -d ' ')
        case "$state" in
            Z*)
                proven=1
                break
                ;;
        esac
        sleep 0.05
    done
    if [ "$proven" -ne 1 ]; then
        echo "$label termination not proven." >&2
        return 1
    fi
    rm -f "$file"
    echo "$label stopped."
}

stop_recorded logs/courier_daemon.pid "Courier Server" || status=1
stop_recorded logs/courier_verifier.pid "Courier Verifier" || status=1
stop_recorded logs/courier_github_dispatcher.pid "Courier GitHub Dispatcher" || status=1
stop_recorded logs/courier_watchdog.pid "Courier Watchdog" || status=1
exit "$status"
