#!/usr/bin/env bash
set -u

PROMPT_FILE="${1:-ops/ai/MAC_GOOGLE_HARD_NO_IDLE_FINISHER_PROMPT.txt}"
MAX_HOURS="${MAX_HOURS:-8}"
SLEEP_SECONDS="${SLEEP_SECONDS:-45}"
LOG_DIR="${LOG_DIR:-logs/agy-relauncher}"
mkdir -p "$LOG_DIR"

if ! command -v agy >/dev/null 2>&1; then
  echo "agy not found in PATH" >&2
  exit 127
fi

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 2
fi

start_epoch=$(date +%s)
end_epoch=$((start_epoch + MAX_HOURS * 3600))
run=0

while [ "$(date +%s)" -lt "$end_epoch" ]; do
  run=$((run + 1))
  stamp=$(date +%Y%m%d-%H%M%S)
  log="$LOG_DIR/$stamp-run$run.log"
  echo "[agy-relauncher] run=$run log=$log"

  agy -p "$(cat "$PROMPT_FILE")" --disable-slash-commands >"$log" 2>&1
  rc=$?

  if grep -Eiq 'quota|rate.?limit|billing|authentication|unauthorized|forbidden|2fa|captcha' "$log"; then
    echo "[agy-relauncher] provider/auth gate detected; not probing repeatedly. See $log" >&2
    exit 20
  fi

  echo "[agy-relauncher] worker returned rc=$rc; relaunch after ${SLEEP_SECONDS}s"
  sleep "$SLEEP_SECONDS"
done

echo "[agy-relauncher] MAX_HOURS reached"
