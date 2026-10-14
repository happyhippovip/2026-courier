"""Personal Courier Project Base projection (lane L5).

Pure deterministic functions projecting canonical runtime and ledger truth into
the founder's unified Project Base:

1. NEEDS YOU | WORKING | DONE (canonical piles & counts)
2. Current workkeys and assigned workers/providers
3. Last verified result and evidence
4. What changed while the founder was away
5. The next safe action
6. Durable project context across new sessions

The hub keeps no state of its own; this is a pure projection over Journal tasks,
journal events and optional project memory context.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, Iterable, List, Optional

from courier_hub import model
from courier_hub.model import (
    PILE_DONE,
    PILE_NEEDS_YOU,
    PILE_WORKING,
    WORKING_STATUSES,
    _get,
    _payload,
    _status,
    _type,
    copy_for,
    display_actor,
    done_outcome,
    title_of,
)


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_workkeys(tasks: Iterable[Any], events_by_task: Optional[Dict[str, List[Any]]] = None) -> List[Dict[str, Any]]:
    """Extract active workkeys with assigned workers/providers."""
    events_by_task = events_by_task or {}
    workkeys = []

    for task in tasks:
        st = _status(task)
        # Active workkeys: tasks in working or blocked statuses
        if st in WORKING_STATUSES or st == "BLOCKED":
            task_id = _get(task, "task_id")
            params = _get(task, "params", {})
            if isinstance(params, str):
                try:
                    import json
                    params = json.loads(params)
                except Exception:
                    params = {}

            workkey = params.get("workkey") or params.get("key") or task_id
            worker_id = _get(task, "worker_id") or "unassigned"
            dispatch_id = _get(task, "dispatch_id")
            adapter = _get(task, "adapter") or "unknown"
            attempt = _get(task, "attempt", 1)
            lease_ttl_s = _get(task, "lease_ttl_s")

            # Extract start timestamp if present in events
            started_at = None
            for ev in events_by_task.get(task_id, []):
                if _type(ev) in ("TASK_STARTED", "TASK_CLAIMED"):
                    started_at = _get(ev, "ts_utc")
                    break

            workkeys.append({
                "workkey": workkey,
                "task_id": task_id,
                "title": title_of(task),
                "adapter": adapter,
                "worker_id": worker_id,
                "dispatch_id": dispatch_id,
                "status": st,
                "attempt": attempt,
                "lease_ttl_s": lease_ttl_s,
                "started_at": started_at,
            })

    # Sort: blocked first, then by attempt descending
    workkeys.sort(key=lambda w: (0 if w["status"] == "BLOCKED" else 1, -w["attempt"], w["workkey"]))
    return workkeys


def extract_last_verified_result(tasks: Iterable[Any], events_by_task: Optional[Dict[str, List[Any]]] = None) -> Optional[Dict[str, Any]]:
    """Find the most recent task with a verified outcome and evidence."""
    events_by_task = events_by_task or {}
    candidates = []

    for task in tasks:
        st = _status(task)
        res = _get(task, "resolution")
        if st == "COMPLETE" and res == "verified":
            task_id = _get(task, "task_id")
            ev_list = events_by_task.get(task_id, [])
            
            # Find the acceptance event
            accepted_ev = None
            evidence_artifacts = []
            for ev in ev_list:
                t = _type(ev)
                if t in ("RESULT_ACCEPTED", "TASK_COMPLETE") and accepted_ev is None:
                    accepted_ev = ev
                if t == "RESULT_READY":
                    for art in _payload(ev).get("artifacts") or []:
                        if isinstance(art, dict) and art.get("path"):
                            evidence_artifacts.append({
                                "name": str(art["path"]).rsplit("/", 1)[-1],
                                "path": art["path"],
                                "hash": art.get("sha256") or art.get("hash"),
                            })

            latest_seq = _get(accepted_ev, "seq") if accepted_ev else _get(task, "updated_seq", 0)
            verified_at = _get(accepted_ev, "ts_utc") if accepted_ev else None
            ev_hash = _get(accepted_ev, "hash") if accepted_ev else None

            candidates.append({
                "seq": latest_seq or 0,
                "task_id": task_id,
                "title": title_of(task),
                "result_id": _get(task, "accepted_result_id"),
                "verified_at": verified_at,
                "evidence": evidence_artifacts,
                "how_known": "Checked by Courier: the result matched the verified evidence.",
                "hash": ev_hash,
            })

    if not candidates:
        return None

    # Highest sequence number is the most recent
    candidates.sort(key=lambda c: c["seq"], reverse=True)
    return candidates[0]


def calculate_away_summary(events: Iterable[Any], since_seq: int = 0) -> Dict[str, Any]:
    """Calculate what changed while the founder was away since given sequence."""
    events = list(events)
    if since_seq is None or since_seq < 0:
        since_seq = 0

    unseen = [e for e in events if (_get(e, "seq") or 0) > since_seq]
    completed = []
    blocked = []
    failed = []
    started = []
    milestones = []

    for ev in unseen:
        seq = _get(ev, "seq")
        t = _type(ev)
        task_id = _get(ev, "task_id")
        ts = _get(ev, "ts_utc")
        payload = _payload(ev)

        if t == "TASK_COMPLETE":
            completed.append({"task_id": task_id, "at": ts, "seq": seq})
            milestones.append({"seq": seq, "at": ts, "kind": "COMPLETE", "summary": f"Task {task_id} completed"})
        elif t == "TASK_BLOCKED":
            reason = payload.get("reason", "Question for person")
            blocked.append({"task_id": task_id, "at": ts, "seq": seq, "reason": reason})
            milestones.append({"seq": seq, "at": ts, "kind": "BLOCKED", "summary": f"Task {task_id} blocked: {reason}"})
        elif t == "TASK_FAILED":
            reason = payload.get("reason", "Failure")
            failed.append({"task_id": task_id, "at": ts, "seq": seq, "reason": reason})
            milestones.append({"seq": seq, "at": ts, "kind": "FAILED", "summary": f"Task {task_id} failed: {reason}"})
        elif t == "TASK_STARTED":
            worker_id = _get(ev, "worker_id") or "worker"
            started.append({"task_id": task_id, "at": ts, "seq": seq, "worker_id": worker_id})
            milestones.append({"seq": seq, "at": ts, "kind": "STARTED", "summary": f"Task {task_id} started by {worker_id}"})
        elif t == "RESULT_ACCEPTED":
            milestones.append({"seq": seq, "at": ts, "kind": "VERIFIED", "summary": f"Result accepted and verified for {task_id}"})

    return {
        "since_seq": since_seq,
        "events_count": len(unseen),
        "completed_count": len(completed),
        "blocked_count": len(blocked),
        "failed_count": len(failed),
        "started_count": len(started),
        "completed_tasks": completed,
        "blocked_tasks": blocked,
        "failed_tasks": failed,
        "started_tasks": started,
        "milestones": milestones[-15:],  # up to 15 recent milestones
    }


def calculate_next_safe_action(piles: Dict[str, List[Any]], controller_status: str = "running") -> Dict[str, Any]:
    """Calculate the next safe deterministic action for the founder."""
    needs_you = piles.get(PILE_NEEDS_YOU, [])
    working = piles.get(PILE_WORKING, [])

    # 1. Action required: human decision needed
    if needs_you:
        first = needs_you[0]
        task_id = first.get("id")
        title = first.get("title", "Courier task")
        next_prompt = first.get("next") or "A decision is required before Courier can continue."
        return {
            "type": "DECISION_REQUIRED",
            "urgency": "HIGH",
            "title": f"Review decision: {title}",
            "description": next_prompt,
            "task_id": task_id,
            "actions_offered": ["effect_confirmed", "retry_authorized", "cancel"],
        }

    # 2. Attention: controller inactive or in safe mode
    if controller_status != "running":
        return {
            "type": "CONTROLLER_INACTIVE",
            "urgency": "HIGH",
            "title": "Controller not running",
            "description": f"Controller status is '{controller_status}'. Inspect local Courier daemon.",
            "task_id": None,
            "actions_offered": [],
        }

    # 3. Execution in progress: monitor
    if working:
        adapters = sorted({w.get("authority", {}).get("note", "") for w in working if w.get("authority")})
        return {
            "type": "MONITOR_EXECUTION",
            "urgency": "NORMAL",
            "title": f"Courier is working ({len(working)} active)",
            "description": "Background workers are progressing autonomously. No manual action required.",
            "task_id": None,
            "actions_offered": ["stop"],
        }

    # 4. Ready: all idle and verified
    return {
        "type": "IDLE_READY",
        "urgency": "LOW",
        "title": "System idle and verified",
        "description": "All past tasks have finished and verified. System is ready for the next workkey.",
        "task_id": None,
        "actions_offered": ["dispatch_task"],
    }


def get_durable_context(head_seq: Optional[int], head_hash: Optional[str],
                        total_tasks: int, total_events: int,
                        memory_repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Assemble durable project context across sessions."""
    ctx = {
        "repository": "happyhippovip/2026-courier",
        "trunk_branch": "integration/v1",
        "head_seq": head_seq or 0,
        "head_hash": head_hash or "",
        "total_tasks": total_tasks,
        "total_events": total_events,
        "generated_at": _utc_now(),
        "project_memory": None,
    }

    # Optional integration with Context Fabric / 2026-project-memory
    try:
        import sys
        from pathlib import Path
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import resolve_project_memory as rpm
        mem_path = Path(memory_repo_path) if memory_repo_path else rpm.DEFAULT_MEMORY_REPO_PATH
        if mem_path.exists():
            pkg = rpm.build_memory_context_package(mem_path, instruction="founder project base")
            ctx["project_memory"] = {
                "commit": pkg.get("memory_commit"),
                "files_consulted": pkg.get("files_consulted", []),
                "status_labels": pkg.get("status_labels", {}),
            }
    except Exception:
        pass

    return ctx


