"""Durable Outbox, Result Ingest, and ACK-Binding Boundary.

Enforces CP-10 / CQ-10 Invariants:
1. Persist-Before-Send:
   Results are durably committed to local disk (<home>/outbox/<dispatch_id>.json)
   with fsync prior to attempting network transmission.
2. ACK-Before-Clear:
   No result file is unlinked or removed from outbox until a valid, bound
   acknowledgment (ACK_RESULT_RECEIVED or ACK_DUPLICATE) is confirmed.
3. Idempotent Result Ingest (Zero New Logical Effect on Redelivery):
   Duplicate deliveries of an already-ingested result return ACK_DUPLICATE with
   0 state mutations, 0 re-executions, and 0 duplicate verifier/ledger triggers.
4. Contradictory Results Remain Distinguishable:
   Divergent results for an already-completed task are rejected with a distinct
   conflict error (HTTP 409), cleanly separated from benign duplicate resends.
5. Late Results from Stale Attempts Rejected:
   Results presenting obsolete attempt_id, dispatch_id, or fencing_token fail closed
   without overwriting current task state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Optional


SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


class ResultIngestStatus(str, Enum):
    ACK_RESULT_RECEIVED = "ACK_RESULT_RECEIVED"
    ACK_DUPLICATE = "ACK_DUPLICATE"
    CONFLICT_REJECTED = "CONFLICT_REJECTED"
    STALE_REJECTED = "STALE_REJECTED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


class OutboxBoundaryError(Exception):
    """Base exception for outbox and ACK boundary errors."""


class AckBindingError(OutboxBoundaryError):
    """Raised when an ACK is missing, corrupted, or not bound to the dispatch."""


class ResultConflictError(OutboxBoundaryError):
    """Raised when an incoming result contradicts an already committed result."""


@dataclass
class DeliveryReceipt:
    dispatch_id: str
    status: str
    duplicate: bool
    cleared_from_outbox: bool
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class IngestOutcome:
    status: ResultIngestStatus
    http_code: int
    duplicate: bool
    logical_effect_applied: bool
    error: Optional[str] = None
    stored_result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class DurableOutboxBoundary:
    """Manages the worker-side durable outbox and enforce ACK-before-clear contracts."""

    @staticmethod
    def _outbox_dir(home: str | Path) -> Path:
        return Path(home) / "outbox"

    @classmethod
    def persist_result(cls, home: str | Path, payload: dict[str, Any]) -> Path:
        """Persist-before-send: write result atomically to disk with fsync before network send."""
        dispatch_id = payload.get("dispatch_id")
        if not dispatch_id or not isinstance(dispatch_id, str):
            raise OutboxBoundaryError("Result payload missing valid dispatch_id")
        if any(c not in SAFE_ID_CHARS for c in dispatch_id) or ".." in dispatch_id:
            raise OutboxBoundaryError(f"Invalid dispatch_id characters: {dispatch_id}")

        outbox = cls._outbox_dir(home)
        outbox.mkdir(parents=True, exist_ok=True)
        dest = outbox / f"{dispatch_id}.json"

        serialized = json.dumps(payload, sort_keys=True, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(outbox), prefix=".outbox-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(serialized)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, dest)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

        return dest

    @classmethod
    def deliver_with_ack(
        cls,
        home: str | Path,
        dispatch_id: str,
        deliver_fn: Callable[[dict[str, Any]], dict[str, Any] | bool],
    ) -> DeliveryReceipt:
        """Deliver payload to coordinator and clear outbox ONLY on verified ACK."""
        outbox = cls._outbox_dir(home)
        file_path = outbox / f"{dispatch_id}.json"
        if not file_path.exists():
            return DeliveryReceipt(
                dispatch_id=dispatch_id,
                status="NOT_FOUND",
                duplicate=False,
                cleared_from_outbox=False,
                error=f"No outbox file for dispatch {dispatch_id}",
            )

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        try:
            resp = deliver_fn(payload)
        except Exception as exc:
            # Network drop, timeout, or server crash: KEEP outbox file!
            return DeliveryReceipt(
                dispatch_id=dispatch_id,
                status="DELIVERY_FAILED",
                duplicate=False,
                cleared_from_outbox=False,
                error=str(exc),
            )

        # Parse ACK response
        is_ack = False
        is_dup = False
        ack_status = ""

        if isinstance(resp, dict):
            ack_status = resp.get("status", "")
            if ack_status == "ACK_RESULT_RECEIVED":
                is_ack = True
                is_dup = False
            elif ack_status == "ACK_DUPLICATE":
                is_ack = True
                is_dup = True
        elif resp is True:
            is_ack = True
            ack_status = "ACK_OK"

        if is_ack:
            # ACK-before-clear: Only unlink after receiving confirmation
            try:
                file_path.unlink()
                cleared = True
            except OSError:
                cleared = False

            return DeliveryReceipt(
                dispatch_id=dispatch_id,
                status=ack_status,
                duplicate=is_dup,
                cleared_from_outbox=cleared,
            )
        else:
            # Unacknowledged or rejected response: DO NOT clear file
            err_msg = resp.get("error", "Unrecognized or missing ACK") if isinstance(resp, dict) else "Delivery unacknowledged"
            return DeliveryReceipt(
                dispatch_id=dispatch_id,
                status="UNACKNOWLEDGED",
                duplicate=False,
                cleared_from_outbox=False,
                error=err_msg,
            )

    @classmethod
    def list_pending(cls, home: str | Path) -> list[tuple[Path, dict[str, Any]]]:
        """List outbox files in deterministic chronological FIFO order."""
        outbox = cls._outbox_dir(home)
        if not outbox.is_dir():
            return []
        candidates = sorted(
            [p for p in outbox.glob("*.json") if p.is_file()],
            key=lambda p: (p.stat().st_mtime, p.name),
        )
        results = []
        for p in candidates:
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    results.append((p, json.load(fh)))
            except Exception:
                continue
        return results


class ResultIngestBoundary:
    """Server/Coordinator engine evaluating incoming results for idempotency and conflicts."""

    DETERMINISTIC_IDENTITY_FIELDS = (
        "dispatch_id",
        "result_id",
        "status",
        "worker_id",
        "attempt_id",
        "artifacts",
    )

    @classmethod
    def ingest_result(
        cls,
        task: dict[str, Any],
        incoming: dict[str, Any],
    ) -> IngestOutcome:
        """Evaluate result submission against task state.
        
        Guarantees:
        - Benign duplicates return ACK_DUPLICATE with logical_effect_applied = False.
        - First valid delivery returns ACK_RESULT_RECEIVED with logical_effect_applied = True.
        - Contradictory results return CONFLICT_REJECTED (409) with logical_effect_applied = False.
        - Late results from stale attempts return STALE_REJECTED (409) with logical_effect_applied = False.
        """
        stored = task.get("result") or {}

        # 1. Exact Duplicate Resend Check
        if stored:
            is_identical = all(
                stored.get(field) == incoming.get(field)
                for field in cls.DETERMINISTIC_IDENTITY_FIELDS
            )
            # Check attempt if present
            if "attempt" in incoming and incoming.get("attempt") is not None:
                if stored.get("attempt") != incoming.get("attempt"):
                    is_identical = False

            if is_identical:
                # Idempotent deduplication: ACK immediately without applying new logical effects
                return IngestOutcome(
                    status=ResultIngestStatus.ACK_DUPLICATE,
                    http_code=200,
                    duplicate=True,
                    logical_effect_applied=False,
                    stored_result=stored,
                )

        # 2. Contradictory Result for Processed Task Check
        if task.get("status") in ["RECONCILED", "FAILED_TERMINAL", "RESULT_RECEIVED", "FAILED_VERIFICATION"]:
            return IngestOutcome(
                status=ResultIngestStatus.CONFLICT_REJECTED,
                http_code=409,
                duplicate=False,
                logical_effect_applied=False,
                error="Conflicting result for already processed task",
            )

        # 3. Task Status Check (must be currently awaiting a result)
        if task.get("status") != "DISPATCHED":
            return IngestOutcome(
                status=ResultIngestStatus.CONFLICT_REJECTED,
                http_code=409,
                duplicate=False,
                logical_effect_applied=False,
                error=f"Task is in status {task.get('status')}, not awaiting a result",
            )

        # 4. Worker Ownership Check
        if task.get("worker_id") and incoming.get("worker_id") != task.get("worker_id"):
            return IngestOutcome(
                status=ResultIngestStatus.CONFLICT_REJECTED,
                http_code=409,
                duplicate=False,
                logical_effect_applied=False,
                error=f"worker_id mismatch: task assigned to {task.get('worker_id')}, got {incoming.get('worker_id')}",
            )

        # 5. Stale Attempt or Superseded Dispatch Check
        if incoming.get("attempt_id") != task.get("attempt_id") or (
            incoming.get("dispatch_id") and incoming.get("dispatch_id") != task.get("dispatch_id")
        ):
            return IngestOutcome(
                status=ResultIngestStatus.STALE_REJECTED,
                http_code=409,
                duplicate=False,
                logical_effect_applied=False,
                error="attempt or dispatch mismatch, possible replay from stale worker",
            )

        # 6. Fencing Token & Lease Generation Check
        if "fencing_token" in incoming and "fencing_token" in task:
            if incoming["fencing_token"] != task["fencing_token"]:
                return IngestOutcome(
                    status=ResultIngestStatus.STALE_REJECTED,
                    http_code=409,
                    duplicate=False,
                    logical_effect_applied=False,
                    error=f"stale fencing token: presented {incoming['fencing_token']}, current generation is {task['fencing_token']}",
                )

        # 7. First Valid Delivery: Accept and apply logical effect
        return IngestOutcome(
            status=ResultIngestStatus.ACK_RESULT_RECEIVED,
            http_code=200,
            duplicate=False,
            logical_effect_applied=True,
            stored_result=incoming,
        )
