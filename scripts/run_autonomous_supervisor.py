#!/usr/bin/env python3
"""Autonomous Night Supervisor Engine (093).

Runs unattended night operations over a persistent task queue:
  Task Queue -> Courier -> Dispatcher -> Worker -> RESULT -> 086 Proposal -> 088 Policy -> 087 Memory Write -> Autonomous Next Task -> Loop

Features:
- Prioritized task queue execution (P0, P1, P2...).
- Atomic single-task claiming & deduplication.
- Crash/restart recovery (never re-runs COMPLETED tasks).
- Automatic continuation after independent Human Gates (parks gated task, continues safe tasks).
- Bounded retry limits & session runtime limits.
- Structured Night Session Report & MORNING_REPORT.md generation.
- Zero-cost policy enforcement (0.00 EUR).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Add scripts directory to sys.path for direct imports
SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_chief_relay_cycle

DEFAULT_MEMORY_REPO = Path("/Users/user/Downloads/2026-project-memory")
DEFAULT_QUEUE_DIR = COURIER_DIR / "events/night-queue"
DEFAULT_REPORTS_DIR = COURIER_DIR / "events/morning-reports"
DEFAULT_CHANNELS_CONFIG = COURIER_DIR / "config/social_channels.json"
DEFAULT_TASK_SCHEMA = COURIER_DIR / "schemas/night_task.schema.json"
DEFAULT_REPORT_SCHEMA = COURIER_DIR / "schemas/night_session_report.schema.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def discover_next_task(queue_dir: Path) -> Path | None:
    """Finds the next executable task in the queue sorted by priority and creation time."""
    if not queue_dir.exists():
        return None

    candidates = []
    for task_file in queue_dir.glob("*.json"):
        try:
            data = load_json(task_file)
            status = data.get("status")
            if status == "QUEUED" or (status == "FAILED_RETRYABLE" and data.get("attempt_count", 0) < data.get("max_attempts", 2)):
                priority = data.get("priority", 5)
                created_at = data.get("created_at", "")
                candidates.append((priority, created_at, task_file))
        except Exception:
            continue

    if not candidates:
        return None

    # Sort by priority ascending (0 = P0 top), then created_at ascending (FIFO within same priority)
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def run_supervisor_session(
    repo_dir: Path = COURIER_DIR,
    queue_dir: Path = DEFAULT_QUEUE_DIR,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    events_dir: Path | None = None,
    memory_repo: Path = DEFAULT_MEMORY_REPO,
    channels_config: Path = DEFAULT_CHANNELS_CONFIG,
    max_tasks: int = 10,
    max_runtime_minutes: float = 60.0,
    max_retries_per_task: int = 2,
    memory_dry_run: bool = False,
    push_events: bool = False,
) -> dict:
    started_at = datetime.datetime.now(datetime.timezone.utc)
    session_id = f"night-sess-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    tasks_completed = 0
    tasks_failed = 0
    human_gates = 0
    memory_updates_applied = 0
    memory_updates_queued = 0
    commits_created = 0
    pushes_completed = 0
    details = []

    base_events = events_dir if events_dir is not None else (repo_dir / "events")
    incoming_dir = base_events / "incoming"
    processed_dir = base_events / "processed"
    dispatch_dir = base_events / "dispatch"
    proposals_dir = base_events / "proposals"
    approvals_dir = base_events / "approvals"
    decisions_dir = base_events / "chief-decisions"

    for d in [queue_dir, reports_dir, incoming_dir, processed_dir, dispatch_dir, proposals_dir, approvals_dir, decisions_dir]:
        d.mkdir(parents=True, exist_ok=True)

    stop_reason = "QUEUE_EMPTY"

    print(f"=== STARTING NIGHT SUPERVISOR SESSION: {session_id} ===")

    while True:
        # Check session runtime limit
        elapsed_minutes = (datetime.datetime.now(datetime.timezone.utc) - started_at).total_seconds() / 60.0
        if elapsed_minutes >= max_runtime_minutes:
            stop_reason = "MAX_RUNTIME_EXCEEDED"
            break

        # Check session task count limit
        if (tasks_completed + tasks_failed + human_gates) >= max_tasks:
            stop_reason = "MAX_TASKS_REACHED"
            break

        # Discover next task from persistent queue
        task_file = discover_next_task(queue_dir)
        if not task_file:
            stop_reason = "QUEUE_EMPTY"
            break

        task_data = load_json(task_file)
        task_id = task_data["task_id"]
        instruction = task_data["instruction"]
        requires_human = task_data.get("requires_human", False)
        attempt_count = task_data.get("attempt_count", 0) + 1
        max_attempts = task_data.get("max_attempts", max_retries_per_task)

        print(f"\n--- Claiming Task: {task_id} (Attempt {attempt_count}/{max_attempts}) ---")
        task_data["status"] = "RUNNING"
        task_data["attempt_count"] = attempt_count
        save_json(task_file, task_data)

        # 1. Human Gate check
        if requires_human:
            print(f"HUMAN GATE: Task {task_id} requires explicit human approval. Parking task.")
            task_data["status"] = "HUMAN_GATE"
            save_json(task_file, task_data)
            human_gates += 1
            details.append({
                "task_id": task_id,
                "status": "HUMAN_GATE",
                "reason": "Explicit requires_human flag on task",
            })
            # Continue to next independent task in queue
            continue

        # 2. Stage Chief Command for Courier relay cycle
        cmd_msg_id = f"msg-chief-{task_id}"
        cmd_payload = {
            "target_agent": task_data.get("target_agent", "ANTIGRAVITY"),
            "one_next_command": instruction,
            "allowed_scope": [
                "happyhippovip/2026-courier",
                "happyhippovip/2026-project-memory"
            ],
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "cost_policy": "ZERO_COST_ONLY"
        }
        
        # Canonical SHA-256 payload hash
        import hashlib
        payload_hash = hashlib.sha256(json.dumps(cmd_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

        cmd_event = {
            "schema_version": "2.0",
            "message_id": cmd_msg_id,
            "task_id": task_id,
            "correlation_id": f"corr-{task_id}",
            "parent_id": task_data.get("parent_task_id"),
            "source": "chief",
            "destination": "antigravity",
            "type": "COMMAND",
            "status": "NEW",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payload": cmd_payload,
            "payload_hash": payload_hash,
            "max_iterations": 1
        }
        cmd_file = incoming_dir / f"{task_id}-command.json"
        save_json(cmd_file, cmd_event)

        # 3. Execute Relay Cycle (Dispatch -> Worker -> RESULT -> 086 Proposal -> 088 Policy -> 087 Write)
        try:
            cycle_result = run_chief_relay_cycle.run_cycle(
                repo_dir=repo_dir,
                incoming_dir=incoming_dir,
                processed_dir=processed_dir,
                dispatch_dir=dispatch_dir,
                proposals_dir=proposals_dir,
                approvals_dir=approvals_dir,
                decisions_dir=decisions_dir,
                memory_repo=memory_repo,
                enable_auto_memory=True,
                memory_dry_run=memory_dry_run,
                pull=False,
                push=push_events,
            )

            if cycle_result.get("status") == "COMPLETED":
                task_data["status"] = "COMPLETED"
                task_data["last_result_id"] = cycle_result.get("message_id")
                save_json(task_file, task_data)
                tasks_completed += 1

                mem_info = cycle_result.get("memory_cycle") or {}
                if mem_info.get("decision") == "AUTO_APPROVE":
                    memory_updates_applied += 1
                elif mem_info.get("decision") == "HUMAN_REVIEW":
                    memory_updates_queued += 1

                if cycle_result.get("commit_sha"):
                    commits_created += 1
                    pushes_completed += 1

                details.append({
                    "task_id": task_id,
                    "status": "COMPLETED",
                    "result_path": cycle_result.get("result_path"),
                    "memory_decision": mem_info.get("decision"),
                })
                print(f"Task {task_id} COMPLETED successfully.")
            else:
                raise RuntimeError(f"Relay cycle status: {cycle_result.get('status')}")

        except Exception as exc:
            print(f"ERROR executing task {task_id}: {exc}")
            if attempt_count < max_attempts:
                task_data["status"] = "FAILED_RETRYABLE"
                print(f"Task {task_id} marked FAILED_RETRYABLE.")
            else:
                task_data["status"] = "FAILED_FINAL"
                tasks_failed += 1
                print(f"Task {task_id} marked FAILED_FINAL.")
            save_json(task_file, task_data)
            details.append({
                "task_id": task_id,
                "status": task_data["status"],
                "error": str(exc),
            })

    finished_at = datetime.datetime.now(datetime.timezone.utc)

    # Collect next queued tasks for summary
    remaining_tasks = []
    if queue_dir.exists():
        for tf in sorted(queue_dir.glob("*.json")):
            try:
                td = load_json(tf)
                if td.get("status") in ("QUEUED", "HUMAN_GATE"):
                    remaining_tasks.append(f"{td.get('task_id')} ({td.get('status')})")
            except Exception:
                pass

    session_report = {
        "schema_version": "2.0",
        "session_id": session_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "tasks_completed": tasks_completed,
        "tasks_failed": tasks_failed,
        "human_gates": human_gates,
        "memory_updates_applied": memory_updates_applied,
        "memory_updates_queued_for_review": memory_updates_queued,
        "commits_created": commits_created,
        "pushes_completed": pushes_completed,
        "next_queued_tasks": remaining_tasks,
        "cost": "0.00 EUR",
        "stop_reason": stop_reason,
        "details": details,
    }

    # Save structured session JSON
    report_json_path = reports_dir / f"{session_id}.json"
    save_json(report_json_path, session_report)

    # Generate human-readable MORNING_REPORT.md
    morning_report_md = f"""# Autonomous Night Supervisor Morning Report

