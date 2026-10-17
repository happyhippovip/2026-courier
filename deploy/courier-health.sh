#!/bin/bash
# Courier customer health check: LAUNCH -> SEE HEALTH -> CONNECT.
#
# Reports whether the local Courier controller is reachable and authorized,
# in customer language with a concrete next action. Never prints tokens.
#
#   deploy/courier-health.sh [base-url]
#
# Resolution order for the controller address:
#   1. argv[1]  2. $COURIER_SERVER / $COURIER_CONTROLLER  3. http://127.0.0.1:8080
# Token order: $COURIER_TOKEN, then $COURIER_HOME/run/controller.token.
# Endpoint is always GET <base>/v1/health (the canonical controller route).
#
# Exit codes: 0 connected | 1 unreachable | 2 reachable but unauthorized | 3 other HTTP answer.

set -u

base="${1:-${COURIER_SERVER:-${COURIER_CONTROLLER:-http://127.0.0.1:8080}}}"
base="${base%/}"
token="${COURIER_TOKEN:-}"
if [ -z "$token" ] && [ -n "${COURIER_HOME:-}" ] && [ -f "$COURIER_HOME/run/controller.token" ]; then
    token="$(tr -d ' \t\r\n' < "$COURIER_HOME/run/controller.token")"
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "Courier health check needs 'curl', which is not installed. Next: install curl, then run this check again."
    exit 1
fi

body="$(mktemp)"
trap 'rm -f "$body"' EXIT

args=(-sS -o "$body" -w '%{http_code}' --max-time 5 --connect-timeout 3)
if [ -n "$token" ]; then
    args+=(-H "X-Courier-Token: $token")
fi

code="$(curl "${args[@]}" "$base/v1/health" 2>/dev/null)"
curl_exit="$?"
if [ "$curl_exit" -ne 0 ]; then
    echo "Courier isn't reachable at $base right now. Nothing was sent. Next: start Courier on this machine, then run this check again."
    exit 1
fi

read_body() { tr -d '\000' < "$body" | head -c 300; }
mode="$(grep -o '"mode"[[:space:]]*:[[:space:]]*"[^"]*"' "$body" 2>/dev/null | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')"
seq="$(grep -o '"head_seq"[[:space:]]*:[[:space:]]*[0-9]*' "$body" 2>/dev/null | head -n 1 | grep -o '[0-9]*$')"

case "$code" in
    200)
        if [ -z "$mode" ]; then
            echo "Courier answered with HTTP 200 at $base but the answer was not a Courier health report: $(read_body). Next: check that this is your Courier controller address, then try again or open the Hub."
            exit 3
        fi
        detail=" (mode: $mode"
        if [ -n "$seq" ]; then detail="$detail, tasks seen: $seq)"; else detail="$detail)"; fi
        if [ "$mode" = "degraded_readonly" ]; then
            echo "Courier is connected at $base but in safe mode$detail. Next: open the Hub to see what needs you."
        else
            echo "Courier is connected at $base$detail. Next: submit your first safe task from the Hub."
        fi
        exit 0
        ;;
    401|403)
        echo "Courier is running at $base but this check was not authorized (HTTP $code). Nothing was changed. Next: set COURIER_TOKEN to the controller token or COURIER_HOME to the Courier home containing run/controller.token, then run this check again."
        exit 2
        ;;
    *)
        echo "Courier answered with HTTP $code at $base: $(read_body). Next: check that this is your Courier controller address, then try again or open the Hub."
        exit 3
        ;;
esac
