"""Courier Mailbox Autopilot — Asynchronous Task Processing.

Allows agents and human users to queue tasks in an inbox.jsonl file without
requiring manual copy-pasting between chat windows.
Enforces P0 CostGate (fail-closed, 0.00 EUR limit) and deterministic verification.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from courier_hub.mission_chip import run_mission_chip


def _get_resource_pause_file() -> Path:
    base = os.environ.get("COURIER_HOME")
    if base:
        return Path(base) / "dev-night" / "RESOURCE_PAUSE"
    return Path.home() / ".courier" / "dev-night" / "RESOURCE_PAUSE"


def process_inbox(inbox_path: Path, outbox_path: Path, home_path: Path | None = None) -> list[dict[str, Any]]:
    """Process all pending tasks from inbox.jsonl."""
    if _get_resource_pause_file().exists():
        print("[MAILBOX] RESOURCE_PAUSE is active. Aborting run fail-closed.", file=sys.stderr)
        return []

    if not inbox_path.exists():
        return []

    lines = inbox_path.read_text(encoding="utf-8").splitlines()
    tasks = []
    for line in lines:
        if line.strip():
            try:
                tasks.append(json.loads(line))
            except Exception:
                pass

    executed = []
    updated_lines = []

    for task in tasks:
        task_id = task.get("task_id", f"task-{int(time.time()*1000)}")
        status = task.get("status", "PENDING")

        if status == "PENDING":
            # P0 CostGate Check
            est_cost = task.get("estimated_cost_eur", 0.0)
            if est_cost is None or est_cost > 0.0:
                task["status"] = "BLOCKED_COSTGATE"
                task["resolution"] = "COSTGATE_REJECTED"
                task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                updated_lines.append(json.dumps(task))
                continue

            print(f"[MAILBOX] Executing task: {task_id} ({task.get('name', 'unnamed')})")
            
            # Execute deterministically
            res = run_mission_chip(target_home=home_path)
            
            task["status"] = "DONE"
            task["resolution"] = res["verifier_result"]["resolution"]
            task["accepted_result_id"] = res["verifier_result"]["accepted_result_id"]
            task["artifact_sha256"] = res["verifier_result"]["artifact_sha256"]
            task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            
            outbox_entry = {
                "task_id": task_id,
                "inbox_task": task,
                "execution_result": res,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with outbox_path.open("a", encoding="utf-8") as out_f:
                out_f.write(json.dumps(outbox_entry) + "\n")
                
            executed.append(outbox_entry)

        updated_lines.append(json.dumps(task))

    # Atomically write back updated inbox
    tmp_inbox = inbox_path.with_suffix(".tmp")
    tmp_inbox.write_text("\n".join(updated_lines) + ("\n" if updated_lines else ""), encoding="utf-8")
    tmp_inbox.replace(inbox_path)

    return executed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Courier Autonomous Mailbox Runner")
    parser.add_argument("--inbox", type=Path, default=Path("/Users/user/.courier/dev-night/inbox.jsonl"))
    parser.add_argument("--outbox", type=Path, default=Path("/Users/user/.courier/dev-night/outbox.jsonl"))
    parser.add_argument("--home", type=Path, default=None)
    args = parser.parse_args(argv)

    args.inbox.parent.mkdir(parents=True, exist_ok=True)
    results = process_inbox(args.inbox, args.outbox, home_path=args.home)
    print(f"[MAILBOX] Run finished. Executed {len(results)} task(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
