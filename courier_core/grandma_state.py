"""Grandma State Mapping (Dual-Surface Truth).

Translates internal engine ledger state into a truthful, human-comprehensible
4-state user summary answering the three fundamental questions:
1. Arbeitet Courier gerade? -> ARBEITET
2. Braucht Courier mich? -> BRAUCHT_DICH
3. Ist Courier fertig? -> FERTIG
4. Wartet Courier auf einen Worker? -> WARTET_AUF_KAPAZITAET

Specification: ops/ai/USER_REQUIREMENT_01_GRANDMA_STATE_MAPPING.md
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

# Four canonical Grandma States (Dual-Surface Truth)
STATE_FERTIG = "FERTIG"
STATE_BRAUCHT_DICH = "BRAUCHT_DICH"
STATE_ARBEITET = "ARBEITET"
STATE_WARTET_AUF_KAPAZITAET = "WARTET_AUF_KAPAZITAET"

CANONICAL_STATES = {
    STATE_FERTIG,
    STATE_BRAUCHT_DICH,
    STATE_ARBEITET,
    STATE_WARTET_AUF_KAPAZITAET,
}

# Heartbeat freshness threshold in seconds
DEFAULT_HEARTBEAT_WINDOW = 300.0


def derive_user_state(
    goal: Dict[str, Any],
    state: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
    heartbeat_window: float = DEFAULT_HEARTBEAT_WINDOW,
) -> Dict[str, Any]:
    """Deterministically map a goal and system state to a user-facing summary.

    Parameters:
        goal: The goal dict containing 'status', 'workflow_plan', 'current_step_index'.
        state: The overall engine state dict containing 'workers', 'tasks', etc.
        now: Current Unix timestamp (defaults to time.time() if None).
        heartbeat_window: Max elapsed seconds for a worker heartbeat to be considered fresh.

    Returns:
        Dict with keys:
            user_state: 'FERTIG' | 'BRAUCHT_DICH' | 'ARBEITET' | 'WARTET_AUF_KAPAZITAET'
            user_message: Human-friendly explanation without raw internal stack traces
            action_required: bool indicating if human intervention is necessary
            action_type: Optional string ('RESUME_OR_RETRY', 'HUMAN_INPUT', None)
            step_progress: Optional dict {'current': X, 'total': Y}
    """
    if now is None:
        now = time.time()

    if state is None:
        state = {}

    goal_status = goal.get("status", "ACTIVE")
    workflow_plan = goal.get("workflow_plan", [])
    step_index = goal.get("current_step_index", 0)
    total_steps = len(workflow_plan)

    step_progress = {
        "current": min(step_index + 1, total_steps) if total_steps > 0 else 0,
        "total": total_steps,
    }

    # 1. Check FERTIG: goal is marked DONE or all workflow steps are RECONCILED/COMPLETED
    if goal_status == "DONE":
        return {
            "user_state": STATE_FERTIG,
            "user_message": "Alle Aufgaben wurden erfolgreich abgeschlossen und verifiziert.",
            "action_required": False,
            "action_type": None,
            "step_progress": step_progress,
        }

    # Reconciled steps are the only step status the runtime records as finished.
    # SUCCESS, DONE, and COMPLETED are not that proof.
    if workflow_plan and all(
        isinstance(step, dict) and step.get("status") == "RECONCILED"
        for step in workflow_plan
    ):
        return {
            "user_state": STATE_FERTIG,
            "user_message": "Alle Aufgaben wurden erfolgreich abgeschlossen und verifiziert.",
            "action_required": False,
            "action_type": None,
            "step_progress": step_progress,
        }

    # 2. Check BRAUCHT_DICH: explicit BLOCKED, HUMAN_REQUIRED, or terminal failure
    if goal_status == "BLOCKED":
        blocker_reason = goal.get("blocked_reason") or goal.get("error")
        clean_msg = _sanitize_user_message(blocker_reason) if blocker_reason else "Courier ist blockiert und benoetigt deine Freigabe."
        return {
            "user_state": STATE_BRAUCHT_DICH,
            "user_message": clean_msg,
            "action_required": True,
            "action_type": "RESUME_OR_RETRY",
            "step_progress": step_progress,
        }

    # Inspect current active step
    current_step: Optional[Dict[str, Any]] = None
    if 0 <= step_index < total_steps:
        current_step = workflow_plan[step_index]

    if current_step:
        step_status = current_step.get("status", "QUEUED")
        task_id = current_step.get("task_id", "")
        target_agent = current_step.get("target_agent") or current_step.get("platform") or "Worker"

        # Check for step failure / human input required
        if step_status in ("HUMAN_REQUIRED", "FAILED_TERMINAL", "FAILED_VERIFICATION", "ERROR"):
            reason = current_step.get("error") or current_step.get("failure_reason")
            clean_msg = _sanitize_user_message(reason) if reason else f"Schritt {step_index + 1} benoetigt deine Pruefung oder Bestaetigung."
            return {
                "user_state": STATE_BRAUCHT_DICH,
                "user_message": clean_msg,
                "action_required": True,
                "action_type": "RESUME_OR_RETRY",
                "step_progress": step_progress,
            }

        # Check for ARBEITET: DISPATCHED or RESULT_RECEIVED with active worker
        if step_status in ("DISPATCHED", "RESULT_RECEIVED", "ACTIVE", "RUNNING"):
            worker_active = _is_worker_active_for_task(state.get("workers", {}), task_id, now, heartbeat_window)
            if worker_active:
                step_num = step_index + 1
                return {
                    "user_state": STATE_ARBEITET,
                    "user_message": f"Courier arbeitet selbstaendig an Schritt {step_num} von {total_steps}.",
                    "action_required": False,
                    "action_type": None,
                    "step_progress": step_progress,
                }
            else:
                # Dispatched but worker heartbeat is stale or missing
                return {
                    "user_state": STATE_BRAUCHT_DICH,
                    "user_message": f"Worker fuer Schritt {step_index + 1} reagiert nicht mehr (Heartbeat abgelaufen). Pruefe den Worker-Dienst.",
                    "action_required": True,
                    "action_type": "RESUME_OR_RETRY",
                    "step_progress": step_progress,
                }

        # Check for WARTET_AUF_KAPAZITAET: QUEUED
        if step_status == "QUEUED":
            return {
                "user_state": STATE_WARTET_AUF_KAPAZITAET,
                "user_message": f"Courier wartet auf einen verfuegbaren Worker fuer Plattform {target_agent}.",
                "action_required": False,
                "action_type": None,
                "step_progress": step_progress,
            }

    # If no steps defined yet or general active state
    if total_steps == 0:
        return {
            "user_state": STATE_WARTET_AUF_KAPAZITAET,
            "user_message": "Courier initialisiert den Arbeitsplan.",
            "action_required": False,
            "action_type": None,
            "step_progress": step_progress,
        }

    # Default fallback to honest working state
    return {
        "user_state": STATE_ARBEITET,
        "user_message": f"Courier verarbeitet Zielschritte ({step_index + 1}/{total_steps}).",
        "action_required": False,
        "action_type": None,
        "step_progress": step_progress,
    }


def _is_worker_active_for_task(
    workers: Dict[str, Any],
    task_id: str,
    now: float,
    heartbeat_window: float,
) -> bool:
    """Check if any registered worker is actively computing the specified task with a fresh heartbeat."""
    for worker_id, worker in workers.items():
        if not isinstance(worker, dict):
            continue
        last_seen = worker.get("last_seen", 0)
        is_fresh = (now - last_seen) <= heartbeat_window
        if is_fresh and worker.get("current_task") == task_id:
            return True

    return False


def _sanitize_user_message(raw: Optional[str]) -> str:
    """Filter raw internal stack traces or technical dumps into clear, honest explanations."""
    if not raw:
        return "Courier benoetigt Pruefung."
    s = str(raw).strip()
    # Strip Python exception prefixes
    for prefix in ("Exception:", "Error:", "RuntimeError:", "ValueError:", "AssertionError:"):
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
    # If it contains a stack trace, truncate to the first readable explanation
    if "Traceback (most recent call last)" in s:
        lines = [line.strip() for line in s.splitlines() if line.strip()]
        s = lines[-1] if lines else "Unerwarteter Systemzustand."
    # Limit length
    if len(s) > 160:
        s = s[:157] + "..."
    return s
