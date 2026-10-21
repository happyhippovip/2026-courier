"""Durable Lease Fencing, Epoch Guard, and Unknown-Effect Reconciliation Boundary.

Enforces CP-09 / CQ-09 Invariants:
1. Fencing/Epoch and Result Acceptance decoupled from process abort:
   Even if an old worker process survives cancellation or continues running,
   it cannot authorize external effects or commit results with a stale lease/epoch.
2. Alter Lease-Inhaber kann keinen neuen Effekt autorisieren:
   Monotonically increasing lease generations (fencing tokens) reject stale writes.
3. Unknown-effect-Reconciliation statt blindem Retry:
   When a lease expires or failover occurs while a non-idempotent task is in-flight,
   the task transitions to NEEDS_RECONCILIATION and is strictly BLOCKED until
   explicit resolution (CONFIRMED_EXECUTED vs. PROVEN_NOT_EXECUTED).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import time
from typing import Any, Optional


class EffectClass(str, Enum):
    IDEMPOTENT = "idempotent"
    NON_IDEMPOTENT = "non_idempotent"
    READ_ONLY = "read_only"


class ExecutionPhase(str, Enum):
    CLAIMED = "CLAIMED"
    STARTED = "STARTED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


class EffectResolution(str, Enum):
    CONFIRMED_EXECUTED = "CONFIRMED_EXECUTED"
    PROVEN_NOT_EXECUTED = "PROVEN_NOT_EXECUTED"
    AMBIGUOUS = "AMBIGUOUS"


class FencingBoundaryError(Exception):
    """Base exception for effect fencing and boundary violations."""


class StaleFencingTokenError(FencingBoundaryError):
    """Raised when an operation presents a stale fencing token/lease generation."""


class LeaseExpiredError(FencingBoundaryError):
    """Raised when an operation is attempted with an expired lease."""


class EffectAuthorizationDenied(FencingBoundaryError):
    """Raised when effect authorization is denied by the fencing boundary."""


class UnknownEffectQuarantinedError(FencingBoundaryError):
    """Raised when attempting to execute or re-dispatch a task quarantined for unknown effect."""


@dataclass
class LeaseFencingRecord:
    task_id: str
    holder: str
    generation: int
    acquired_at: float
    expires_at: float
    effect_class: str = EffectClass.NON_IDEMPOTENT.value
    phase: str = ExecutionPhase.CLAIMED.value
    status: str = "DISPATCHED"
    physical_effects_count: int = 0
    reconciliation_resolution: Optional[str] = None
    reconciliation_note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LeaseFencingRecord:
        return cls(
            task_id=str(data["task_id"]),
            holder=str(data["holder"]),
            generation=int(data["generation"]),
            acquired_at=float(data["acquired_at"]),
            expires_at=float(data["expires_at"]),
            effect_class=str(data.get("effect_class", EffectClass.NON_IDEMPOTENT.value)),
            phase=str(data.get("phase", ExecutionPhase.CLAIMED.value)),
            status=str(data.get("status", "DISPATCHED")),
            physical_effects_count=int(data.get("physical_effects_count", 0)),
            reconciliation_resolution=data.get("reconciliation_resolution"),
            reconciliation_note=data.get("reconciliation_note"),
        )


class EffectFencingBoundary:
    """Coordinates lease fencing, effect authorization gates, and unknown effect reconciliation."""

    def __init__(self, state_path: Optional[str | Path] = None) -> None:
        self.state_path = Path(state_path) if state_path else None
        self._leases: dict[str, LeaseFencingRecord] = {}
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._load()

    def _load(self) -> None:
        if self.state_path and self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._leases = {
                    k: LeaseFencingRecord.from_dict(v)
                    for k, v in data.get("leases", {}).items()
                }
            except Exception:
                self._leases = {}

    def _save(self) -> None:
        if not self.state_path:
            return
        payload = {
            "leases": {k: v.to_dict() for k, v in self._leases.items()},
            "updated_at": time.time(),
        }
        tmp = self.state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(self.state_path)

    def acquire_lease(
        self,
        task_id: str,
        holder: str,
        ttl_seconds: float = 30.0,
        effect_class: str = EffectClass.NON_IDEMPOTENT.value,
        now: Optional[float] = None,
    ) -> LeaseFencingRecord:
        """Acquire a new lease generation / fencing token for a task."""
        curr_time = now if now is not None else time.time()
        existing = self._leases.get(task_id)

        # Check if task is quarantined awaiting unknown effect reconciliation
        if existing and existing.status == "NEEDS_RECONCILIATION":
            raise UnknownEffectQuarantinedError(
                f"Task {task_id} is quarantined for unknown external effect; cannot acquire lease without reconciliation"
            )

        # Check if held by another active worker
        if existing and existing.expires_at > curr_time and existing.holder != holder:
            raise EffectAuthorizationDenied(
                f"Task {task_id} is currently leased to {existing.holder} until {existing.expires_at}"
            )

        next_generation = (existing.generation + 1) if existing else 1
        record = LeaseFencingRecord(
            task_id=task_id,
            holder=holder,
            generation=next_generation,
            acquired_at=curr_time,
            expires_at=curr_time + ttl_seconds,
            effect_class=effect_class,
            phase=ExecutionPhase.CLAIMED.value,
            status="DISPATCHED",
            physical_effects_count=existing.physical_effects_count if existing else 0,
        )
        self._leases[task_id] = record
        self._save()
        return record

    def authorize_effect(
        self,
        task_id: str,
        holder: str,
        generation: int,
        effect_payload: dict[str, Any],
        now: Optional[float] = None,
    ) -> dict[str, Any]:
        """Authorize a physical external effect prior to execution.
        
        Strictly decoupled from process termination: even if a zombie worker process
        was never killed or is still running, this boundary rejects the operation if
        the token is stale or the lease expired.
        """
        curr_time = now if now is not None else time.time()
        record = self._leases.get(task_id)

        if not record:
            raise EffectAuthorizationDenied(f"No lease found for task {task_id}")

        if record.status == "NEEDS_RECONCILIATION":
            raise UnknownEffectQuarantinedError(
                f"Task {task_id} is blocked in NEEDS_RECONCILIATION; effect authorization forbidden"
            )

        if record.status in ("RECONCILED", "COMPLETED"):
            raise EffectAuthorizationDenied(
                f"Task {task_id} is already in terminal state {record.status}; second effect prohibited"
            )

        # Stale fencing token / epoch check
        if generation != record.generation:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: current lease epoch is {record.generation}"
            )

        # Holder mismatch
        if record.holder != holder:
            raise EffectAuthorizationDenied(
                f"Holder mismatch: lease held by {record.holder}, presented by {holder}"
            )

        # Lease expiration check
        if record.expires_at <= curr_time:
            raise LeaseExpiredError(
                f"Lease expired at {record.expires_at} (current time: {curr_time}); effect authorization denied"
            )

        # Transition phase to STARTED and increment physical effect counter
        record.phase = ExecutionPhase.STARTED.value
        record.physical_effects_count += 1
        self._save()

        return {
            "authorized": True,
            "task_id": task_id,
            "holder": holder,
            "generation": generation,
            "authorized_at": curr_time,
            "physical_effect_sequence": record.physical_effects_count,
        }

    def commit_result(
        self,
        task_id: str,
        holder: str,
        generation: int,
        result_payload: dict[str, Any],
        now: Optional[float] = None,
    ) -> dict[str, Any]:
        """Commit result of an executed task, validating fencing token and lease."""
        curr_time = now if now is not None else time.time()
        record = self._leases.get(task_id)

        if not record:
            raise EffectAuthorizationDenied(f"No lease found for task {task_id}")

        if record.status == "NEEDS_RECONCILIATION":
            raise UnknownEffectQuarantinedError(
                f"Task {task_id} is in NEEDS_RECONCILIATION; cannot commit result from expired attempt"
            )

        if generation != record.generation:
            raise StaleFencingTokenError(
                f"Stale fencing token {generation} rejected: current lease epoch is {record.generation}"
            )

        if record.holder != holder:
            raise EffectAuthorizationDenied(
                f"Holder mismatch: lease held by {record.holder}, presented by {holder}"
            )

        record.phase = ExecutionPhase.COMMITTED.value
        record.status = "COMPLETED"
        self._save()

        return {
            "status": "ACK_COMMITTED",
            "task_id": task_id,
            "generation": generation,
        }

    def handle_lease_expiry_or_failover(
        self,
        task_id: str,
        now: Optional[float] = None,
    ) -> dict[str, Any]:
        """Evaluate lease expiry or worker failover.
        
        Enforces unknown-effect-reconciliation instead of blind retry:
        If the task had reached STARTED phase and is NON_IDEMPOTENT, it MUST NOT
        be blindly retried. It transitions to NEEDS_RECONCILIATION and is BLOCKED.
        """
        record = self._leases.get(task_id)
        if not record:
            return {"task_id": task_id, "action": "NO_OP"}

        curr_time = now if now is not None else time.time()
        # Expire lease
        record.expires_at = 0.0

        if record.phase == ExecutionPhase.STARTED.value and record.effect_class == EffectClass.NON_IDEMPOTENT.value:
            # Side effect may have executed externally. Blind retry forbidden!
            record.status = "NEEDS_RECONCILIATION"
            self._save()
            return {
                "task_id": task_id,
                "status": "NEEDS_RECONCILIATION",
                "recovery_reason": "STALE_WORKER_EFFECT_AMBIGUOUS",
                "reexecution_allowed": False,
                "action": "QUARANTINE_BLOCKED",
            }

        if record.phase == ExecutionPhase.CLAIMED.value or record.effect_class == EffectClass.IDEMPOTENT.value:
            # Safe to retry because no non-idempotent side effect was started
            record.status = "QUEUED"
            record.phase = ExecutionPhase.CLAIMED.value
            self._save()
            return {
                "task_id": task_id,
                "status": "QUEUED",
                "reexecution_allowed": True,
                "action": "SAFE_RETRY",
            }

        return {"task_id": task_id, "status": record.status, "reexecution_allowed": False}

    def reconcile_unknown_effect(
        self,
        task_id: str,
        resolution: EffectResolution | str,
        operator_id: str = "operator",
        note: str = "",
    ) -> dict[str, Any]:
        """Operator or automated audit reconciles an ambiguous/quarantined task."""
        record = self._leases.get(task_id)
        if not record:
            raise EffectAuthorizationDenied(f"Task {task_id} not found")

        if record.status != "NEEDS_RECONCILIATION":
            raise EffectAuthorizationDenied(
                f"Task {task_id} is in status {record.status}, not NEEDS_RECONCILIATION"
            )

        res_val = resolution.value if isinstance(resolution, EffectResolution) else str(resolution)

        if res_val == EffectResolution.CONFIRMED_EXECUTED.value:
            # External effect already happened. Reconcile as completed without second execution.
            record.status = "RECONCILED"
            record.phase = ExecutionPhase.COMMITTED.value
            record.reconciliation_resolution = res_val
            record.reconciliation_note = f"Reconciled by {operator_id}: {note}"
            self._save()
            return {
                "task_id": task_id,
                "status": "RECONCILED",
                "resolution": res_val,
                "reexecution_allowed": False,
            }

        elif res_val == EffectResolution.PROVEN_NOT_EXECUTED.value:
            # Proven that no external effect occurred. Safe for controlled re-execution with fresh lease generation.
            record.status = "QUEUED"
            record.phase = ExecutionPhase.CLAIMED.value
            record.reconciliation_resolution = res_val
            record.reconciliation_note = f"Reconciled by {operator_id}: {note}"
            self._save()
            return {
                "task_id": task_id,
                "status": "QUEUED",
                "resolution": res_val,
                "reexecution_allowed": True,
            }

        else:
            # Ambiguous resolution remains quarantined
            return {
                "task_id": task_id,
                "status": "NEEDS_RECONCILIATION",
                "resolution": EffectResolution.AMBIGUOUS.value,
                "reexecution_allowed": False,
            }

    def verify_no_duplicate_effect(self, task_id: str) -> bool:
        """Invariant: proves that at most 1 physical effect was authorized."""
        record = self._leases.get(task_id)
        if not record:
            return True
        return record.physical_effects_count <= 1

    def inspect(self, task_id: str) -> Optional[dict[str, Any]]:
        record = self._leases.get(task_id)
        return record.to_dict() if record else None
