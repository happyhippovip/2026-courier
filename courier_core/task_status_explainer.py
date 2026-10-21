"""Task Status Explainer & Observable State Projection Engine (CP-44 / GB-STATUS-EXPLAINER-01).

Guarantees:
1. Canonical state projection: SUBMITTED is never projected as executed or running.
2. Missing status or freshness metadata is strictly classified as UNKNOWN.
3. Full preservation of raw technical details, stack traces, and exit codes.
4. Duration-alone alarms are forbidden: elapsed time never triggers false alarms without an explicit error.
5. Evidence generation containing 'state-projection', 'freshness', and 'error-codes'.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CanonicalTaskState(str, Enum):
    SUBMITTED = "SUBMITTED"    # Staged / in intake queue (NOT executed)
    WAITING = "WAITING"        # Waiting for dependencies or admission
    RUNNING = "RUNNING"        # Actively executing
    BLOCKED = "BLOCKED"        # Blocked on external human gate / resource
    COMPLETED = "COMPLETED"    # Successfully executed with verified result
    FAILED = "FAILED"          # Terminated with verified error code / failure
    UNKNOWN = "UNKNOWN"        # Missing or unverified state data


@dataclass(frozen=True)
class TaskStatusProjection:
    task_id: str
    canonical_state: CanonicalTaskState
    compact_status_line: str
    detail_explanation: str
    freshness_timestamp_iso: Optional[str]
    freshness_age_seconds: Optional[float]
    reason: Optional[str]
    error_code: Optional[str]
    is_alarm_triggered: bool
    raw_technical_details: Dict[str, Any]


class TaskStatusExplainer:
    """Projects raw task telemetry into truthful canonical status representations."""

    def __init__(self) -> None:
        self._projections: List[TaskStatusProjection] = []

    def project_task_status(
        self,
        raw_event: Dict[str, Any],
        now_iso: Optional[str] = None,
    ) -> TaskStatusProjection:
        """Transforms a raw task event into a strictly bounded canonical projection.

        Adheres strictly to truth invariants:
        - SUBMITTED is never executed.
        - Missing or corrupt data is UNKNOWN.
        - Long elapsed durations do NOT trigger alarms without explicit failures.
        """
        task_id = raw_event.get("task_id", "").strip()
        if not task_id:
            task_id = "UNKNOWN_TASK"

        raw_state = raw_event.get("state")
        timestamp_iso = raw_event.get("timestamp_iso")
        reason = raw_event.get("reason")
        error_code = raw_event.get("error_code")
        raw_details = raw_event.get("technical_details", {})
        duration_seconds = float(raw_event.get("duration_seconds", 0.0))

        # 1. Missing data handling -> UNKNOWN
        if not raw_state or not timestamp_iso:
            canonical_state = CanonicalTaskState.UNKNOWN
            compact_line = f"[{canonical_state.value}] Status telemetry missing or unverifiable"
            detail = "Status or heartbeat timestamp missing from worker telemetry; classified as UNKNOWN."
            freshness_age = None
            is_alarm = False
        else:
            # Calculate freshness age
            freshness_age = self._calculate_age(timestamp_iso, now_iso)

            # Map raw state to Canonical state
            state_str = str(raw_state).upper().strip()
            if state_str == "SUBMITTED":
                canonical_state = CanonicalTaskState.SUBMITTED
                compact_line = f"[{canonical_state.value}] Queued in intake (unstarted)"
                detail = "Task is registered in the intake queue. Has NOT begun execution."
                is_alarm = False
            elif state_str == "WAITING":
                canonical_state = CanonicalTaskState.WAITING
                compact_line = f"[{canonical_state.value}] {reason or 'Waiting for available worker'}"
                detail = f"Task is waiting for dependency or admission slot: {reason or 'None'}"
                is_alarm = False
            elif state_str == "RUNNING":
                canonical_state = CanonicalTaskState.RUNNING
                compact_line = f"[{canonical_state.value}] Active ({duration_seconds:.0f}s elapsed)"
                detail = f"Worker is actively processing task. Elapsed: {duration_seconds:.1f}s."
                # Duration invariant: long run duration NEVER triggers alarm on its own
                is_alarm = False
            elif state_str == "BLOCKED":
                canonical_state = CanonicalTaskState.BLOCKED
                compact_line = f"[{canonical_state.value}] Gate: {reason or 'External requirement'}"
                detail = f"Execution paused on gate or dependency: {reason or 'Unspecified boundary'}"
                is_alarm = False
            elif state_str == "COMPLETED":
                canonical_state = CanonicalTaskState.COMPLETED
                compact_line = f"[{canonical_state.value}] Finished successfully"
                detail = "Task completed and verified against goal contract."
                is_alarm = False
            elif state_str == "FAILED":
                canonical_state = CanonicalTaskState.FAILED
                err_display = f" [{error_code}]" if error_code else ""
                compact_line = f"[{canonical_state.value}]{err_display} {reason or 'Process failure'}"
                detail = f"Execution terminated with error: {reason or 'Unknown failure'}. ErrorCode: {error_code}."
                # Alarms ONLY trigger when canonical state is genuinely FAILED
                is_alarm = True
            else:
                canonical_state = CanonicalTaskState.UNKNOWN
                compact_line = f"[{canonical_state.value}] Unrecognized raw state '{raw_state}'"
                detail = f"Received non-canonical state string '{raw_state}'; preserved as UNKNOWN."
                is_alarm = False

        projection = TaskStatusProjection(
            task_id=task_id,
            canonical_state=canonical_state,
            compact_status_line=compact_line,
            detail_explanation=detail,
            freshness_timestamp_iso=timestamp_iso,
            freshness_age_seconds=freshness_age,
            reason=reason,
            error_code=error_code,
            is_alarm_triggered=is_alarm,
            raw_technical_details=raw_details,
        )
        self._projections.append(projection)
        return projection

    def _calculate_age(self, timestamp_iso: str, now_iso: Optional[str]) -> Optional[float]:
        try:
            ts = datetime.datetime.fromisoformat(timestamp_iso)
            now = datetime.datetime.fromisoformat(now_iso) if now_iso else datetime.datetime.now(datetime.timezone.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            if now.tzinfo is None:
                now = now.replace(tzinfo=datetime.timezone.utc)
            return max(0.0, (now - ts).total_seconds())
        except Exception:
            return None

    def generate_status_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        return {
            "state-projection": [
                {
                    "task_id": p.task_id,
                    "canonical_state": p.canonical_state.value,
                    "is_alarm": p.is_alarm_triggered,
                }
                for p in self._projections
            ],
            "freshness": [
                {
                    "task_id": p.task_id,
                    "timestamp": p.freshness_timestamp_iso,
                    "age_seconds": p.freshness_age_seconds,
                }
                for p in self._projections
            ],
            "error-codes": [
                {"task_id": p.task_id, "error_code": p.error_code}
                for p in self._projections
                if p.error_code is not None
            ],
        }
