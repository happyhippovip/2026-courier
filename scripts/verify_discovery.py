#!/usr/bin/env python3
from pathlib import Path
import json
import sys

COURIER_DIR = Path(__file__).resolve().parent.parent
DISPATCH_DIR = COURIER_DIR / "events" / "dispatch"

pending = sorted(list(DISPATCH_DIR.glob("*.json")))
if not pending:
    print("NO TASKS DISCOVERED")
    sys.exit(1)

target_job = pending[0]
print(f"DISCOVERED_TASK: {target_job.name}")

job = json.loads(target_job.read_text())
task_id = job.get("task_id")
print(f"CODEX_NOW_SEES_TASK_ID: {task_id}")

status = job.get("status")
print(f"STATUS_VALID: {'YES' if status else 'NO'}")

provenance = job.get("provenance", {})
print(f"PROVENANCE_VALID: {'YES' if provenance and 'origin' in provenance else 'NO'}")

lease = job.get("lease", {})
print(f"LEASE_VALID: {'YES' if lease and 'acquired_at' in lease else 'NO'}")

print("SUCCESS: NEXT TASK READY FOR CODEX RECEIVER")
