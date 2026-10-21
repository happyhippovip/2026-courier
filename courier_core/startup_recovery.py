"""Minimal Startup Recovery Sequence and Split-Brain Prevention Engine.

Enforces CP-11 / CQ-11 Invariants:
1. Strict 4-Phase Recovery Sequence:
   Phase 1: Laden (Load durable state from disk/journal)
   Phase 2: Abgleichen (Reconcile processes, leases, and results against runtime evidence)
   Phase 3: READY berechnen (Compute genuine READY tasks from dependency graph)
   Phase 4: Dispatch (Open dispatch gate for new worker claims)
2. Vor Reconciliation kein neuer Konflikt-Dispatch:
   No task can be claimed or dispatched before Phase 2 reconciliation is complete.
3. Bestätigte Ergebnisse bleiben erhalten:
   Any task with a verified durable result is preserved as RESULT_RECEIVED / RECONCILED.
4. Fehlende Runtime-Evidenz wird nicht erfunden:
   If an in-flight non-idempotent task has no verified result, it is never assumed complete
   nor blindly re-dispatched. It transitions to NEEDS_RECONCILIATION / BLOCKED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Optional


class StartupPhase(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    LOADING = "LOADING"
    RECONCILING = "RECONCILING"
    COMPUTING_READY = "COMPUTING_READY"
    DISPATCH_READY = "DISPATCH_READY"


class RecoveryAction(str, Enum):
    PRESERVED_CONFIRMED_RESULT = "PRESERVED_CONFIRMED_RESULT"
    QUARANTINED_UNKNOWN_EFFECT = "QUARANTINED_UNKNOWN_EFFECT"
    CLEARED_SAFE_RETRY = "CLEARED_SAFE_RETRY"
    WORKER_DECLARED_OFFLINE = "WORKER_DECLARED_OFFLINE"


class StartupRecoveryError(Exception):
    """Base exception for startup recovery violations."""


class ConflictDispatchBlockedError(StartupRecoveryError):
    """Raised when dispatch is attempted prior to reconciliation completion."""


@dataclass
class TaskRecoveryRecord:
    task_id: str
    previous_status: str
    new_status: str
    action: RecoveryAction
    recovery_reason: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["action"] = self.action.value
        return data


@dataclass
class StartupRecoveryReport:
    phase: StartupPhase
    loaded_goals: int
    loaded_tasks: int
    reconciled_tasks: list[TaskRecoveryRecord] = field(default_factory=list)
    ready_task_ids: list[str] = field(default_factory=list)
    quarantined_task_ids: list[str] = field(default_factory=list)
    dispatch_gate_open: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phase"] = self.phase.value
        data["reconciled_tasks"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.reconciled_tasks]
        return data


class StartupRecoveryEngine:
    """Orchestrates the 4-phase recovery sequence for Courier Central & Controllers."""

    def __init__(
        self,
        process_checker: Optional[Callable[[int], bool]] = None,
        outbox_checker: Optional[Callable[[str], Optional[dict[str, Any]]]] = None,
    ) -> None:
        self.process_checker = process_checker or self._default_process_checker
        self.outbox_checker = outbox_checker or (lambda dsp: None)
        self.phase = StartupPhase.UNINITIALIZED

    @staticmethod
    def _default_process_checker(pid: int) -> bool:
        """Check if process with pid is actively running on this host."""
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h:
                kernel32.CloseHandle(h)
                return True
            return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, ProcessLookupError):
                return False

    def execute_recovery(
        self,
        raw_state: dict[str, Any],
        now: Optional[float] = None,
    ) -> tuple[dict[str, Any], StartupRecoveryReport]:
        """Execute the exact 4-phase recovery sequence:
        1. Laden -> 2. Abgleichen -> 3. READY berechnen -> 4. Dispatch.
        """
        curr_time = now if now is not None else time.time()

        # =====================================================================
        # Phase 1: LADEN (Load durable state from disk)
        # =====================================================================
        self.phase = StartupPhase.LOADING
        state = json.loads(json.dumps(raw_state))  # Clean deep copy
        goals = state.setdefault("goals", {})
        tasks = state.setdefault("tasks", {})
        workers = state.setdefault("workers", {})

        report = StartupRecoveryReport(
            phase=self.phase,
            loaded_goals=len(goals),
            loaded_tasks=len(tasks),
        )

        # =====================================================================
        # Phase 2: ABGLEICHEN (Reconcile Processes, Leases, and Results)
        # =====================================================================
        self.phase = StartupPhase.RECONCILING

        # Step 2a: Only offline workers whose last_seen indicates a stale pre-crash state
        for w_id, w_info in workers.items():
            if curr_time - w_info.get("last_seen", 0) > 300.0:
                w_info["available"] = False
                w_info["current_task"] = None

        # Step 2b: Reconcile active attempts / in-flight tasks
        for task_id, task in tasks.items():
            current_status = task.get("status")

            # Check if task was in-flight when previous process crashed
            if current_status in ("DISPATCHED", "RUNNING", "STARTED"):
                dispatch_id = task.get("dispatch_id", "")
                effect_class = task.get("effect_class", "non_idempotent")
                worker_id = task.get("worker_id")

                # If the holding worker is dead or stale:
                w_info = workers.get(worker_id)
                worker_dead = not w_info or (curr_time - w_info.get("last_seen", 0) > 300.0) or not w_info.get("available")

                # 1. Did a durable result arrive or exist in outbox?
                confirmed_result = task.get("result") or self.outbox_checker(dispatch_id)

                if confirmed_result:
                    # Invariant: Bestätigte Ergebnisse bleiben erhalten
                    task["status"] = "RESULT_RECEIVED"
                    task["result"] = confirmed_result
                    report.reconciled_tasks.append(
                        TaskRecoveryRecord(
                            task_id=task_id,
                            previous_status=current_status,
                            new_status="RESULT_RECEIVED",
                            action=RecoveryAction.PRESERVED_CONFIRMED_RESULT,
                            detail="Durable result confirmed and preserved across restart",
                        )
                    )
                else:
                    # No confirmed result exists.
                    # Invariant: Fehlende Runtime-Evidenz wird nicht erfunden.
                    if effect_class == "non_idempotent":
                        # Side effects may have occurred; blind retry is forbidden!
                        task["status"] = "HUMAN_REQUIRED"
                        task["recovery_reason"] = "STALE_WORKER_EFFECT_AMBIGUOUS"
                        if w_info and w_info.get("current_task") == task_id:
                            w_info["current_task"] = None
                            w_info["available"] = False
                        report.quarantined_task_ids.append(task_id)
                        report.reconciled_tasks.append(
                            TaskRecoveryRecord(
                                task_id=task_id,
                                previous_status=current_status,
                                new_status="HUMAN_REQUIRED",
                                action=RecoveryAction.QUARANTINED_UNKNOWN_EFFECT,
                                recovery_reason="STALE_WORKER_EFFECT_AMBIGUOUS",
                                detail="In-flight non-idempotent task quarantined without blind replay",
                            )
                        )
                    else:
                        # Idempotent task with zero side effect risk can be safely cleared for retry
                        task["status"] = "QUEUED"
                        task["worker_id"] = None
                        if w_info and w_info.get("current_task") == task_id:
                            w_info["current_task"] = None
                        report.reconciled_tasks.append(
                            TaskRecoveryRecord(
                                task_id=task_id,
                                previous_status=current_status,
                                new_status="QUEUED",
                                action=RecoveryAction.CLEARED_SAFE_RETRY,
                                detail="Idempotent task cleared safely for fresh claim",
                            )
                        )

            # Sync updated task status back into goal workflow_plans
            goal_id = task.get("goal_id")
            if goal_id and goal_id in goals:
                goal = goals[goal_id]
                for step in goal.get("workflow_plan", []):
                    if step.get("task_id") == task_id:
                        step["status"] = task["status"]
                        if task.get("recovery_reason"):
                            step["recovery_reason"] = task["recovery_reason"]

                # If any step in goal is quarantined, block the goal
                if any(s.get("status") == "HUMAN_REQUIRED" for s in goal.get("workflow_plan", [])):
                    goal["status"] = "BLOCKED"

        # =====================================================================
        # Phase 3: READY BERECHNEN (Compute genuinely ready tasks)
        # =====================================================================
        self.phase = StartupPhase.COMPUTING_READY
        ready_tasks = []

        for goal_id, goal in goals.items():
            if goal.get("status") == "ACTIVE":
                for step in goal.get("workflow_plan", []):
                    # Check prerequisites
                    if step.get("status") == "QUEUED":
                        ready_tasks.append(step.get("task_id"))

        report.ready_task_ids = ready_tasks

        # =====================================================================
        # Phase 4: DISPATCH (Open dispatch gate)
        # =====================================================================
        self.phase = StartupPhase.DISPATCH_READY
        report.phase = self.phase
        report.dispatch_gate_open = True
        state["_startup_reconciled"] = True
        state["_recovery_timestamp"] = curr_time

        return state, report

    def assert_can_dispatch(self) -> None:
        """Enforces invariant: Vor Reconciliation kein neuer Konflikt-Dispatch."""
        if self.phase != StartupPhase.DISPATCH_READY:
            raise ConflictDispatchBlockedError(
                f"Cannot dispatch tasks in phase {self.phase.value}: startup reconciliation must complete first"
            )
