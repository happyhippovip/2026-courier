#!/bin/bash
set -eu

# Unified Development Services Manager
# Handles: server, verifier, worker, motor, studio

if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '#' | awk '/=/ {print $1}')
fi

COMMAND=${1:-}
SERVICE=${2:-all}

SERVICES=("server" "verifier" "worker" "motor" "studio" "watchdog")
PIDS_DIR="logs/pids"
LOGS_DIR="logs"

mkdir -p "$PIDS_DIR" "$LOGS_DIR"

start_service() {
    local s=$1
    local pid_file="$PIDS_DIR/$s.pid"
    local log_file="$LOGS_DIR/$s.log"
    
    if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null && ps -p $(cat "$pid_file") -o command= | grep -qi "python"; then
        echo "Service '$s' is already running (PID $(cat "$pid_file"))."
        return
    fi

    # Set up command
    local cmd=""
    case $s in
        server)   cmd="env PYTHONPATH=$(pwd) python3 server/app.py" ;;
        verifier) cmd="env PYTHONPATH=$(pwd) python3 scripts/courier_verifier.py" ;;
        worker)   cmd="env PYTHONPATH=$(pwd) python3 scripts/mac_worker/daemon.py" ;;
        motor)    cmd="env PYTHONPATH=$(pwd) python3 scripts/courier_continue.py --run" ;;
        studio)   cmd="env PYTHONPATH=$(pwd) python3 scripts/run_visual_studio_server.py" ;;
        watchdog) cmd="env PYTHONPATH=$(pwd) python3 scripts/courier_watchdog.py" ;;
    esac

    echo "Starting $s..."
    nohup $cmd > "$log_file" 2>&1 &
    local pid=$!
    echo $pid > "$pid_file"
    
    # Give it a moment and check if it crashed immediately
    sleep 1
    if kill -0 $pid 2>/dev/null; then
        echo "Service '$s' started successfully (PID $pid)."
    else
        echo "Service '$s' failed to start! Check $log_file"
        rm -f "$pid_file"
    fi
}

stop_service() {
    local s=$1
    local pid_file="$PIDS_DIR/$s.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null && ps -p $pid -o command= | grep -qi "python"; then
            echo "Stopping $s (PID $pid)..."
            kill $pid
            
            # Wait for shutdown
            local timeout=10
            while kill -0 $pid 2>/dev/null && [ $timeout -gt 0 ]; do
                sleep 0.5
                timeout=$((timeout-1))
            done
            
            if kill -0 $pid 2>/dev/null && ps -p $pid -o command= | grep -qi "python"; then
                echo "Service '$s' did not stop gracefully. Forcing kill..."
                kill -9 $pid
            fi
            echo "Service '$s' stopped."
        else
            echo "Service '$s' was not running (stale PID file)."
        fi
        rm -f "$pid_file"
    else
        echo "Service '$s' is not running."
    fi
}

status_service() {
    local s=$1
    local pid_file="$PIDS_DIR/$s.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null && ps -p $pid -o command= | grep -qi "python"; then
            echo "[RUNNING] $s (PID $pid)"
        else
            echo "[DEAD]    $s (Stale PID $pid)"
        fi
    else
        echo "[STOPPED] $s"
    fi
}

case $COMMAND in
    start)
        if [ "$SERVICE" == "all" ]; then
            for s in "${SERVICES[@]}"; do start_service $s; done
        else
            start_service $SERVICE
        fi
        ;;
    stop)
        if [ "$SERVICE" == "all" ]; then
            for s in "${SERVICES[@]}"; do stop_service $s; done
        else
            stop_service $SERVICE
        fi
        ;;
    restart)
        $0 stop $SERVICE
        sleep 1
        $0 start $SERVICE
        ;;
    status)
        if [ "$SERVICE" == "all" ]; then
            for s in "${SERVICES[@]}"; do status_service $s; done
        else
            status_service $SERVICE
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [server|verifier|worker|motor|studio|watchdog|all]"
        exit 1
        ;;
esac