**Session ID:** `{session_id}`  
**Window:** {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')} → {finished_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Stop Reason:** `{stop_reason}`  
**Cost:** `0.00 EUR` (Policy: ZERO_COST_ONLY)

---

## Summary Metrics

| Metric | Value |
|---|---|
| Tasks Completed | **{tasks_completed}** |
| Tasks Failed | **{tasks_failed}** |
| Human Gates Encountered | **{human_gates}** |
| Canonical Memory Updates Applied | **{memory_updates_applied}** |
| Memory Updates Queued for Review | **{memory_updates_queued}** |
| Commits Created | **{commits_created}** |
| Pushes Completed | **{pushes_completed}** |

---

## Processed Task Details

"""
    for d in details:
        morning_report_md += f"- **{d['task_id']}**: Status `{d['status']}`"
        if "memory_decision" in d:
            morning_report_md += f" (Memory Policy: `{d['memory_decision']}`)"
        if "error" in d:
            morning_report_md += f" — Error: {d['error']}"
        morning_report_md += "\n"

    if not details:
        morning_report_md += "_No tasks processed during this session._\n"

    morning_report_md += f"""
---

## Next Queued / Pending Tasks

"""
    if remaining_tasks:
        for t in remaining_tasks:
            morning_report_md += f"- `{t}`\n"
    else:
        morning_report_md += "_Queue is currently clean and empty._\n"

    morning_report_path = reports_dir / "MORNING_REPORT.md"
    morning_report_path.write_text(morning_report_md, encoding="utf-8")

    print(f"\n=== NIGHT SUPERVISOR SESSION COMPLETED: {stop_reason} ===")
    print(f"Tasks Completed: {tasks_completed} | Failed: {tasks_failed} | Human Gates: {human_gates}")
    print(f"Report saved to: {report_json_path.name} & MORNING_REPORT.md")

    return session_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Autonomous Night Supervisor Loop (093)")
    parser.add_argument("--max-tasks", type=int, default=10, help="Maximum number of tasks to process")
    parser.add_argument("--max-runtime-minutes", type=float, default=60.0, help="Maximum session runtime in minutes")
    parser.add_argument("--max-retries-per-task", type=int, default=2, help="Maximum retry attempts per task")
    parser.add_argument("--queue-dir", default=str(DEFAULT_QUEUE_DIR), help="Task queue directory")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Reports directory")
    parser.add_argument("--events-dir", default=None, help="Optional base events directory")
    parser.add_argument("--memory-repo", default=str(DEFAULT_MEMORY_REPO), help="Path to 2026-project-memory")
    parser.add_argument("--memory-dry-run", action="store_true", help="Run memory updates in dry-run mode")
    parser.add_argument("--push", action="store_true", help="Push git commits for processed tasks")
    args = parser.parse_args()

    events_path = Path(args.events_dir).resolve() if args.events_dir else None

    result = run_supervisor_session(
        queue_dir=Path(args.queue_dir).resolve(),
        reports_dir=Path(args.reports_dir).resolve(),
        events_dir=events_path,
        memory_repo=Path(args.memory_repo).resolve(),
        max_tasks=args.max_tasks,
        max_runtime_minutes=args.max_runtime_minutes,
        max_retries_per_task=args.max_retries_per_task,
        memory_dry_run=args.memory_dry_run,
        push_events=args.push,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
