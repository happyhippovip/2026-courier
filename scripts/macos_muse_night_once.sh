#!/bin/bash
# One non-overlapping, read-only Muse night-batch invocation.
# Intended for launchd or manual use. Does not require an open Muse terminal.
set -u

REPO_ROOT="${COURIER_REPO_ROOT:-}"
if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

STATE_DIR="${COURIER_NIGHT_STATE_DIR:-$HOME/.courier/dev-night}"
PROMPT_FILE="${COURIER_NIGHT_PROMPT_FILE:-$REPO_ROOT/ops/orchestration/muse_night_prompt.txt}"
LOCK_DIR="${COURIER_NIGHT_LOCK_DIR:-/tmp/courier-v1/muse-night-runner.lock}"
LOG_FILE="$STATE_DIR/runner.log"
PAUSE_FILE="$STATE_DIR/RESOURCE_PAUSE"
BACKOFF_FILE="$STATE_DIR/BACKOFF_UNTIL"
BACKOFF_SECONDS="${COURIER_NIGHT_BACKOFF_SECONDS:-900}"

mkdir -p "$STATE_DIR"
mkdir -p "$(dirname "$LOCK_DIR")"

now_epoch() { date +%s; }

if [ -f "$PAUSE_FILE" ]; then
  echo "COURIER_NIGHT_RESOURCE_PAUSE: $PAUSE_FILE exists"
  exit 75
fi

if [ -f "$BACKOFF_FILE" ]; then
  now="$(now_epoch)"
  until_epoch="$(cat "$BACKOFF_FILE" 2>/dev/null || echo 0)"
  case "$until_epoch" in
    ''|*[!0-9]*) until_epoch=0 ;;
  esac
  if [ "$now" -lt "$until_epoch" ]; then
    echo "COURIER_NIGHT_BACKOFF until $until_epoch"
    exit 0
  fi
  rm -f "$BACKOFF_FILE"
fi

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    return 0
  fi

  old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || echo '')"
  case "$old_pid" in
    ''|*[!0-9]*) old_pid="" ;;
  esac

  if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
    echo "COURIER_NIGHT_SKIP_ACTIVE pid=$old_pid"
    return 1
  fi

  rm -rf "$LOCK_DIR" 2>/dev/null || return 1
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_DIR/pid"
    return 0
  fi
  return 1
}

if ! acquire_lock; then
  exit 0
fi

cleanup() {
  rm -rf "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [ ! -f "$PROMPT_FILE" ]; then
  echo "Missing prompt file: $PROMPT_FILE" >&2
  exit 66
fi

if ! command -v muse >/dev/null 2>&1; then
  echo "Muse executable not found in PATH" >&2
  echo $(( $(now_epoch) + BACKOFF_SECONDS )) > "$BACKOFF_FILE"
  exit 127
fi

# Cap the persistent log without starting a log-management daemon.
if [ -f "$LOG_FILE" ]; then
  bytes="$(wc -c < "$LOG_FILE" 2>/dev/null | tr -d ' ')"
  case "$bytes" in
    ''|*[!0-9]*) bytes=0 ;;
  esac
  if [ "$bytes" -gt 5242880 ]; then
    mv -f "$LOG_FILE" "$LOG_FILE.1"
  fi
fi

run_log="$(mktemp "$STATE_DIR/run.XXXXXX")" || exit 73
trap 'rm -f "$run_log" 2>/dev/null || true; cleanup' EXIT INT TERM

{
  echo
  echo "===== COURIER MUSE NIGHT RUN $(date -u '+%Y-%m-%dT%H:%M:%SZ') ====="
  echo "repo=$REPO_ROOT"
} >> "$LOG_FILE"

cd "$REPO_ROOT" || exit 66

# Follow the checked-out branch so each batch reviews current code instead of
# the commit the runner was installed from. Fast-forward only, and only when
# the checkout is clean; a failed update never blocks a run.
if [ "${COURIER_NIGHT_AUTO_UPDATE:-1}" = "1" ]; then
  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    if git pull --ff-only --quiet >/dev/null 2>&1; then
      echo "update=ok head=$(git rev-parse --short HEAD 2>/dev/null)" >> "$LOG_FILE"
    else
      echo "update=skipped (no fast-forward, no upstream or offline)" >> "$LOG_FILE"
    fi
  else
    echo "update=skipped (checkout not clean)" >> "$LOG_FILE"
  fi
fi

muse exec --prompt-file "$PROMPT_FILE" >"$run_log" 2>&1
rc=$?

cat "$run_log" >> "$LOG_FILE"
cat "$run_log"

resource_pause=0
if grep -q 'COURIER_NIGHT_RESOURCE_PAUSE' "$run_log"; then
  resource_pause=1
elif [ "$rc" -ne 0 ] && grep -Eqi 'Too many open files.*os error 24|EMFILE|os error 24' "$run_log"; then
  resource_pause=1
fi

if [ "$resource_pause" -eq 1 ]; then
  {
    echo "RESOURCE_PAUSE detected $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "Clear this file manually only after host pressure is resolved."
  } > "$PAUSE_FILE"
  echo "COURIER_NIGHT_RESOURCE_PAUSE"
  exit 75
fi

if [ "$rc" -ne 0 ]; then
  next=$(( $(now_epoch) + BACKOFF_SECONDS ))
  echo "$next" > "$BACKOFF_FILE"
  echo "COURIER_NIGHT_PROVIDER_BACKOFF rc=$rc until=$next" >&2
  exit "$rc"
fi

rm -f "$BACKOFF_FILE"
exit 0
