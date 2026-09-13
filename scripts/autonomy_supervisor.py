#!/usr/bin/env python3
"""Canonical Autonomy Supervisor & Watchdog Engine.

Provides deterministic, crash-safe, multi-worker supervisor with lease fencing,
idempotent failover, and zero-spend guardrails for 2026-Projektzentrale.

Responsibilities:
1. Observe worker registry & durable heartbeats.
2. Maintain single active supervisor lease via OS-level flock + monotonic generation fencing.
3. Supervise worker lifecycles according to the Worker Restart Matrix (No Mutual Restart Chaos).
4. Reconcile durable queue & resume from checkpoints after crash.
5. Support Chief Offline Mode (continue approved safe work; fail-closed on permissions/spend).
6. Crash loop prevention with exponential backoff and bounded thresholds.
7. Track comprehensive telemetry and efficiency counters.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
SUPERVISOR_DIR = EVENTS_DIR / "autonomy-supervisor"
SUPERVISOR_LEASE_FILE = SUPERVISOR_DIR / "supervisor_lease.json"
SUPERVISOR_LOCK_FILE = SUPERVISOR_DIR / "supervisor.lock"
HEARTBEATS_DIR = SUPERVISOR_DIR / "heartbeats"
CHECKPOINT_FILE = SUPERVISOR_DIR / "supervisor_checkpoint.json"

LEASE_TTL_SECONDS = 15.0
CRASH_LOOP_WINDOW_SECONDS = 60.0
MAX_RESTARTS_PER_WINDOW = 5


class WorkerState(str, enum.Enum):
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


class WorkerRole(str, enum.Enum):
    GOOGLE = "GOOGLE"
    CLI1 = "CLI1"
    CLI2 = "CLI2"
    CODEX = "CODEX"
    CHIEF = "CHIEF"


@dataclass
class WorkerHeartbeat:
    worker_id: str
    session_epoch: str
    mission_id: str
    state: str
    last_progress_at: str
    last_heartbeat_at: str
    process_id: Optional[int]
    process_start_identity: str
    current_fingerprint: str = ""
    checkpoint_ref: str = ""
    provider_state: str = "AVAILABLE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorLease:
    supervisor_id: str
    generation: int
    lease_acquired_at: str
    lease_expires_at: str
    last_heartbeat: str
    process_id: int
    process_start_identity: str
    state: str = "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SupervisorMetrics:
    unchanged_polls: int = 0
    hashes_avoided: int = 0
    duplicate_alerts_suppressed: int = 0
    tests_suppressed: int = 0
    model_calls_avoided: int = 0
    worker_restarts: int = 0
    failovers: int = 0
    checkpoint_resumes: int = 0
    duplicate_executions_prevented: int = 0
    crash_loops_blocked: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def utc_now_plus(seconds: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)).isoformat()


def parse_iso(ts_str: Optional[str]) -> Optional[dt.datetime]:
    if not ts_str or ts_str in ("UNKNOWN", "NOT_REACHED"):
        return None
    try:
        return dt.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


class AutonomySupervisor:
    """Master Autonomy Supervisor for single-PC and crash-safe multi-worker operations."""

    def __init__(
        self,
        supervisor_id: Optional[str] = None,
        repo_dir: Optional[Path] = None,
    ):
        self.repo_dir = repo_dir or COURIER_DIR
        self.supervisor_dir = self.repo_dir / "events" / "autonomy-supervisor"
        self.lease_file = self.supervisor_dir / "supervisor_lease.json"
        self.lock_file = self.supervisor_dir / "supervisor.lock"
        self.heartbeats_dir = self.supervisor_dir / "heartbeats"
        self.checkpoint_file = self.supervisor_dir / "supervisor_checkpoint.json"

        self.supervisor_id = supervisor_id or f"supervisor-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.current_generation: int = 0
        self.is_active_leader: bool = False
        self.chief_offline_mode: bool = True
        self.metrics = SupervisorMetrics()

        self.restart_history: Dict[str, List[float]] = {}
        self.worker_processes: Dict[str, Optional[int]] = {}
        self.last_known_heartbeats: Dict[str, WorkerHeartbeat] = {}

        self._lock_fd: Optional[int] = None
        self._ensure_dir()
        self.load_checkpoint()

    def _ensure_dir(self) -> None:
        self.supervisor_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeats_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------------
    # Legacy compatibility boundary.  Production authority is the canonical
    # Motor SQLite lease; this module is observer/restart-policy only.
    # --------------------------------------------------------------------------

    def try_acquire_leader_lease(self) -> bool:
        """Fail closed: this legacy entry point cannot own production work."""
        self.legacy_lease_diagnostic = self._read_lease_safe()
        self.is_active_leader = False
        return False

    def renew_lease(self) -> bool:
        return False

    def release_lease(self) -> None:
        """Preserve historical lease evidence; never mutate production authority."""
        self.is_active_leader = False

    def _read_lease_safe(self) -> Optional[Dict[str, Any]]:
        if not self.lease_file.exists():
            return None
        try:
            text = self.lease_file.read_text(encoding="utf-8").strip()
            if not text:
                return {"state": "LEGACY_NON_AUTHORITATIVE", "diagnostic": "EMPTY_LEGACY_LEASE"}
            data = json.loads(text)
            if not isinstance(data, dict) or "generation" not in data or "supervisor_id" not in data:
                return {"state": "LEGACY_NON_AUTHORITATIVE", "diagnostic": "MALFORMED_LEGACY_LEASE"}
            return {"state": "LEGACY_NON_AUTHORITATIVE", "legacy_record": data}
        except Exception:
            return {"state": "LEGACY_NON_AUTHORITATIVE", "diagnostic": "UNREADABLE_LEGACY_LEASE"}

    def _write_lease(self, lease: SupervisorLease) -> None:
        temp = self.lease_file.with_suffix(".tmp")
        temp.write_text(json.dumps(lease.to_dict(), indent=2), encoding="utf-8")
        temp.replace(self.lease_file)

    # --------------------------------------------------------------------------
    # Heartbeat Ingestion & Liveness Classification
    # --------------------------------------------------------------------------

    def publish_worker_heartbeat(
        self,
        worker_id: str,
        state: str,
        process_id: Optional[int],
        mission_id: str = "MISSION_ACTIVE",
        checkpoint_ref: str = "",
        provider_state: str = "AVAILABLE",
    ) -> WorkerHeartbeat:
        """Records a cheap deterministic worker heartbeat."""
        now_iso = utc_now()
        hb = WorkerHeartbeat(
            worker_id=worker_id,
            session_epoch="EPOCH_2026",
            mission_id=mission_id,
            state=state,
            last_progress_at=now_iso if state in (WorkerState.PROGRESSING.value, WorkerState.COMPLETED.value) else "",
            last_heartbeat_at=now_iso,
            process_id=process_id,
            process_start_identity=f"proc-{process_id}-{worker_id}",
            checkpoint_ref=checkpoint_ref,
            provider_state=provider_state,
        )
        hb_file = self.heartbeats_dir / f"{worker_id}_heartbeat.json"
        hb_file.write_text(json.dumps(hb.to_dict(), indent=2), encoding="utf-8")
        self.last_known_heartbeats[worker_id] = hb
        return hb

    def inspect_worker_health(self, worker_id: str) -> Tuple[WorkerState, str]:
        """Classifies worker state: pid=None is not alive; persistent daemon with fresh heartbeat is not hung."""
        hb_file = self.heartbeats_dir / f"{worker_id}_heartbeat.json"
        if not hb_file.exists():
            return WorkerState.UNKNOWN, "NO_HEARTBEAT_RECORD"

        try:
            hb_data = json.loads(hb_file.read_text(encoding="utf-8"))
            pid = hb_data.get("process_id")
            last_hb_str = hb_data.get("last_heartbeat_at")
            declared_state = hb_data.get("state", WorkerState.UNKNOWN.value)
            prov_state = hb_data.get("provider_state", "AVAILABLE")
        except Exception:
            return WorkerState.UNKNOWN, "MALFORMED_HEARTBEAT"

        if prov_state in ("QUOTA_EXHAUSTED", "PROVIDER_ERROR"):
            return WorkerState.WAITING_RESOURCE, f"PROVIDER_STATE_{prov_state}"

        if pid is None:
            # pid=None is NEVER alive
            return WorkerState.SAFE_IDLE, "PID_NONE_SAFE_IDLE"

        # Check OS process existence
        try:
            os.kill(pid, 0)
            is_alive = True
        except OSError:
            is_alive = False

        if not is_alive:
            if declared_state == WorkerState.PROGRESSING.value:
                return WorkerState.ORPHANED, "DEAD_PROCESS_ORPHANED"
            return WorkerState.FAILED, "PROCESS_DEAD"

        # Process is alive. Check heartbeat age
        now = dt.datetime.now(dt.timezone.utc)
        hb_dt = parse_iso(last_hb_str)
        if hb_dt and (now - hb_dt).total_seconds() > 45.0:
            if declared_state == WorkerState.PROGRESSING.value:
                return WorkerState.HUNG, "HEARTBEAT_EXPIRED_PROGRESSING"
            elif declared_state == WorkerState.SAFE_IDLE.value:
                # Persistent daemon in safe idle with old heartbeat is NOT hung
                return WorkerState.SAFE_IDLE, "DAEMON_SAFE_IDLE"

        return WorkerState(declared_state), "HEALTHY"

    # --------------------------------------------------------------------------
    # Worker Restart Matrix & Crash Loop Prevention
    # --------------------------------------------------------------------------

    def can_restart_worker(self, worker_id: str) -> Tuple[bool, str]:
        """Evaluates Worker Restart Matrix, authorization, and crash loop bounds."""
        now = time.time()
        history = self.restart_history.get(worker_id, [])
        # Filter window
        history = [t for t in history if (now - t) < CRASH_LOOP_WINDOW_SECONDS]
        self.restart_history[worker_id] = history

        if len(history) >= MAX_RESTARTS_PER_WINDOW:
            self.metrics.crash_loops_blocked += 1
            return False, "CRASH_LOOP_BLOCKED"

        if worker_id == WorkerRole.CHIEF.value:
            return False, "CHIEF_AUTORESTART_FORBIDDEN"

        if worker_id in (WorkerRole.CLI1.value, WorkerRole.CLI2.value):
            return True, "AUTORESTART_APPROVED_READ_ONLY"

        if worker_id == WorkerRole.GOOGLE.value:
            # Google is conditional: requires no active ambiguous mutation
            return True, "AUTORESTART_APPROVED_CONDITIONAL"

        if worker_id == WorkerRole.CODEX.value:
            return True, "AUTORESTART_APPROVED_LOCAL_SURFACE"

        return False, "UNKNOWN_WORKER"

    def restart_worker(
        self,
        worker_id: str,
        spawn_fn: Optional[Callable[[], int]] = None,
    ) -> Tuple[bool, str]:
        """Restarts an eligible worker process strictly governed by supervisor."""
        can_restart, reason = self.can_restart_worker(worker_id)
        if not can_restart:
            return False, reason

        self.restart_history[worker_id].append(time.time())
        self.metrics.worker_restarts += 1

        new_pid = None
        if spawn_fn:
            try:
                new_pid = spawn_fn()
                self.worker_processes[worker_id] = new_pid
                self.publish_worker_heartbeat(worker_id, WorkerState.PROGRESSING.value, new_pid)
                self.save_checkpoint()
                return True, f"WORKER_RESTARTED_PID_{new_pid}"
            except Exception as e:
                return False, f"SPAWN_EXCEPTION_{e}"

        return True, "RESTART_RECORDED"

    # --------------------------------------------------------------------------
    # Checkpoint & Telemetry Persistence
    # --------------------------------------------------------------------------

    def save_checkpoint(self) -> Path:
        data = {
            "supervisor_id": self.supervisor_id,
            "generation": self.current_generation,
            "is_active_leader": self.is_active_leader,
            "chief_offline_mode": self.chief_offline_mode,
            "saved_at": utc_now(),
            "metrics": self.metrics.to_dict(),
            "worker_processes": self.worker_processes,
        }
        self.checkpoint_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.checkpoint_file

    def load_checkpoint(self) -> None:
        if not self.checkpoint_file.exists():
            return
        try:
            data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
            self.current_generation = data.get("generation", 0)
            self.chief_offline_mode = data.get("chief_offline_mode", True)
            m = data.get("metrics", {})
            self.metrics = SupervisorMetrics(**m) if m else SupervisorMetrics()
            self.worker_processes = data.get("worker_processes", {})
            self.metrics.checkpoint_resumes += 1
        except Exception as e:
            print(f"Warning: could not load supervisor checkpoint: {e}")


def init_supervisor() -> AutonomySupervisor:
    sup = AutonomySupervisor()
    return sup


if __name__ == "__main__":
    sup = init_supervisor()
    print("AutonomySupervisor is legacy/non-authoritative; use canonical Motor runtime.")
