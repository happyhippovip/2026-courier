"""Workload Liveness, Stuck-RUNNING Resolution, and Service/Job Decoupling Engine.

Enforces CP-12 / CQ-12 Invariants:
1. Differentiates:
   - Langsame Arbeit (Healthy Slow Work): Worker is alive, actively heartbeating, progress recent.
   - Tote Worker (Dead Workers): Process missing in owned process tree or heartbeat exceeded dead threshold.
   - Erforderliche Dauerprozesse (Persistent Services/Daemons): Standing background infrastructure.
2. Keine pauschalen Kills:
   Reaping is strictly restricted to the owned job process tree via Job Objects / PGID.
   Persistent background daemons, Hub, and unrelated OS processes are never killed.
3. Kein DONE aus Timeout:
   A timeout, crash, or liveness expiration can NEVER transition a task to DONE or SUCCESS.
   Only verified cryptographic DurableResults can advance a task.
4. Trennung von Service-Status und Job-Status:
   A slow, stuck, or failed job does not degrade or terminate a healthy persistent service.
5. Unbekannter Zustand wird sichtbar reconciled / blockiert:
   Uncertain in-flight non-idempotent work transitions to NEEDS_RECONCILIATION / BLOCKED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import os
import time
from typing import Any, Callable, Optional

from courier_core.process_tree import is_process_alive, kill_process_tree


class WorkloadKind(str, Enum):
    JOB = "JOB"
    PERSISTENT_SERVICE = "PERSISTENT_SERVICE"


class WorkloadLivenessState(str, Enum):
    HEALTHY_ACTIVE = "HEALTHY_ACTIVE"
    HEALTHY_SLOW_WORK = "HEALTHY_SLOW_WORK"
    DEAD_WORKER = "DEAD_WORKER"
    STUCK_JOB_EXPIRED = "STUCK_JOB_EXPIRED"
    SERVICE_HEALTHY = "SERVICE_HEALTHY"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"


class RecommendedAction(str, Enum):
    PRESERVE_AND_WAIT = "PRESERVE_AND_WAIT"
    REAP_JOB_TREE_AND_QUARANTINE = "REAP_JOB_TREE_AND_QUARANTINE"
    REAP_JOB_TREE_AND_RETRY = "REAP_JOB_TREE_AND_RETRY"
    PRESERVE_SERVICE = "PRESERVE_SERVICE"
    RECONCILE_MANUAL = "RECONCILE_MANUAL"


class WorkloadPolicyError(Exception):
    """Base exception for workload classification violations."""


class IllegalDoneFromTimeoutError(WorkloadPolicyError):
    """Raised when a system attempts to mark a timed-out or stuck task as DONE."""


@dataclass
class TaskExecutionPolicy:
    timeout_s: float = 300.0
    progress_grace_s: float = 60.0
    heartbeat_ttl_s: float = 30.0
    effect_class: str = "non_idempotent"
    is_service: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationReport:
    workload_id: str
    kind: WorkloadKind
    state: WorkloadLivenessState
    action: RecommendedAction
    service_status: str
    job_status: Optional[str] = None
    elapsed_total_s: float = 0.0
    elapsed_since_progress_s: float = 0.0
    elapsed_since_heartbeat_s: float = 0.0
    process_alive: bool = False
    reaped_tree: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["state"] = self.state.value
        data["action"] = self.action.value
        return data


class WorkloadClassifier:
    """Classifies in-flight workloads, protects services, and resolves stuck RUNNING tasks."""

    def __init__(
        self,
        alive_checker: Optional[Callable[[int], bool]] = None,
        tree_killer: Optional[Callable[[int, float], None]] = None,
    ) -> None:
        self.alive_checker = alive_checker or is_process_alive
        self.tree_killer = tree_killer or kill_process_tree

    def classify_and_resolve(
        self,
        workload_id: str,
        pid: Optional[int],
        started_at: float,
        last_progress_at: float,
        last_heartbeat_at: float,
        policy: TaskExecutionPolicy,
        current_time: Optional[float] = None,
        execute_reap: bool = False,
    ) -> ClassificationReport:
        """Classify a running workload and determine exact safe resolution."""
        now = current_time if current_time is not None else time.time()
        elapsed_total = max(0.0, round(now - started_at, 3))
        elapsed_progress = max(0.0, round(now - last_progress_at, 3))
        elapsed_heartbeat = max(0.0, round(now - last_heartbeat_at, 3))

        proc_alive = False
        if pid and pid > 0:
            proc_alive = self.alive_checker(pid)

        # ---------------------------------------------------------------------
        # Case 1: Persistent Service / Daemon (Courier Hub, daemon supervisor)
        # ---------------------------------------------------------------------
        if policy.is_service:
            # Persistent services must not be terminated due to task execution delays
            if proc_alive or elapsed_heartbeat <= policy.heartbeat_ttl_s:
                return ClassificationReport(
                    workload_id=workload_id,
                    kind=WorkloadKind.PERSISTENT_SERVICE,
                    state=WorkloadLivenessState.SERVICE_HEALTHY,
                    action=RecommendedAction.PRESERVE_SERVICE,
                    service_status="SERVICE_HEALTHY",
                    job_status=None,
                    elapsed_total_s=elapsed_total,
                    elapsed_since_progress_s=elapsed_progress,
                    elapsed_since_heartbeat_s=elapsed_heartbeat,
                    process_alive=proc_alive,
                    reason="Persistent service is alive and healthy; blanket kills prohibited",
                )
            else:
                return ClassificationReport(
                    workload_id=workload_id,
                    kind=WorkloadKind.PERSISTENT_SERVICE,
                    state=WorkloadLivenessState.DEAD_WORKER,
                    action=RecommendedAction.RECONCILE_MANUAL,
                    service_status="SERVICE_DEAD",
                    job_status=None,
                    elapsed_total_s=elapsed_total,
                    elapsed_since_progress_s=elapsed_progress,
                    elapsed_since_heartbeat_s=elapsed_heartbeat,
                    process_alive=False,
                    reason="Persistent service process died or heartbeat expired",
                )

        # ---------------------------------------------------------------------
        # Case 2: Ephemeral Job Execution Unit
        # ---------------------------------------------------------------------

        # Condition 2a: Dead Worker (Process died or heartbeat gone beyond threshold)
        if (pid and not proc_alive) or (elapsed_heartbeat > policy.heartbeat_ttl_s * 2):
            reaped = False
            if execute_reap and pid and pid > 0:
                self.tree_killer(pid, 5.0)
                reaped = True

            if policy.effect_class == "non_idempotent":
                action = RecommendedAction.REAP_JOB_TREE_AND_QUARANTINE
                job_status = "HUMAN_REQUIRED"
                reason = "Worker process dead or missing heartbeat; non-idempotent task quarantined"
            else:
                action = RecommendedAction.REAP_JOB_TREE_AND_RETRY
                job_status = "QUEUED"
                reason = "Worker process dead; idempotent task cleared safely for retry"

            return ClassificationReport(
                workload_id=workload_id,
                kind=WorkloadKind.JOB,
                state=WorkloadLivenessState.DEAD_WORKER,
                action=action,
                service_status="SERVICE_HEALTHY",  # Service remains healthy even if child worker died
                job_status=job_status,
                elapsed_total_s=elapsed_total,
                elapsed_since_progress_s=elapsed_progress,
                elapsed_since_heartbeat_s=elapsed_heartbeat,
                process_alive=False,
                reaped_tree=reaped,
                reason=reason,
            )

        # Condition 2b: Stuck Job (Process alive, but exceeded policy timeout with stalled progress)
        if elapsed_total > policy.timeout_s and elapsed_progress > policy.progress_grace_s:
            reaped = False
            if execute_reap and pid and pid > 0:
                self.tree_killer(pid, 5.0)
                reaped = True

            # Invariant: Kein DONE aus Timeout!
            if policy.effect_class == "non_idempotent":
                action = RecommendedAction.REAP_JOB_TREE_AND_QUARANTINE
                job_status = "HUMAN_REQUIRED"
                reason = "Job exceeded task policy deadline without progress; scoped tree reaped; quarantined"
            else:
                action = RecommendedAction.REAP_JOB_TREE_AND_RETRY
                job_status = "QUEUED"
                reason = "Job exceeded task policy deadline without progress; scoped tree reaped; queued for retry"

            return ClassificationReport(
                workload_id=workload_id,
                kind=WorkloadKind.JOB,
                state=WorkloadLivenessState.STUCK_JOB_EXPIRED,
                action=action,
                service_status="SERVICE_HEALTHY",  # Service hosting the job is preserved
                job_status=job_status,
                elapsed_total_s=elapsed_total,
                elapsed_since_progress_s=elapsed_progress,
                elapsed_since_heartbeat_s=elapsed_heartbeat,
                process_alive=proc_alive,
                reaped_tree=reaped,
                reason=reason,
            )

        # Condition 2c: Healthy Slow Work (Alive, heartbeat recent, or progress advancing)
        if elapsed_progress <= policy.progress_grace_s or elapsed_heartbeat <= policy.heartbeat_ttl_s:
            state = (
                WorkloadLivenessState.HEALTHY_SLOW_WORK
                if elapsed_total > (policy.timeout_s * 0.5)
                else WorkloadLivenessState.HEALTHY_ACTIVE
            )
            return ClassificationReport(
                workload_id=workload_id,
                kind=WorkloadKind.JOB,
                state=state,
                action=RecommendedAction.PRESERVE_AND_WAIT,
                service_status="SERVICE_HEALTHY",
                job_status="RUNNING",
                elapsed_total_s=elapsed_total,
                elapsed_since_progress_s=elapsed_progress,
                elapsed_since_heartbeat_s=elapsed_heartbeat,
                process_alive=True,
                reaped_tree=False,
                reason="Workload is alive, making progress, and actively heartbeating",
            )

        # Fallback: Ambiguous / Unknown state
        return ClassificationReport(
            workload_id=workload_id,
            kind=WorkloadKind.JOB,
            state=WorkloadLivenessState.UNKNOWN_AMBIGUOUS,
            action=RecommendedAction.RECONCILE_MANUAL,
            service_status="SERVICE_HEALTHY",
            job_status="HUMAN_REQUIRED",
            elapsed_total_s=elapsed_total,
            elapsed_since_progress_s=elapsed_progress,
            elapsed_since_heartbeat_s=elapsed_heartbeat,
            process_alive=proc_alive,
            reason="Ambiguous state: progress stalled but process still visible",
        )

    @staticmethod
    def enforce_no_done_from_timeout(desired_status: str, source_reason: str) -> None:
        """Asserts that a timeout or stuck state can never result in status DONE or SUCCESS."""
        if desired_status.upper() in ("DONE", "SUCCESS", "COMPLETED", "RECONCILED") and "timeout" in source_reason.lower():
            raise IllegalDoneFromTimeoutError(
                f"Invariant violation: Cannot mark task as {desired_status} due to {source_reason}. "
                f"Timeouts must fail, quarantine, or retry; only verified DurableResults allow completion."
            )