def build_project_base(tasks: Iterable[Any], events_by_task: Dict[str, List[Any]],
                       all_events: Optional[List[Any]] = None,
                       head: Optional[tuple] = None,
                       controller_status: str = "running",
                       since_seq: int = 0,
                       memory_repo_path: Optional[str] = None) -> Dict[str, Any]:
    """Build the complete personal Courier Project Base projection."""
    tasks = list(tasks)
    home_view = model.home(tasks, events_by_task)
    piles = {
        PILE_NEEDS_YOU: home_view["needs_you"],
        PILE_WORKING: home_view["working"],
        PILE_DONE: home_view["done"],
    }

    head_seq = head[0] if head else 0
    head_hash = head[1] if head and len(head) > 1 else ""

    workkeys = extract_workkeys(tasks, events_by_task)
    last_verified = extract_last_verified_result(tasks, events_by_task)
    away = calculate_away_summary(all_events or [], since_seq=since_seq)
    next_action = calculate_next_safe_action(piles, controller_status=controller_status)
    context = get_durable_context(head_seq, head_hash, len(tasks), len(all_events or []), memory_repo_path)

    return {
        "piles": piles,
        "counts": {
            "needs_you": len(piles[PILE_NEEDS_YOU]),
            "working": len(piles[PILE_WORKING]),
            "done": home_view["counts"]["done"],
            "active_workkeys": len(workkeys),
        },
        "current_workkeys": workkeys,
        "last_verified_result": last_verified,
        "away_summary": away,
        "next_safe_action": next_action,
        "durable_context": context,
        "read_at": _utc_now(),
    }
