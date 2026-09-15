#!/usr/bin/env bash
set -euo pipefail

: "${COURIER_STATE_DIR:=/var/lib/courier}"
: "${COURIER_POLL_SECONDS:=60}"
: "${COURIER_MAX_TASKS:=10}"
: "${COURIER_MAX_RUNTIME_MINUTES:=60}"
: "${COURIER_MAX_RETRIES_PER_TASK:=2}"
: "${COURIER_REPORT_RETENTION_DAYS:=30}"
: "${COURIER_MEMORY_DRY_RUN:=true}"
: "${COURIER_ALLOWED_TARGET_AGENTS:=}"

case "$COURIER_MEMORY_DRY_RUN" in
  true|false) ;;
  *) echo "COURIER_MEMORY_DRY_RUN must be true or false" >&2; exit 2 ;;
esac

events_dir="$COURIER_STATE_DIR/events"
queue_dir="$events_dir/night-queue"
reports_dir="$events_dir/morning-reports"
mkdir -p "$queue_dir" "$reports_dir"

validate_queued_targets() {
  python3 - "$queue_dir" "$COURIER_ALLOWED_TARGET_AGENTS" <<'PY'
import json
import sys
from pathlib import Path

queue_dir = Path(sys.argv[1])
allowed_targets = {item.strip().upper() for item in sys.argv[2].split(",") if item.strip()}
errors = []

for task_path in sorted(queue_dir.glob("*.json")):
    try:
        task = json.loads(task_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{task_path.name}: unreadable task ({exc})")
        continue
    if task.get("status") not in {"QUEUED", "FAILED_RETRYABLE"}:
        continue
    target = task.get("target_agent")
    if not isinstance(target, str) or not target.strip():
        errors.append(f"{task_path.name}: queued task has no target_agent")
    elif target.strip().upper() not in allowed_targets:
        errors.append(f"{task_path.name}: target_agent {target!r} is not explicitly allowed")

if errors:
    print("Courier deployment is holding queued work fail-closed:", file=sys.stderr)
    print("\n".join(errors), file=sys.stderr)
    sys.exit(1)
PY
}

while true; do
  if ! validate_queued_targets; then
    sleep "$COURIER_POLL_SECONDS"
    continue
  fi

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
