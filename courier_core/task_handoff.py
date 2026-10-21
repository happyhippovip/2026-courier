"""Task Handoff, Attempt Lineage, and Effect Reconciliation Engine (CP-20 / CQ-20 / GB-HANDOFF-01)

Durable Worker Contract:
1. Fehlversuch bleibt Historie:
   - Each attempt is an immutable record in AttemptLineage.
   - Logical task maintains identity (task_id, project_id, goal_id).
2. Kein Cross-Project-Kontextleck:
   - Strict workspace and project/tenant isolation; candidate substitute workers
     must be authorized for the specific project_id, preventing context leaks.
3. Inkompatibler Ersatz wird abgewiesen:
   - Substitute workers must satisfy required capabilities, effect class, and platform.
   - Incompatible workers fail closed with IncompatibleSubstituteWorkerError.
4. Unbekannter Effekt wird vor Retry geklärt:
   - Tasks whose previous attempt resulted in UNKNOWN_EFFECT / AMBIGUOUS are quarantined.
   - Blind re-dispatch is strictly BLOCKED until explicit effect reconciliation.
5. Required Evidence:
   - task-contract, attempt-lineage, effect-state.
"""

from __future__ import annotations

import datetime
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class AttemptStatus(str, Enum):
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    QUARANTINED = "QUARANTINED"


class EffectState(str, Enum):
    NO_EFFECT = "NO_EFFECT"
    EFFECT_COMMITTED = "EFFECT_COMMITTED"
    EFFECT_REVERTED = "EFFECT_REVERTED"
    UNKNOWN_EFFECT = "UNKNOWN_EFFECT"


class EffectReconciliationDecision(str, Enum):
    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"


class CrossProjectContextLeakError(RuntimeError):
    """Raised when a task handoff violates tenant/project isolation boundaries."""


class IncompatibleSubstituteWorkerError(RuntimeError):
    """Raised when a candidate replacement worker fails required capability or effect contract."""


class UnresolvedEffectError(RuntimeError):
    """Raised when an attempt is made to re-dispatch a task with an unresolved unknown effect."""


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    project_id: str
    goal_id: str
    required_capabilities: Set[str]
    effect_class: str  # "idempotent", "non_idempotent", "read_only"
    allowed_platforms: Optional[Set[str]] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "goal_id": self.goal_id,
            "required_capabilities": sorted(list(self.required_capabilities)),
            "effect_class": self.effect_class,
            "allowed_platforms": sorted(list(self.allowed_platforms)) if self.allowed_platforms else None,
            "params": self.params,
        }


@dataclass(frozen=True)
class WorkerProfile:
    worker_id: str
    authorized_projects: Set[str]  # e.g. {"proj-alpha"} or {"*"}
    supported_capabilities: Set[str]
    supported_effect_classes: Set[str]
    platform: str  # "windows", "macos", "linux"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "authorized_projects": sorted(list(self.authorized_projects)),
            "supported_capabilities": sorted(list(self.supported_capabilities)),
            "supported_effect_classes": sorted(list(self.supported_effect_classes)),
            "platform": self.platform,
        }


@dataclass(frozen=True)
class AttemptRecord:
    attempt_number: int
    attempt_id: str
    worker_id: str
    started_at: float
    finished_at: Optional[float]
    status: AttemptStatus
    effect_state: EffectState
    failure_reason: Optional[str] = None
    evidence_receipt: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_number": self.attempt_number,
            "attempt_id": self.attempt_id,
            "worker_id": self.worker_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status.value,
            "effect_state": self.effect_state.value,
            "failure_reason": self.failure_reason,
            "evidence_receipt": self.evidence_receipt,
        }


@dataclass
class TaskHandoffRecord:
    contract: TaskContract
    attempt_lineage: List[AttemptRecord] = field(default_factory=list)
    current_effect_state: EffectState = EffectState.NO_EFFECT
    is_completed: bool = False
    quarantined: bool = False
    reconciliation_history: List[Dict[str, Any]] = field(default_factory=list)


