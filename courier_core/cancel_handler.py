"""
courier_core/cancel_handler.py — Cancel-Requested, Confirmed Stop, Stale Result & Effect Boundary (CP-13 / CQ-13)

Invariants:
1. Cancel is neither proof of success nor an immediate safe stop.
2. An in-flight process or external effect may continue running after a cancel request.
3. Cancellation confirmation requires the worker to actively confirm the process tree was reaped.
4. If a worker vanishes after a cancel request without confirmation:
   - Idempotent tasks may be safely cleared/cancelled.
   - Non-idempotent tasks transition to BLOCKED/NEEDS_RECONCILIATION (unknown external effect).
   - Automatic retry is strictly prohibited (reexecution_allowed = False).
5. Late results for cancel-requested or cancelled tasks are recorded as immutable Effect Receipts
   without history rewriting (they never overwrite cancellation with unverified success).
6. Cancelling a BLOCKED task is a human gate requiring an explicit actor.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class CancellationStatus(str, Enum):
    NONE = "NONE"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CONFIRMED_STOPPED = "CONFIRMED_STOPPED"
    CANCELLED = "CANCELLED"
    BLOCKED_UNKNOWN_EFFECT = "BLOCKED_UNKNOWN_EFFECT"


@dataclass
class EffectReceipt:
    """Immutable evidence of an external execution effect or late result."""
    task_id: str
    attempt_id: Union[str, int]
    dispatch_id: str
    worker_id: str
    result_id: Optional[str] = None
    artifacts: List[Any] = field(default_factory=list)
    outcome: Optional[str] = None
    reason: Optional[str] = None
    recorded_at: float = field(default_factory=time.time)
    receipt_digest: str = ""

    def __post_init__(self):
        if not self.receipt_digest:
            artifacts_repr = json.dumps(self.artifacts, sort_keys=True, default=str)
            payload_str = f"{self.task_id}:{self.attempt_id}:{self.dispatch_id}:{self.worker_id}:{self.result_id}:{self.outcome}:{artifacts_repr}"
            self.receipt_digest = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AttemptCancellationRecord:
    """Audit record capturing the attempt lifecycle under cancellation."""
    task_id: str
    attempt_id: Union[str, int]
    dispatch_id: str
    worker_id: str
    actor: Optional[str] = None
    reason: Optional[str] = None
    requested_at: float = field(default_factory=time.time)
    confirmed_at: Optional[float] = None
    status: CancellationStatus = CancellationStatus.CANCEL_REQUESTED
    effect_receipts: List[EffectReceipt] = field(default_factory=list)
    reexecution_allowed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["effect_receipts"] = [r.to_dict() if isinstance(r, EffectReceipt) else r for r in self.effect_receipts]
        return d


class CancelHandlerError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CancelHandler:
    """Enforces cancellation boundaries, attempt state tracking, and effect receipt collection."""

    TERMINAL_STATUSES = frozenset({"COMPLETE", "RESULT_RECEIVED", "RECONCILED", "FAILED_TERMINAL", "CANCELLED"})

    @classmethod
    def request_cancellation(
        cls,
        task: Dict[str, Any],
        actor: Optional[str] = None,
        reason: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Request cancellation of a task.
        - Fails closed on terminal tasks.
        - Requires an actor for BLOCKED tasks.
        - Immediately marks QUEUED tasks as CANCELLED (not running yet).
        - Transitions in-flight tasks (DISPATCHED, STARTED, RUNNING) to CANCEL_REQUESTED.
        """
        now = now if now is not None else time.time()
        status = task.get("status", "QUEUED")

        if status in cls.TERMINAL_STATUSES:
            raise CancelHandlerError(
                code="terminal_task",
                message=f"Cannot cancel task {task.get('task_id')} in terminal status {status}",
                status_code=409,
            )

        if status in ("BLOCKED", "NEEDS_RECONCILIATION"):
            if not actor:
                raise CancelHandlerError(
                    code="actor_required",
                    message="cancelling a blocked task is a human decision; name the actor",
                    status_code=409,
                )
            task["status"] = "CANCELLED"
            task["resolution"] = "cancelled_effect_unknown"
            task["decided_by"] = actor
            task["reexecution_allowed"] = False
            task["cancel_confirmed_at"] = now
            task["cancel_requested"] = False
            return task

        if status == "QUEUED":
            task["status"] = "CANCELLED"
            task["resolution"] = "cancelled_before_dispatch"
            task["decided_by"] = actor or "system"
            task["cancel_reason"] = reason or "cancelled_before_dispatch"
            task["cancel_confirmed_at"] = now
            task["cancel_requested"] = False
            task["reexecution_allowed"] = False
            return task

        # In-flight task: DISPATCHED, STARTED, RUNNING
        if task.get("cancel_requested"):
            raise CancelHandlerError(
                code="already_requested",
                message=f"Cancellation already requested for task {task.get('task_id')}",
                status_code=409,
            )

        task["cancel_requested"] = True
        task["cancel_actor"] = actor or "system"
        task["cancel_reason"] = reason or "cancellation_requested"
        task["cancel_requested_at"] = now

        raw_attempt = task.get("attempt_id") or task.get("attempts") or 1
        record = AttemptCancellationRecord(
            task_id=task.get("task_id", ""),
            attempt_id=raw_attempt,
            dispatch_id=task.get("dispatch_id", ""),
            worker_id=task.get("worker_id", ""),
            actor=actor,
            reason=reason,
            requested_at=now,
            status=CancellationStatus.CANCEL_REQUESTED,
            reexecution_allowed=False,
        )
        task.setdefault("cancellation_history", []).append(record.to_dict())
        return task

    @classmethod
    def confirm_stop(
        cls,
        task: Dict[str, Any],
        worker_id: str,
        dispatch_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Worker confirmed the process tree has been cleanly reaped and halted.
        Transitions the task from CANCEL_REQUESTED to CANCELLED.
        """
        now = now if now is not None else time.time()
        if not task.get("cancel_requested"):
            raise CancelHandlerError(
                code="cancellation_not_requested",
                message=f"Cancellation was not requested for task {task.get('task_id')}",
                status_code=409,
            )

        expected_worker = task.get("worker_id")
        if expected_worker and expected_worker != worker_id:
            raise CancelHandlerError(
                code="worker_mismatch",
                message=f"Worker {worker_id} cannot confirm stop for task held by {expected_worker}",
                status_code=409,
            )

        expected_dispatch = task.get("dispatch_id")
        if dispatch_id and expected_dispatch and dispatch_id != expected_dispatch:
            raise CancelHandlerError(
                code="dispatch_mismatch",
                message=f"Dispatch {dispatch_id} mismatch with active dispatch {expected_dispatch}",
                status_code=409,
            )

        task["status"] = "CANCELLED"
        task["resolution"] = "worker confirmed stop"
        task["cancel_confirmed_at"] = now
        task["cancel_requested"] = False
        task["reexecution_allowed"] = False

        if "cancellation_history" in task and task["cancellation_history"]:
            latest = task["cancellation_history"][-1]
            latest["confirmed_at"] = now
            latest["status"] = CancellationStatus.CONFIRMED_STOPPED.value

        return task

    @classmethod
    def handle_vanished_worker(
        cls,
        task: Dict[str, Any],
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        A worker holding a cancel-requested task disappeared/died before confirming stop.
        - Idempotent: safe to clear and cancel cleanly.
        - Non-idempotent: uncertain whether side-effects executed; transition to BLOCKED.
          Automatic retry is strictly prohibited.
        """
        now = now if now is not None else time.time()
        if not task.get("cancel_requested"):
            return task

        is_idempotent = bool(task.get("idempotent") or task.get("effect_class") == "idempotent")

        if is_idempotent:
            task["status"] = "CANCELLED"
            task["resolution"] = "idempotent_cleared"
            task["cancel_confirmed_at"] = now
            task["cancel_requested"] = False
            task["reexecution_allowed"] = False
            if "cancellation_history" in task and task["cancellation_history"]:
                latest = task["cancellation_history"][-1]
                latest["confirmed_at"] = now
                latest["status"] = CancellationStatus.CONFIRMED_STOPPED.value
        else:
            task["status"] = "BLOCKED"
            task["recovery_reason"] = "cancelled_worker_vanished_effect_ambiguous"
            task["reexecution_allowed"] = False
            task["cancel_requested"] = True  # Still reflects cancel was requested
            if "cancellation_history" in task and task["cancellation_history"]:
                latest = task["cancellation_history"][-1]
                latest["status"] = CancellationStatus.BLOCKED_UNKNOWN_EFFECT.value

        return task

    @classmethod
    def record_late_result(
        cls,
        task: Dict[str, Any],
        result_data: Dict[str, Any],
        now: Optional[float] = None,
    ) -> EffectReceipt:
        """
        A worker submits a result for a task that is either CANCEL_REQUESTED or CANCELLED.
        - Invariant: No history rewriting. The result is NOT accepted as task success.
        - Invariant: Effect receipt is immutably appended to preserve physical evidence.
        """
        now = now if now is not None else time.time()

        raw_attempt = result_data.get("attempt_id") or task.get("attempt_id") or task.get("attempts") or 1
        receipt = EffectReceipt(
            task_id=task.get("task_id", result_data.get("task_id", "")),
            attempt_id=raw_attempt,
            dispatch_id=result_data.get("dispatch_id", task.get("dispatch_id", "")),
            worker_id=result_data.get("worker_id", task.get("worker_id", "")),
            result_id=result_data.get("result_id"),
            artifacts=result_data.get("artifacts", []),
            outcome=result_data.get("outcome") or result_data.get("status"),
            reason=result_data.get("reason", "late_result_under_cancel"),
            recorded_at=now,
        )

        task.setdefault("effect_receipts", []).append(receipt.to_dict())

        # Also link into latest cancellation history entry if present
        if "cancellation_history" in task and task["cancellation_history"]:
            task["cancellation_history"][-1].setdefault("effect_receipts", []).append(receipt.to_dict())

        return receipt
