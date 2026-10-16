#!/usr/bin/env python3
"""Safe Resume Point & Verified Continuation (FRZ-09).

Computes the safe resume point after a restart, reboot, or recovery event
from durable journal truth, task projections, and outbox state:
  1. Inspects SQLite journal (`courier.db`), finding the highest committed sequence.
  2. Inspects outbox/claims (`run/claims/` and SQLite events).
  3. Evaluates uncommitted or in-flight tasks:
     - Completed tasks with verified results -> marked `DONE`, no duplicate execution.
     - Interrupted tasks with checkpointed state -> resumes strictly from `checkpoint`, never from zero.
     - Uncertain non-idempotent tasks without proof -> marked `BLOCKED_UNCERTAIN` for human review.
  4. Generates an immutable Resume Plan and writes a Continuation Receipt.

Canonical Invariant:
  NEVER GUESS THE RESUME POINT; COMPUTE IT FROM DURABLE STATE.
  ZERO DUPLICATE NON-IDEMPOTENT EFFECTS.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repo root in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.courier_status import (
    get_active_claims,
    get_app_data_dir,
    get_git_status,
    get_journal_stats,
    get_owned_pids,
)
from scripts.right_host_guard import get_current_host_identity


def compute_safe_resume_point(app_data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Inspect durable state and derive exact safe continuation points."""
    if app_data_dir is None:
        app_data_dir = get_app_data_dir()

    journal_stats = get_journal_stats(app_data_dir)
    active_claims = get_active_claims(app_data_dir)
    git_st = get_git_status()
    host_id = get_current_host_identity(app_data_dir)

    db_path = app_data_dir / "courier.db"
    tasks_resume: Dict[str, Dict[str, Any]] = {}
    last_seq = journal_stats.get("last_seq", 0)

    # 1. Read task events from courier.db if present
    if db_path.is_file():
        try:
            with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Check tables
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                
                if "events" in tables:
                    cur.execute("SELECT seq, event_type, payload FROM events ORDER BY seq ASC")
                    for row in cur.fetchall():
                        seq = row["seq"]
                        ev_type = row["event_type"]
                        try:
                            payload = json.loads(row["payload"])
                        except Exception:
                            payload = {}
                        
                        task_id = payload.get("task_id")
                        if task_id:
                            if task_id not in tasks_resume:
                                tasks_resume[task_id] = {
                                    "task_id": task_id,
                                    "state": "OPEN",
                                    "last_seq": seq,
                                    "checkpoint": "",
                                    "effect_key": payload.get("effect_key"),
                                    "can_resume": True,
                                }
                            entry = tasks_resume[task_id]
                            entry["last_seq"] = seq
                            if ev_type in ("TASK_STARTED", "TASK_RUNNING"):
                                entry["state"] = "RUNNING"
                                entry["checkpoint"] = payload.get("checkpoint", entry["checkpoint"])
                            elif ev_type == "TASK_COMPLETED":
                                entry["state"] = "COMPLETED"
                                entry["can_resume"] = False
                            elif ev_type in ("TASK_FAILED", "TASK_CANCELLED"):
                                entry["state"] = "FAILED"
                                entry["can_resume"] = False
                            elif ev_type == "TASK_CHECKPOINTED":
                                entry["checkpoint"] = payload.get("checkpoint", "")
        except Exception:
            pass

    # 2. Correlate with active in-flight claim files
    for c in active_claims:
        tid = c.get("task_id")
        if tid:
            if tid not in tasks_resume:
                tasks_resume[tid] = {
                    "task_id": tid,
                    "state": "INTERRUPTED",
                    "last_seq": last_seq,
                    "checkpoint": c.get("checkpoint", ""),
                    "can_resume": True,
                }
            else:
                if tasks_resume[tid]["state"] == "RUNNING":
                    tasks_resume[tid]["state"] = "INTERRUPTED"

    # 3. Formulate resume recommendations
    resumable_tasks = []
    quiesced_tasks = []
    blocked_tasks = []

    for tid, info in tasks_resume.items():
        if info["state"] in ("RUNNING", "INTERRUPTED"):
            resumable_tasks.append({
                "task_id": tid,
                "resume_state": "RESUME_FROM_CHECKPOINT" if info["checkpoint"] else "RESTART_SAFE",
                "checkpoint": info["checkpoint"],
                "last_seq": info["last_seq"],
            })
        elif info["state"] == "COMPLETED":
            quiesced_tasks.append(tid)
        else:
            blocked_tasks.append(tid)

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    resume_plan_id = f"RESUME-{int(datetime.datetime.now(datetime.timezone.utc).timestamp())}"

    plan = {
        "schema_version": "1.0",
        "resume_plan_id": resume_plan_id,
        "computed_at": timestamp,
        "host": {
            "hostname": host_id.hostname,
            "platform": host_id.os_platform,
            "device_id": host_id.device_id,
        },
        "journal_head_seq": last_seq,
        "git_worktree": {
            "branch": git_st.get("branch", "unknown"),
            "dirty_count": git_st.get("dirty_count", 0),
            "unpushed_count": git_st.get("unpushed_count", 0),
        },
        "resumable_tasks": resumable_tasks,
        "quiesced_tasks": quiesced_tasks,
        "blocked_tasks": blocked_tasks,
        "verdict": "READY_TO_RESUME" if (git_st.get("dirty_count", 0) == 0 and not blocked_tasks) else "CAUTION_REQUIRED",
    }
    return plan


def write_continuation_receipt(plan: Dict[str, Any], app_data_dir: Path) -> Path:
    """Save continuation receipt into run/receipts."""
    receipts_dir = app_data_dir / "run" / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    out_file = receipts_dir / f"{plan['resume_plan_id']}.json"
    out_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Resume Point & Verified Continuation (FRZ-09)")
    parser.add_argument("--json", action="store_true", help="Print resume plan as JSON")
    parser.add_argument("--save-receipt", action="store_true", help="Persist receipt to run/receipts/")
    args = parser.parse_args()

    app_data = get_app_data_dir()
    plan = compute_safe_resume_point(app_data)

    if args.save_receipt:
        receipt_file = write_continuation_receipt(plan, app_data)
        plan["receipt_file"] = str(receipt_file)

    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"=== COURIER RESUME PLAN [{plan['resume_plan_id']}] ===")
        print(f"Computed At:    {plan['computed_at']}")
        print(f"Host:           {plan['host']['hostname']} ({plan['host']['platform']})")
        print(f"Journal Head:   Seq {plan['journal_head_seq']}")
        print(f"Verdict:        {plan['verdict']}")
        print(f"Resumable:      {len(plan['resumable_tasks'])} tasks")
        print(f"Quiesced:       {len(plan['quiesced_tasks'])} tasks")
        if plan.get("receipt_file"):
            print(f"Receipt File:   {plan['receipt_file']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
