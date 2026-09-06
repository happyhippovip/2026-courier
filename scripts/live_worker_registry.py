#!/usr/bin/env python3
"""Mission 200: Live Worker Registry, Snitch & Operations Controller.

Provides real-time, multi-worker operational truth across GOOGLE, CODEX, CLI1, and CLI2:
- 16-State deterministic classification engine
- Temporary resource availability and 30-day window lifecycle
- Real meaningful progress detection (no fake PID/persisted-RUNNING liveness)
- Network degradation and provider error recovery with task preservation
- Deduplicated event and alert emission to events/runtime-alerts/ and events/worker-events/
- Continuous next-safe-work signaling without human WEITER
- Compact aggregate machine-readable status view for Visual HQ
- 100% deterministic local execution (0 model calls, 0 EUR spend)
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from opportunity_queue import Opportunity, OpportunityQueue
    from queue_hygiene_manager import QueueHygieneManager
except ImportError:
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.queue_hygiene_manager import QueueHygieneManager


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_iso(ts: Optional[str]) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        parsed = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def safe_load_json(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def is_pid_alive(pid: Optional[int]) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class WorkerState(str, enum.Enum):
    STARTING = "STARTING"
    PROGRESSING = "PROGRESSING"
    SAFE_IDLE = "SAFE_IDLE"
    AVAILABLE = "AVAILABLE"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_RESOURCE = "WAITING_RESOURCE"
    NETWORK_DEGRADED = "NETWORK_DEGRADED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    RUNNING_NO_PROGRESS = "RUNNING_NO_PROGRESS"
    HUNG = "HUNG"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ORPHANED = "ORPHANED"
    UNKNOWN = "UNKNOWN"


class AvailabilityClass(str, enum.Enum):
    TEMPORARY_30_DAY = "TEMPORARY_30_DAY"
    PERSISTENT_HOST = "PERSISTENT_HOST"
    PRIMARY_BUILDER = "PRIMARY_BUILDER"
    DETERMINISTIC_LOCAL = "DETERMINISTIC_LOCAL"
    EXPIRED = "EXPIRED"
    AVAILABILITY_UNKNOWN = "AVAILABILITY_UNKNOWN"


class EventType(str, enum.Enum):
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_PROGRESS = "WORKER_PROGRESS"
    WORKER_COMPLETED = "WORKER_COMPLETED"
    WORKER_AVAILABLE = "WORKER_AVAILABLE"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    WAITING_HUMAN = "WAITING_HUMAN"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    NETWORK_DEGRADED = "NETWORK_DEGRADED"
    RECOVERED = "RECOVERED"
    RUNNING_NO_PROGRESS = "RUNNING_NO_PROGRESS"
    FAILED = "FAILED"
    ORPHANED = "ORPHANED"
    UNKNOWN_ANOMALY = "UNKNOWN_ANOMALY"
    NEXT_SAFE_WORK_AVAILABLE = "NEXT_SAFE_WORK_AVAILABLE"


@dataclass
class WorkerRecord:
    worker_id: str
    role: str
    provider: str
    availability_class: str
    available_until: Optional[str]
    mission_id: Optional[str] = None
    task_id: Optional[str] = None
    task_fingerprint: Optional[str] = None
    process_identity: Optional[str] = None
    process_start_identity: Optional[str] = None
    session_epoch: str = field(default_factory=lambda: f"epoch-{int(time.time())}")
    state: str = WorkerState.STARTING.value
    state_since: str = field(default_factory=utc_now)
    last_heartbeat: Optional[str] = field(default_factory=utc_now)
    last_meaningful_progress: Optional[str] = field(default_factory=utc_now)
    blocked_reason: Optional[str] = None
    mutable_scope: List[str] = field(default_factory=list)
    heavy_job: bool = False
    last_result_id: Optional[str] = None
    state_confidence: float = 1.0
    pid: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_expired(self) -> bool:
        """Determines if a temporary resource access window has expired."""
        if not self.available_until:
            return False
        expiry_dt = parse_iso(self.available_until)
        if not expiry_dt:
            return True
        return dt.datetime.now(dt.timezone.utc) > expiry_dt


@dataclass
class StructuredRuntimeEvent:
    event_id: str = field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    event_type: str = EventType.WORKER_PROGRESS.value
    worker_id: str = "CLI1"
    task_id: Optional[str] = None
    mission_id: Optional[str] = None
    fingerprint: str = ""
    session_epoch: str = ""
    created_at: str = field(default_factory=utc_now)
    severity: str = "INFO"  # INFO, WARNING, HIGH, CRITICAL
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommended_action: Optional[str] = None
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LiveWorkerRegistry:
    """Authoritative live operations registry and Snitch controller for Computer A."""

    DEFAULT_30_DAY_SECONDS = 30 * 86400

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.registry_dir = self.repo_dir / "events" / "worker-registry"
        self.alerts_dir = self.repo_dir / "events" / "runtime-alerts"
        self.events_dir = self.repo_dir / "events" / "worker-events"
        self.state_dir = self.repo_dir / "events" / "runtime-state"

        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.registry_file = self.registry_dir / "active_workers.json"
        self.aggregate_status_file = self.state_dir / "aggregate_worker_status.json"
        self.queue_manager = QueueHygieneManager(repo_dir=self.repo_dir)

        self._alert_dedup_cache: Dict[str, str] = {}
        self.telemetry = {
            "checks_count": 0,
            "events_emitted": 0,
            "duplicate_events_suppressed": 0,
            "model_calls": 0,
        }

    # --------------------------------------------------------------------------
    # Registration & Resource Lifecycle Management
    # --------------------------------------------------------------------------

    def register_worker(
        self,
        worker_id: str,
        role: str,
        provider: str,
        availability_class: AvailabilityClass = AvailabilityClass.TEMPORARY_30_DAY,
        available_duration_seconds: Optional[float] = None,
        process_identity: Optional[str] = None,
        pid: Optional[int] = None,
        mission_id: Optional[str] = None,
        mutable_scope: Optional[List[str]] = None,
        heavy_job: bool = False,
    ) -> WorkerRecord:
        """Registers or refreshes a live worker record in the registry."""
        now = dt.datetime.now(dt.timezone.utc)

        # Calculate availability window
        if availability_class == AvailabilityClass.TEMPORARY_30_DAY:
            duration = available_duration_seconds or self.DEFAULT_30_DAY_SECONDS
            available_until = (now + dt.timedelta(seconds=duration)).isoformat()
        else:
            available_until = None

        proc_start_id = f"pid-{pid}-{int(time.time())}" if pid else None

        record = WorkerRecord(
            worker_id=worker_id,
            role=role,
            provider=provider,
            availability_class=availability_class.value,
            available_until=available_until,
            mission_id=mission_id,
            process_identity=process_identity,
            process_start_identity=proc_start_id,
            session_epoch=f"epoch-{worker_id.lower()}-{int(time.time())}",
            state=WorkerState.STARTING.value,
            state_since=now.isoformat(),
            last_heartbeat=now.isoformat(),
            last_meaningful_progress=now.isoformat(),
            mutable_scope=mutable_scope or [],
            heavy_job=heavy_job,
            state_confidence=1.0,
            pid=pid,
        )

        self._save_worker_record(record)
        self.emit_event(
            event_type=EventType.WORKER_STARTED,
            worker=record,
            evidence={"initial_registration": True, "availability_class": record.availability_class},
        )
        return record

    def get_worker(self, worker_id: str) -> Optional[WorkerRecord]:
        workers = self.list_workers()
        return workers.get(worker_id)

    def list_workers(self) -> Dict[str, WorkerRecord]:
        data = safe_load_json(self.registry_file)
        if not isinstance(data, dict):
            return {}
        result: Dict[str, WorkerRecord] = {}
        for wid, wdict in data.items():
            if isinstance(wdict, dict):
                try:
                    result[wid] = WorkerRecord(**wdict)
                except Exception:
                    result[wid] = WorkerRecord(
                        worker_id=wid,
                        role=str(wdict.get("role", "Specialist")),
                        provider=str(wdict.get("provider", "UNKNOWN")),
                        availability_class=str(wdict.get("availability_class", "PAY_AS_YOU_GO")),
                        available_until=wdict.get("available_until"),
                        state=WorkerState.UNKNOWN.value,
                        blocked_reason="CORRUPT_REGISTRY_RECORD",
                    )
            else:
                result[wid] = WorkerRecord(
                    worker_id=wid,
                    role="Specialist",
                    provider="UNKNOWN",
                    availability_class="PAY_AS_YOU_GO",
                    available_until=None,
                    state=WorkerState.UNKNOWN.value,
                    blocked_reason="CORRUPT_REGISTRY_RECORD",
                )
        return result

    def _save_worker_record(self, record: WorkerRecord) -> None:
        workers = self.list_workers()
        workers[record.worker_id] = record
        payload = {wid: w.to_dict() for wid, w in workers.items()}
        safe_write_json(self.registry_file, payload)

    # --------------------------------------------------------------------------
    # Progress, State Transitions & Anomaly Classification
    # --------------------------------------------------------------------------

    def record_progress(
        self,
        worker_id: str,
        evidence: Dict[str, Any],
        task_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        result_id: Optional[str] = None,
    ) -> Optional[WorkerRecord]:
        """Records verified meaningful progress (output change, test result, step completion)."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None

        now_iso = utc_now()
        was_degraded = worker.state in (WorkerState.PROVIDER_ERROR.value, WorkerState.NETWORK_DEGRADED.value, WorkerState.HUNG.value)

        worker.last_meaningful_progress = now_iso
        worker.last_heartbeat = now_iso
        worker.state = WorkerState.PROGRESSING.value
        worker.state_since = now_iso
        if task_id:
            worker.task_id = task_id
            worker.task_fingerprint = hashlib.sha256(f"{task_id}|{now_iso}".encode()).hexdigest()[:16]
        if mission_id:
            worker.mission_id = mission_id
        if result_id:
            worker.last_result_id = result_id
        worker.blocked_reason = None

        self._save_worker_record(worker)

        # Emit progress event or recovery event
        if was_degraded:
            self.emit_event(
                event_type=EventType.RECOVERED,
                worker=worker,
                evidence=evidence,
                severity="INFO",
            )
        else:
            self.emit_event(
                event_type=EventType.WORKER_PROGRESS,
                worker=worker,
                evidence=evidence,
                severity="INFO",
            )
        return worker

    def record_worker_completed(
        self,
        worker_id: str,
        result_id: str,
        completion_evidence: Dict[str, Any],
    ) -> Optional[WorkerRecord]:
        """Transitions worker to COMPLETED and immediately triggers availability evaluation."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None

        now_iso = utc_now()
        worker.state = WorkerState.COMPLETED.value
        worker.state_since = now_iso
        worker.last_result_id = result_id
        worker.last_meaningful_progress = now_iso
        self._save_worker_record(worker)

        self.emit_event(
            event_type=EventType.WORKER_COMPLETED,
            worker=worker,
            evidence=completion_evidence,
            severity="INFO",
        )

        # Transition immediately to AVAILABLE unless expired
        if worker.is_expired():
            worker.state = WorkerState.UNKNOWN.value
            worker.availability_class = AvailabilityClass.EXPIRED.value
            worker.blocked_reason = "30_DAY_RESOURCE_WINDOW_EXPIRED"
        else:
            worker.state = WorkerState.AVAILABLE.value
            worker.state_since = now_iso
            worker.task_id = None
            worker.task_fingerprint = None
            worker.blocked_reason = None

        self._save_worker_record(worker)

        self.emit_event(
            event_type=EventType.WORKER_AVAILABLE,
            worker=worker,
            evidence={"available_for_next_work": True},
            severity="INFO",
        )

        # Evaluate continuous flow next work
        self.evaluate_and_signal_next_safe_work(worker)
        return worker

    def record_provider_failure(
        self,
        worker_id: str,
        failure_reason: str,
        is_network: bool = False,
    ) -> Optional[WorkerRecord]:
        """Records provider error or network drop while strictly preserving task checkpoint."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None

        now_iso = utc_now()
        event_type = EventType.NETWORK_DEGRADED if is_network else EventType.PROVIDER_ERROR
        worker.state = WorkerState.NETWORK_DEGRADED.value if is_network else WorkerState.PROVIDER_ERROR.value
        worker.state_since = now_iso
        worker.blocked_reason = failure_reason
        self._save_worker_record(worker)

        self.emit_event(
            event_type=event_type,
            worker=worker,
            evidence={"failure_reason": failure_reason, "task_preserved": worker.task_id},
            severity="HIGH",
        )
        return worker

    def record_permission_blocked(
        self,
        worker_id: str,
        prompt_text: str,
        requested_command: Optional[str] = None,
    ) -> Optional[WorkerRecord]:
        """Records interactive tool permission wait."""
        worker = self.get_worker(worker_id)
        if not worker:
            return None

        now_iso = utc_now()
        worker.state = WorkerState.WAITING_PERMISSION.value
        worker.state_since = now_iso
        worker.blocked_reason = f"TOOL_PERMISSION_PROMPT: {prompt_text[:100]}"
        self._save_worker_record(worker)

        self.emit_event(
            event_type=EventType.WAITING_PERMISSION,
            worker=worker,
            evidence={"prompt_text": prompt_text, "requested_command": requested_command},
            recommended_action="REWRITE_SAFE_COMMAND_OR_APPROVE",
            severity="HIGH",
        )
        return worker

    # --------------------------------------------------------------------------
    # Observation & Liveness Audit
    # --------------------------------------------------------------------------

    def audit_worker_liveness(
        self,
        worker: WorkerRecord,
        pid: Optional[int],
        last_activity_ts: Optional[float] = None,
        stall_threshold_seconds: float = 180.0,
    ) -> WorkerRecord:
        """Evaluates live worker state against true progress, PID liveness, and expiry."""
        self.telemetry["checks_count"] += 1
        now = dt.datetime.now(dt.timezone.utc)
        now_ts = now.timestamp()

        # 1. Check temporary resource expiration
        if worker.is_expired():
            worker.availability_class = AvailabilityClass.EXPIRED.value
            worker.state = WorkerState.UNKNOWN.value
            worker.blocked_reason = "30_DAY_RESOURCE_WINDOW_EXPIRED"
            self._save_worker_record(worker)
            return worker

        # 2. Check process liveness & missing PID
        # Authoritative rule: Missing or invalid PID is NEVER assumed alive.
        if pid is None or not isinstance(pid, int) or pid <= 0:
            if worker.state in (WorkerState.PROGRESSING.value, WorkerState.STARTING.value):
                worker.state = WorkerState.UNKNOWN.value
                worker.blocked_reason = "MISSING_OR_INVALID_PID"
                self._save_worker_record(worker)
                self.emit_event(
                    event_type=EventType.UNKNOWN_ANOMALY,
                    worker=worker,
                    evidence={"pid": pid, "reason": "MISSING_OR_INVALID_PID_WITH_ACTIVE_STATE"},
                    severity="WARNING",
                )
                return worker
            alive = False
        else:
            alive = is_pid_alive(pid)
            if not alive and worker.state in (WorkerState.PROGRESSING.value, WorkerState.STARTING.value):
                worker.state = WorkerState.ORPHANED.value
                worker.blocked_reason = "PID_DEAD_WITH_ACTIVE_STATE"
                self._save_worker_record(worker)
                self.emit_event(
                    event_type=EventType.ORPHANED,
                    worker=worker,
                    evidence={"pid": pid, "is_alive": False},
                    severity="CRITICAL",
                )
                return worker

        # 3. Check stall / no-progress
        if last_activity_ts and worker.state == WorkerState.PROGRESSING.value:
            idle_seconds = now_ts - last_activity_ts
            if idle_seconds > stall_threshold_seconds:
                worker.state = WorkerState.RUNNING_NO_PROGRESS.value
                worker.blocked_reason = f"NO_PROGRESS_FOR_{int(idle_seconds)}S"
                self._save_worker_record(worker)
                self.emit_event(
                    event_type=EventType.RUNNING_NO_PROGRESS,
                    worker=worker,
                    evidence={"idle_seconds": round(idle_seconds, 1), "pid": pid},
                    severity="WARNING",
                )
                return worker

        return worker

    # --------------------------------------------------------------------------
    # Event Emission & Alert Deduplication
    # --------------------------------------------------------------------------

    def compute_event_fingerprint(
        self,
        event_type: Any,
        worker: WorkerRecord,
        evidence: Dict[str, Any],
    ) -> str:
        ev_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        raw = f"{worker.session_epoch}|{worker.worker_id}|{worker.task_id or 'NONE'}|{ev_str}|{evidence_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def emit_event(
        self,
        event_type: Any,
        worker: WorkerRecord,
        evidence: Dict[str, Any],
        recommended_action: Optional[str] = None,
        severity: str = "INFO",
    ) -> Optional[Path]:
        """Emits a structured, deduplicated event and alert file."""
        ev_str = event_type.value if hasattr(event_type, "value") else str(event_type)
        fp = self.compute_event_fingerprint(event_type, worker, evidence)

        # Check deduplication cache
        if self._alert_dedup_cache.get(worker.worker_id) == fp:
            self.telemetry["duplicate_events_suppressed"] += 1
            return None

        event = StructuredRuntimeEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            event_type=ev_str,
            worker_id=worker.worker_id,
            task_id=worker.task_id,
            mission_id=worker.mission_id,
            fingerprint=fp,
            session_epoch=worker.session_epoch,
            created_at=utc_now(),
            severity=severity,
            evidence=evidence,
            recommended_action=recommended_action,
            acknowledged=False,
        )

        # Write to worker-events directory
        event_file = self.events_dir / f"{event.event_id}.json"
        safe_write_json(event_file, event.to_dict())

        # If severity is WARNING, HIGH, or CRITICAL, also write to runtime-alerts
        if severity in ("WARNING", "HIGH", "CRITICAL"):
            alert_file = self.alerts_dir / f"alert-{event.event_id}.json"
            safe_write_json(alert_file, event.to_dict())

        self._alert_dedup_cache[worker.worker_id] = fp
        self.telemetry["events_emitted"] += 1
        return event_file

    def compact_event_stream(self, max_events: int = 500) -> int:
        """Archives oldest event files if count exceeds max_events to keep events directory bounded."""
        if not self.events_dir.is_dir():
            return 0
        event_files = sorted(
            [f for f in self.events_dir.iterdir() if f.is_file() and f.name.startswith("evt-") and f.suffix == ".json"],
            key=lambda p: p.stat().st_mtime,
        )
        if len(event_files) <= max_events:
            return 0
        to_archive = event_files[: len(event_files) - max_events]
        archive_dir = self.events_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archived = 0
        for f in to_archive:
            try:
                dest = archive_dir / f.name
                shutil.move(str(f), str(dest))
                archived += 1
            except Exception:
                pass
        return archived

    # --------------------------------------------------------------------------
    # Continuous Flow & Next Safe Work Signaling
    # --------------------------------------------------------------------------

    def evaluate_and_signal_next_safe_work(self, worker: WorkerRecord) -> Optional[Opportunity]:
        """Evaluates active OpportunityQueue and signals NEXT_SAFE_WORK_AVAILABLE if safe candidate exists."""
        if worker.state != WorkerState.AVAILABLE.value or worker.is_expired():
            return None

        q = OpportunityQueue(repo_dir=self.repo_dir)
        all_opps = q.list_opportunities()
        ready_tasks = [o for o in all_opps if o.status == "READY"]

        # Sort by priority descending
        ready_tasks = sorted(ready_tasks, key=lambda x: x.priority, reverse=True)

        for candidate in ready_tasks:
            # 1. Historical deduplication check
            if self.queue_manager.is_task_completed_in_history(candidate.opportunity_id):
                continue

            # 2. Scope conflict check with other active workers
            workers = self.list_workers()
            cand_scopes = set(candidate.allowed_scope or [candidate.project or "GLOBAL"])
            has_conflict = False
            for wid, w in workers.items():
                if wid != worker.worker_id and w.state == WorkerState.PROGRESSING.value:
                    if any(s in set(w.mutable_scope) for s in cand_scopes):
                        has_conflict = True
                        break
            if has_conflict:
                continue

            # 3. Heavy job exclusivity check
            if candidate.heavy_job and any(w.heavy_job for w in workers.values() if w.state == WorkerState.PROGRESSING.value):
                continue

            # 4. Exclude High Risk tasks from autonomous auto-start
            if candidate.risk == "HIGH":
                continue

            # Eligible safe task found! Signal NEXT_SAFE_WORK_AVAILABLE
            self.emit_event(
                event_type=EventType.NEXT_SAFE_WORK_AVAILABLE,
                worker=worker,
                evidence={
                    "eligible_task_id": candidate.opportunity_id,
                    "priority": candidate.priority,
                    "description": candidate.description,
                    "project": candidate.project,
                },
                recommended_action=f"ASSIGN_TASK_{candidate.opportunity_id}",
                severity="INFO",
            )
            return candidate

        # If no task, ensure worker reflects SAFE_IDLE
        worker.state = WorkerState.SAFE_IDLE.value
        self._save_worker_record(worker)
        return None

    # --------------------------------------------------------------------------
    # Aggregate Status View Generator
    # --------------------------------------------------------------------------

    def generate_aggregate_status(self) -> Dict[str, Any]:
        """Generates compact machine-readable summary view for Visual HQ."""
        workers = self.list_workers()
        status_map: Dict[str, Any] = {}
        free_workers: List[str] = []

        for wid, w in workers.items():
            status_map[wid] = {
                "role": w.role,
                "provider": w.provider,
                "state": w.state,
                "mission_id": w.mission_id or "NONE",
                "task_id": w.task_id or "NONE",
                "availability_class": w.availability_class,
                "is_expired": w.is_expired(),
                "last_meaningful_progress": w.last_meaningful_progress,
                "blocked_reason": w.blocked_reason,
            }
            if w.state in (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value) and not w.is_expired():
                free_workers.append(wid)

        result = {
            "schema_version": "3.0",
            "updated_at": utc_now(),
            "workers": status_map,
            "free_workers": free_workers,
            "active_worker_count": sum(1 for w in workers.values() if w.state == WorkerState.PROGRESSING.value),
            "telemetry": self.telemetry,
        }
        safe_write_json(self.aggregate_status_file, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Live Worker Registry & Snitch Controller (Mission 200)")
    parser.add_argument("--status", action="store_true", help="Print aggregate worker status")
    parser.add_argument("--audit", action="store_true", help="Audit worker liveness and availability")
    args = parser.parse_args()

    registry = LiveWorkerRegistry()
    if args.status or args.audit:
        status = registry.generate_aggregate_status()
        print(json.dumps(status, indent=2))
        return 0

    print("[REGISTRY] Active live worker registry initialized.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
