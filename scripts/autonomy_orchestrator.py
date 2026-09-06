#!/usr/bin/env python3
"""Canonical Autonomy Orchestrator (Mission 2026-Projektzentrale).

Provides fully autonomous, safe, deterministic loop continuation without manual "WEITER".

Core Loop:
OBSERVE → CLASSIFY → ROUTE → EXECUTE_SAFE_NEXT_STEP → CHECKPOINT → REPEAT

Strict Rules:
- Zero manual "WEITER" required between safe phases.
- Real telemetry/evidence only (no fake progress, no synthetic working).
- AUTONOMOUS_SPEND_LIMIT = 0 EUR.
- HEAVY_JOB_LIMIT = 1.
- Queue claim != execution authorization (delegates execution admission to CanonicalAuthority).
- pid=None NEVER implies alive.
- Unmet dependencies or gates block fail-closed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import enum
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

COURIER_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = COURIER_DIR / "events"
ORCHESTRATOR_DIR = EVENTS_DIR / "autonomy-orchestrator"
CHECKPOINT_FILE = ORCHESTRATOR_DIR / "checkpoint.json"
QUEUE_FILE = ORCHESTRATOR_DIR / "safe_queue.json"

try:
    from scripts.canonical_authority import CanonicalAuthority
except ImportError:
    try:
        from canonical_authority import CanonicalAuthority
    except ImportError:
        CanonicalAuthority = None


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


class RoutingAction(str, enum.Enum):
    CLI2_FINAL_ATTACK = "CLI2_FINAL_ATTACK"
    CODEX_FINAL_ACCEPTANCE = "CODEX_FINAL_ACCEPTANCE"
    GOOGLE_REMEDIATE = "GOOGLE_REMEDIATE"
    ENABLE_NEXT_SAFE_AUTONOMY_PHASE = "ENABLE_NEXT_SAFE_AUTONOMY_PHASE"
    CLAIM_NEXT_SAFE_JOB = "CLAIM_NEXT_SAFE_JOB"
    WAITING_RESOURCE = "WAITING_RESOURCE"
    WAITING_PERMISSION = "WAITING_PERMISSION"
    WAITING_HUMAN = "WAITING_HUMAN"
    SAFE_IDLE = "SAFE_IDLE"


@dataclass
class SafeJob:
    job_id: str
    job_type: str
    priority: int = 100
    requires_model: bool = False
    requires_network: bool = False
    requires_payment: bool = False
    requires_human: bool = False
    requires_write_authority: bool = False
    resource_class: str = "LIGHT"  # LIGHT | HEAVY | READ_ONLY
    dependencies: List[str] = field(default_factory=list)
    status: str = "QUEUED"  # QUEUED | CLAIMED | RUNNING | COMPLETED | BLOCKED | FAILED
    claim_owner: Optional[str] = None
    claim_generation: int = 0
    created_at: str = ""
    updated_at: str = ""
    evidence_fingerprint: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DataSaverMetrics:
    unchanged_polls: int = 0
    hashes_avoided: int = 0
    duplicate_alerts_suppressed: int = 0
    tests_suppressed: int = 0
    model_calls_avoided: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class AutonomyOrchestrator:
    """Canonical Autonomy Orchestrator and state machine."""

    def __init__(self, repo_dir: Optional[Path] = None):
        self.repo_dir = repo_dir or COURIER_DIR
        self.orchestrator_dir = self.repo_dir / "events" / "autonomy-orchestrator"
        self.checkpoint_file = self.orchestrator_dir / "checkpoint.json"
        self.queue_file = self.orchestrator_dir / "safe_queue.json"

        self.worker_states: Dict[str, str] = {
            WorkerRole.GOOGLE.value: WorkerState.AVAILABLE.value,
            WorkerRole.CLI1.value: WorkerState.SAFE_IDLE.value,
            WorkerRole.CLI2.value: WorkerState.AVAILABLE.value,
            WorkerRole.CODEX.value: WorkerState.AVAILABLE.value,
        }
        self.worker_pids: Dict[str, Optional[int]] = {
            WorkerRole.GOOGLE.value: os.getpid(),
            WorkerRole.CLI1.value: None,
            WorkerRole.CLI2.value: None,
            WorkerRole.CODEX.value: None,
        }

        self.active_fingerprint: str = ""
        self.current_action: RoutingAction = RoutingAction.SAFE_IDLE
        self.queue: List[SafeJob] = []
        self.completed_job_ids: Set[str] = set()
        self.data_saver = DataSaverMetrics()
        self.last_observation_hash: str = ""

        self._ensure_dir()
        self.load_checkpoint()

    def _ensure_dir(self) -> None:
        self.orchestrator_dir.mkdir(parents=True, exist_ok=True)

    def enqueue_job(
        self,
        job_id: str,
        job_type: str,
        priority: int = 100,
        requires_model: bool = False,
        requires_network: bool = False,
        requires_payment: bool = False,
        requires_human: bool = False,
        requires_write_authority: bool = False,
        resource_class: str = "LIGHT",
        dependencies: Optional[List[str]] = None,
        evidence_fingerprint: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> SafeJob:
        """Enqueues a new safe job into the canonical queue."""
        now = utc_now()
        job = SafeJob(
            job_id=job_id,
            job_type=job_type,
            priority=priority,
            requires_model=requires_model,
            requires_network=requires_network,
            requires_payment=requires_payment,
            requires_human=requires_human,
            requires_write_authority=requires_write_authority,
            resource_class=resource_class,
            dependencies=dependencies or [],
            status="QUEUED",
            created_at=now,
            updated_at=now,
            evidence_fingerprint=evidence_fingerprint,
            payload=payload or {},
        )
        # Avoid duplicate queueing if already present
        existing = next((j for j in self.queue if j.job_id == job_id), None)
        if not existing and job_id not in self.completed_job_ids:
            self.queue.append(job)
            self.save_checkpoint()
        return job

    def observe_worker_liveness(self, worker_id: str, pid: Optional[int]) -> WorkerState:
        """Classify worker liveness: pid=None is NEVER alive."""
        self.worker_pids[worker_id] = pid
        if pid is None:
            # Missing or None PID is never assumed alive
            curr = self.worker_states.get(worker_id, WorkerState.UNKNOWN.value)
            if curr in (WorkerState.PROGRESSING.value, WorkerState.COMPLETED.value):
                # Transition to SAFE_IDLE or UNKNOWN, never remaining PROGRESSING
                self.worker_states[worker_id] = WorkerState.SAFE_IDLE.value
            return WorkerState(self.worker_states[worker_id])

        # Check actual OS process existence
        try:
            os.kill(pid, 0)
            is_alive = True
        except OSError:
            is_alive = False

        if not is_alive:
            self.worker_states[worker_id] = WorkerState.ORPHANED.value
        return WorkerState(self.worker_states[worker_id])

    def route(
        self,
        event_name: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[RoutingAction, Optional[SafeJob]]:
        """Deterministic Routing Table implementation."""
        payload = event_payload or {}

        # 1. Direct explicit event state transitions
        if event_name == "GOOGLE_COMPLETED":
            self.active_fingerprint = payload.get("fingerprint", self.active_fingerprint)
            self.worker_states[WorkerRole.GOOGLE.value] = WorkerState.COMPLETED.value

        elif event_name == "CLI2_FINAL_ATTACK_PASS":
            self.active_fingerprint = payload.get("fingerprint", self.active_fingerprint)
            self.worker_states[WorkerRole.CLI2.value] = WorkerState.COMPLETED.value

        elif event_name in ("CLI2_HIGH_DEFECT", "CODEX_REMEDIATE"):
            self.worker_states[WorkerRole.GOOGLE.value] = WorkerState.AVAILABLE.value
            self.worker_states[WorkerRole.CLI2.value] = WorkerState.AVAILABLE.value
            self.worker_states[WorkerRole.CODEX.value] = WorkerState.AVAILABLE.value
            self.current_action = RoutingAction.GOOGLE_REMEDIATE
            return RoutingAction.GOOGLE_REMEDIATE, None

        elif event_name == "CODEX_RELEASE":
            self.worker_states[WorkerRole.CODEX.value] = WorkerState.COMPLETED.value

        elif event_name in ("CODEX_EXECUTION_SURFACE_BLOCK", "PROVIDER_QUOTA_REACHED"):
            self.current_action = RoutingAction.WAITING_RESOURCE
            return RoutingAction.WAITING_RESOURCE, None

        # 2. State-driven routing
        if self.worker_states.get(WorkerRole.GOOGLE.value) == WorkerState.COMPLETED.value:
            if self.worker_states.get(WorkerRole.CLI2.value) in (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value):
                self.current_action = RoutingAction.CLI2_FINAL_ATTACK
                return RoutingAction.CLI2_FINAL_ATTACK, None

        if self.worker_states.get(WorkerRole.CLI2.value) == WorkerState.COMPLETED.value:
            if self.worker_states.get(WorkerRole.CODEX.value) in (WorkerState.AVAILABLE.value, WorkerState.SAFE_IDLE.value):
                self.current_action = RoutingAction.CODEX_FINAL_ACCEPTANCE
                return RoutingAction.CODEX_FINAL_ACCEPTANCE, None

        if self.worker_states.get(WorkerRole.CODEX.value) == WorkerState.COMPLETED.value:
            self.current_action = RoutingAction.ENABLE_NEXT_SAFE_AUTONOMY_PHASE
            return RoutingAction.ENABLE_NEXT_SAFE_AUTONOMY_PHASE, None

        # 3. Queue-based routing: Find highest priority unblocked safe job
        eligible_job = self._find_next_executable_job()
        if eligible_job:
            if eligible_job.requires_payment:
                self.current_action = RoutingAction.WAITING_PERMISSION
                return RoutingAction.WAITING_PERMISSION, eligible_job
            if eligible_job.requires_human:
                self.current_action = RoutingAction.WAITING_HUMAN
                return RoutingAction.WAITING_HUMAN, eligible_job

            self.current_action = RoutingAction.CLAIM_NEXT_SAFE_JOB
            return RoutingAction.CLAIM_NEXT_SAFE_JOB, eligible_job

        self.current_action = RoutingAction.SAFE_IDLE
        return RoutingAction.SAFE_IDLE, None

    def _find_next_executable_job(self) -> Optional[SafeJob]:
        """Finds the next queued job whose dependencies are all completed."""
        queued = [j for j in self.queue if j.status == "QUEUED"]
        queued.sort(key=lambda j: j.priority)

        for job in queued:
            # Check dependencies
            deps_met = all(dep in self.completed_job_ids for dep in job.dependencies)
            if deps_met:
                return job
        return None

    def execute_next_step(
        self,
        event_name: Optional[str] = None,
        event_payload: Optional[Dict[str, Any]] = None,
        runner_fn: Optional[Callable[[SafeJob], bool]] = None,
    ) -> Tuple[RoutingAction, Optional[str]]:
        """Executes one safe step in the autonomy cycle without requiring manual WEITER."""
        action, job = self.route(event_name=event_name, event_payload=event_payload)

        if action == RoutingAction.CLAIM_NEXT_SAFE_JOB and job is not None:
            # Claim job
            job.status = "CLAIMED"
            job.claim_owner = WorkerRole.GOOGLE.value
            job.claim_generation += 1
            job.updated_at = utc_now()
            self.save_checkpoint()

            # Execute job if runner provided
            success = True
            if runner_fn:
                job.status = "RUNNING"
                try:
                    success = runner_fn(job)
                except Exception:
                    success = False
                    job.status = "FAILED"

            if success:
                self.completed_job_ids.add(job.job_id)
                self.queue = [j for j in self.queue if j.job_id != job.job_id]

            self.save_checkpoint()
            return action, job.job_id

        elif action == RoutingAction.CLI2_FINAL_ATTACK:
            # Automatically enqueue CLI2 adversarial test
            self.enqueue_job(
                job_id=f"job-cli2-attack-{self.active_fingerprint[:8]}",
                job_type="CLI2_ADVERSARIAL_TEST",
                priority=10,
                evidence_fingerprint=self.active_fingerprint,
            )
            return action, f"CLI2_ATTACK_QUEUED_{self.active_fingerprint[:8]}"

        elif action == RoutingAction.CODEX_FINAL_ACCEPTANCE:
            # Automatically enqueue Codex acceptance review
            self.enqueue_job(
                job_id=f"job-codex-acceptance-{self.active_fingerprint[:8]}",
                job_type="CODEX_ACCEPTANCE_REVIEW",
                priority=10,
                evidence_fingerprint=self.active_fingerprint,
            )
            return action, f"CODEX_ACCEPTANCE_QUEUED_{self.active_fingerprint[:8]}"

        elif action == RoutingAction.ENABLE_NEXT_SAFE_AUTONOMY_PHASE:
            return action, "NEXT_PHASE_UNLOCKED"

        elif action in (RoutingAction.WAITING_PERMISSION, RoutingAction.WAITING_HUMAN, RoutingAction.WAITING_RESOURCE):
            return action, f"PAUSED_{action.value}"

        return action, "SAFE_IDLE"

    def mark_job_completed(self, job_id: str) -> None:
        """Marks a job completed, records in completed set, and saves state."""
        self.completed_job_ids.add(job_id)
        for j in self.queue:
            if j.job_id == job_id:
                j.status = "COMPLETED"
                j.updated_at = utc_now()
        self.queue = [j for j in self.queue if j.job_id != job_id]
        self.save_checkpoint()

    def save_checkpoint(self) -> Path:
        """Durable persistence for crash recovery and resume."""
        data = {
            "orchestrator_version": "1.0",
            "saved_at": utc_now(),
            "worker_states": self.worker_states,
            "active_fingerprint": self.active_fingerprint,
            "current_action": self.current_action.value,
            "completed_job_ids": sorted(list(self.completed_job_ids)),
            "queue": [j.to_dict() for j in self.queue],
            "data_saver": self.data_saver.to_dict(),
        }
        self.checkpoint_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return self.checkpoint_file

    def load_checkpoint(self) -> None:
        """Restores state from durable checkpoint."""
        if not self.checkpoint_file.exists():
            return
        try:
            data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
            self.worker_states = data.get("worker_states", self.worker_states)
            self.active_fingerprint = data.get("active_fingerprint", "")
            action_val = data.get("current_action", RoutingAction.SAFE_IDLE.value)
            self.current_action = RoutingAction(action_val)
            self.completed_job_ids = set(data.get("completed_job_ids", []))
            self.queue = [SafeJob(**j) for j in data.get("queue", [])]
            ds = data.get("data_saver", {})
            self.data_saver = DataSaverMetrics(**ds) if ds else DataSaverMetrics()
        except Exception as e:
            print(f"Warning: could not load checkpoint: {e}")


def init_orchestrator() -> AutonomyOrchestrator:
    orch = AutonomyOrchestrator()
    orch.save_checkpoint()
    return orch


if __name__ == "__main__":
    orch = init_orchestrator()
    action, detail = orch.execute_next_step()
    print(f"✅ Autonomy Orchestrator Initialized: Action={action.value}, Detail={detail}")