class TaskHandoffCoordinator:
    """Manages task handoff across workers while guaranteeing lineage and effect safety."""

    def __init__(self) -> None:
        self.tasks: Dict[str, TaskHandoffRecord] = {}

    def register_task(
        self,
        task_id: str,
        project_id: str,
        goal_id: str,
        required_capabilities: Set[str],
        effect_class: str,
        allowed_platforms: Optional[Set[str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> TaskHandoffRecord:
        contract = TaskContract(
            task_id=task_id,
            project_id=project_id,
            goal_id=goal_id,
            required_capabilities=set(required_capabilities),
            effect_class=effect_class,
            allowed_platforms=set(allowed_platforms) if allowed_platforms else None,
            params=params or {},
        )
        record = TaskHandoffRecord(contract=contract)
        self.tasks[task_id] = record
        return record

    def get_task(self, task_id: str) -> TaskHandoffRecord:
        if task_id not in self.tasks:
            raise KeyError(f"Task not found: {task_id}")
        return self.tasks[task_id]

    def record_attempt_terminal(
        self,
        task_id: str,
        attempt_number: int,
        status: AttemptStatus,
        effect_state: EffectState,
        failure_reason: Optional[str] = None,
        finished_at: Optional[float] = None,
        evidence_receipt: Optional[Dict[str, Any]] = None,
    ) -> AttemptRecord:
        """Records terminal status for an attempt. History is strictly preserved (immutable append)."""
        task = self.get_task(task_id)
        fin_time = time.time() if finished_at is None else finished_at

        # Locate existing attempt in lineage
        target_idx = None
        for idx, att in enumerate(task.attempt_lineage):
            if att.attempt_number == attempt_number:
                target_idx = idx
                break

        if target_idx is None:
            raise ValueError(f"Attempt number {attempt_number} not found for task {task_id}")

        old_attempt = task.attempt_lineage[target_idx]
        updated_attempt = AttemptRecord(
            attempt_number=old_attempt.attempt_number,
            attempt_id=old_attempt.attempt_id,
            worker_id=old_attempt.worker_id,
            started_at=old_attempt.started_at,
            finished_at=fin_time,
            status=status,
            effect_state=effect_state,
            failure_reason=failure_reason,
            evidence_receipt=evidence_receipt,
        )

        task.attempt_lineage[target_idx] = updated_attempt
        task.current_effect_state = effect_state

        if status == AttemptStatus.COMPLETED:
            task.is_completed = True
            task.quarantined = False
        elif effect_state == EffectState.UNKNOWN_EFFECT:
            task.quarantined = True
        else:
            task.quarantined = False

        return updated_attempt

    def reconcile_unresolved_effect(
        self,
        task_id: str,
        decision: EffectReconciliationDecision,
        evidence_digest: str,
        reconciled_by: str,
    ) -> None:
        """Explicitly reconciles a quarantined task with an unknown effect."""
        task = self.get_task(task_id)

        audit_entry = {
            "timestamp": time.time(),
            "decision": decision.value,
            "evidence_digest": evidence_digest,
            "reconciled_by": reconciled_by,
        }
        task.reconciliation_history.append(audit_entry)

        if decision == EffectReconciliationDecision.PROVEN_NOT_EXECUTED:
            # Effect was proven not to have executed: clear quarantine and set effect state back to NO_EFFECT
            task.current_effect_state = EffectState.NO_EFFECT
            task.quarantined = False
        elif decision == EffectReconciliationDecision.CONFIRMED_EXECUTED:
            # Effect was confirmed executed: task is complete, no redundant attempt allowed
            task.current_effect_state = EffectState.EFFECT_COMMITTED
            task.is_completed = True
            task.quarantined = False

    def handoff_to_substitute_worker(
        self,
        task_id: str,
        substitute_worker: WorkerProfile,
        now: Optional[float] = None,
    ) -> AttemptRecord:
        """Safely hands off task to a replacement worker with complete lineage and contract checks."""
        task = self.get_task(task_id)
        contract = task.contract
        current_time = time.time() if now is None else now

        if task.is_completed:
            raise RuntimeError(f"Task {task_id} is already completed; handoff denied.")

        # 1. Unknown Effect Quarantine Check
        if task.quarantined or task.current_effect_state == EffectState.UNKNOWN_EFFECT:
            raise UnresolvedEffectError(
                f"Handoff blocked: Task {task_id} has an unresolved UNKNOWN_EFFECT from previous attempt. "
                "Must be reconciled before a new attempt can be scheduled."
            )

        # 2. Cross-Project Context Isolation Check
        if "*" not in substitute_worker.authorized_projects:
            if contract.project_id not in substitute_worker.authorized_projects:
                raise CrossProjectContextLeakError(
                    f"Cross-project boundary violation: Worker '{substitute_worker.worker_id}' "
                    f"authorized only for {substitute_worker.authorized_projects}, but task '{task_id}' "
                    f"belongs to project '{contract.project_id}'."
                )

        # 3. Capability Contract Check
        missing_capabilities = contract.required_capabilities - substitute_worker.supported_capabilities
        if missing_capabilities:
            raise IncompatibleSubstituteWorkerError(
                f"Substitute worker '{substitute_worker.worker_id}' lacks required capabilities: {sorted(list(missing_capabilities))}"
            )

        # 4. Effect Class Compatibility Check
        if contract.effect_class not in substitute_worker.supported_effect_classes:
            raise IncompatibleSubstituteWorkerError(
                f"Substitute worker '{substitute_worker.worker_id}' does not support effect class '{contract.effect_class}' "
                f"(supports: {sorted(list(substitute_worker.supported_effect_classes))})"
            )

        # 5. Platform Compatibility Check
        if contract.allowed_platforms:
            if substitute_worker.platform not in contract.allowed_platforms:
                raise IncompatibleSubstituteWorkerError(
                    f"Substitute worker platform '{substitute_worker.platform}' not in allowed platforms {sorted(list(contract.allowed_platforms))}"
                )

        # 6. Create Next Immutable Attempt
        next_attempt_number = len(task.attempt_lineage) + 1
        attempt_id = f"{task_id}-att-{next_attempt_number}"

        new_attempt = AttemptRecord(
            attempt_number=next_attempt_number,
            attempt_id=attempt_id,
            worker_id=substitute_worker.worker_id,
            started_at=current_time,
            finished_at=None,
            status=AttemptStatus.RUNNING,
            effect_state=EffectState.NO_EFFECT,
        )

        task.attempt_lineage.append(new_attempt)
        return new_attempt

    def generate_handoff_evidence(self, task_id: str) -> Dict[str, Any]:
        """Generates CP-20 required evidence: ['task-contract', 'attempt-lineage', 'effect-state']."""
        task = self.get_task(task_id)

        return {
            "required_evidence": ["task-contract", "attempt-lineage", "effect-state"],
            "task-contract": task.contract.to_dict(),
            "attempt-lineage": [att.to_dict() for att in task.attempt_lineage],
            "effect-state": {
                "current_effect_state": task.current_effect_state.value,
                "is_completed": task.is_completed,
                "quarantined": task.quarantined,
                "total_attempts": len(task.attempt_lineage),
                "reconciliation_history": task.reconciliation_history,
            },
        }
