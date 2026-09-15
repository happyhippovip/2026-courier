#!/usr/bin/env bash
set -euo pipefail

: "${COURIER_STATE_DIR:=/var/lib/courier}"
: "${COURIER_POLL_SECONDS:=60}"
: "${COURIER_MAX_TASKS:=10}"
: "${COURIER_MAX_RUNTIME_MINUTES:=60}"
: "${COURIER_MAX_RETRIES_PER_TASK:=2}"
: "${COURIER_REPORT_RETENTION_DAYS:=30}"
: "${COURIER_MEMORY_DRY_RUN:=true}"

case "$COURIER_MEMORY_DRY_RUN" in
  true|false) ;;
  *) echo "COURIER_MEMORY_DRY_RUN must be true or false" >&2; exit 2 ;;
esac

events_dir="$COURIER_STATE_DIR/events"
queue_dir="$events_dir/night-queue"
reports_dir="$events_dir/morning-reports"
mkdir -p "$queue_dir" "$reports_dir"

while true; do
  args=(
    scripts/run_autonomous_supervisor.py
    --queue-dir "$queue_dir"
    --reports-dir "$reports_dir"
    --events-dir "$events_dir"
    --memory-repo "$COURIER_MEMORY_REPO"
    --max-tasks "$COURIER_MAX_TASKS"
    --max-runtime-minutes "$COURIER_MAX_RUNTIME_MINUTES"
    --max-retries-per-task "$COURIER_MAX_RETRIES_PER_TASK"
  )
  if [[ "$COURIER_MEMORY_DRY_RUN" == true ]]; then
    args+=(--memory-dry-run)
  fi

  python3 "${args[@]}"
  find "$reports_dir" -type f -mtime "+$COURIER_REPORT_RETENTION_DAYS" -delete
  sleep "$COURIER_POLL_SECONDS"
done
