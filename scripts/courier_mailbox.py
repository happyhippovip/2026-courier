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
    """Process all pending tasks from inbox.jsonl under authoritative writer lease."""
    if _get_resource_pause_file().exists():
        print("[MAILBOX] RESOURCE_PAUSE is active. Aborting run fail-closed.", file=sys.stderr)
        return []

    if not inbox_path.exists():
        return []
    for candidate in (inbox_path, outbox_path, home_path):
        if candidate is not None and candidate.is_symlink():
            print("[MAILBOX] Refusing to follow a symlink. Aborting fail-closed.", file=sys.stderr)
            return []

    try:
        from courier_runtime.lease import LeaseConflict, LeaseStore, FencedFileWriter
        auth_db = (home_path or inbox_path.parent) / "authority.db"
        auth_db.parent.mkdir(parents=True, exist_ok=True)
        lease_store = LeaseStore(str(auth_db))
        scope = f"mailbox:{inbox_path.name}"
        holder = f"mailbox_runner:{os.getpid()}"
        lease = lease_store.acquire(scope, holder, "process_inbox", ttl_s=60)
    except Exception as exc:
        print(f"[MAILBOX] Failed to acquire writer lease on {inbox_path.name} ({exc}). Aborting fail-closed.", file=sys.stderr)
        return []

    try:
        lines = inbox_path.read_text(encoding="utf-8").splitlines()
        tasks = []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                print("[MAILBOX] Inbox line is not JSON. Aborting fail-closed.", file=sys.stderr)
                return []
            if not isinstance(item, dict):
                print("[MAILBOX] Inbox line is not an object. Aborting fail-closed.", file=sys.stderr)
                return []
            tasks.append(item)

        executed = []
        updated_lines = []
        seen_ids: set[str] = set()
        if outbox_path.exists() and not outbox_path.is_symlink():
            for prior_line in outbox_path.read_text(encoding="utf-8").splitlines():
                if not prior_line.strip():
                    continue
                try:
                    prior = json.loads(prior_line)
                except json.JSONDecodeError:
                    print("[MAILBOX] Outbox line is not JSON. Aborting fail-closed.", file=sys.stderr)
                    return []
                if not isinstance(prior, dict):
                    print("[MAILBOX] Outbox line is not an object. Aborting fail-closed.", file=sys.stderr)
                    return []
                prior_id = prior.get("task_id")
                if isinstance(prior_id, str) and prior_id and not isinstance(prior_id, bool):
                    seen_ids.add(prior_id)

        for task in tasks:
            raw_id = task.get("task_id")
            if isinstance(raw_id, str) and raw_id:
                task_id = raw_id
            else:
                # A missing id is not a fresh task. Generating one would run
                # every blank line as new work.
                task["status"] = "BLOCKED"
                task["resolution"] = "INVALID_TASK_ID"
                task["reason"] = "Task id must be a non-empty string."
                task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                updated_lines.append(json.dumps(task))
                continue
            status = task.get("status", "PENDING")

            if isinstance(raw_id, str) and raw_id and raw_id in seen_ids:
                if status == "PENDING":
                    task["status"] = "DUPLICATE"
                    task["resolution"] = "IDEMPOTENT_REPLAY"
                    task["reason"] = "The same task_id was already accepted."
                    task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                updated_lines.append(json.dumps(task))
                continue
            if isinstance(raw_id, str) and raw_id:
                seen_ids.add(raw_id)

            if status == "PENDING":
                # P0 CostGate Check: fail closed on missing, non-numeric, or positive cost
                if "estimated_cost_eur" not in task:
                    task["status"] = "BLOCKED_COSTGATE"
                    task["resolution"] = "UNKNOWN_COST"
                    task["reason"] = "Task has no explicit estimated_cost_eur."
                    task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    updated_lines.append(json.dumps(task))
                    continue

                est_cost = task["estimated_cost_eur"]
                import math
                if isinstance(est_cost, bool) or not isinstance(est_cost, (int, float)) or est_cost < 0.0 or est_cost > 0.0 or math.isnan(est_cost) or math.isinf(est_cost):
                    task["status"] = "BLOCKED_COSTGATE"
                    task["resolution"] = "COSTGATE_REJECTED" if (
                        not isinstance(est_cost, bool)
                        and isinstance(est_cost, (int, float))
                        and est_cost > 0.0
                    ) else "UNKNOWN_COST"
                    task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    updated_lines.append(json.dumps(task))
                    continue

                print(f"[MAILBOX] Executing task: {task_id} ({task.get('name', 'unnamed')})")
                
                # Execute deterministically
                res = run_mission_chip(target_home=home_path)
                verifier = res.get("verifier_result") if isinstance(res, dict) else None
                accepted = (
                    isinstance(res, dict)
                    and res.get("overall_status") == "COMPLETE"
                    and isinstance(verifier, dict)
                    and verifier.get("accepted") is True
                    and verifier.get("resolution") == "verified"
                )
                if not accepted:
                    task["status"] = "FAILED"
                    task["resolution"] = "NOT_VERIFIED"
                    task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    updated_lines.append(json.dumps(task))
                    continue

                task["status"] = "DONE"
                task["resolution"] = verifier["resolution"]
                task["accepted_result_id"] = verifier.get("accepted_result_id")
                task["artifact_sha256"] = verifier.get("artifact_sha256")
                task["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                
                outbox_entry = {
                    "task_id": task_id,
                    "inbox_task": task,
                    "execution_result": res,
                    "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                writer = FencedFileWriter(lease_store, f"mailbox:{inbox_path.name}", lease.token, lease.holder)
                with writer.open(outbox_path, "a", encoding="utf-8") as out_f:
                    out_f.write(json.dumps(outbox_entry) + "\n")
                    
                executed.append(outbox_entry)

            updated_lines.append(json.dumps(task))

        # Verify fence before atomic inbox replace
        lease_store.check_write(scope, lease.token, lease.holder)
        tmp_inbox = inbox_path.with_suffix(".tmp")
        tmp_inbox.write_text("\n".join(updated_lines) + ("\n" if updated_lines else ""), encoding="utf-8")
        tmp_inbox.replace(inbox_path)

        return executed
    finally:
        if lease and lease_store:
            try:
                lease_store.release(lease)
                lease_store.close()
            except Exception:
                pass


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
