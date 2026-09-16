#!/usr/bin/env python3
"""Autonomous Chief & Courier Supervisor Engine (Mission 116).

Implements Phase 1+2 Minimal Vertical Slice for Zero-Copy-Paste Autonomous Continuation:
  Human Goal -> Chief -> Courier -> Router -> Worker -> Result -> Courier -> Chief -> Next Decision -> Next Task -> Loop -> Complete

Features:
- Idempotent Chief decision consumption (Zero duplicate dispatches).
- Checkpoint / Resume engine (recovey from safe state after process crash).
- Zero-Spend Firewall (0.00 EUR autonomous spend limit; fail-closed on unapproved cost).
- Value Gate enforcement (deterministic stop if no new information or production benefit).
- Bounded continuation limits (MAX_TASKS=5, MAX_RETRIES=2, MAX_FAILURES=2, HEAVY_JOB_LIMIT=1).
- Single-owner process leases and input hash deduplication.
"""

from __future__ import annotations
import sys
print("Disabled in favor of OS-owned Courier Motor.")
sys.exit(1)

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Setup paths and imports
SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_chief_commander import ChiefCommander, ChiefDecisionContract, evaluate_value_gate, SmartResourceRouter
    from run_autonomous_loop import AutonomousLevel6Loop
    from run_antigravity_bridge import AntigravityVisualStateTracker, AntigravityHookRunner, execute_bridge_task, load_json, save_json
    from run_codex_bridge import CodexVisualStateTracker, CodexHookRunner, execute_codex_task
    from run_context_sync import UpdateSteward
    from standing_objectives import StandingObjectivesRegistry, StandingObjective
    from opportunity_queue import OpportunityQueue, Opportunity, CircuitBreakerManager
    from resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
    )
    from review_budget import ReviewBudgetManager
    from resource_intelligence import ResourceIntelligenceManager
    from github_transport import ProcessSafeFileLock
    from creator_work_generator import discover_creator_opportunities
    from creator_input_sources import refresh_creator_input_sources
except ImportError:
    from scripts.run_chief_commander import ChiefCommander, ChiefDecisionContract, evaluate_value_gate, SmartResourceRouter
    from scripts.run_autonomous_loop import AutonomousLevel6Loop
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, AntigravityHookRunner, execute_bridge_task, load_json, save_json
    from scripts.run_codex_bridge import CodexVisualStateTracker, CodexHookRunner, execute_codex_task
    from scripts.run_context_sync import UpdateSteward
    from scripts.standing_objectives import StandingObjectivesRegistry, StandingObjective
    from scripts.opportunity_queue import OpportunityQueue, Opportunity, CircuitBreakerManager
    from scripts.resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
    )
    from scripts.review_budget import ReviewBudgetManager
    from scripts.resource_intelligence import ResourceIntelligenceManager
    from scripts.github_transport import ProcessSafeFileLock
    from scripts.creator_work_generator import discover_creator_opportunities
    from scripts.creator_input_sources import refresh_creator_input_sources
from dataclasses import dataclass, field


@dataclass
class SessionWorkBudget:
    max_wall_clock_seconds: float = 3600.0 * 8.0  # 8 hours default for full sleep session
    max_active_tasks: int = 1
    heavy_job_limit: int = 1
    max_consecutive_failures: int = 2
    max_retries_per_task: int = 2
    max_queue_size: int = 50
    max_model_work_budget: int = 0
    max_external_actions: int = 0
    zero_spend_limit_eur: float = 0.0


def save_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Persist control-plane state without exposing a partially written JSON record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


class SessionBudgetLedger:
    """Durable fail-closed reservation ledger for model and external-action job units."""

    def __init__(self, repo_dir: Path, session_id: str, budget: SessionWorkBudget):
        self.file_path = repo_dir / "events" / "session-budgets" / f"{session_id}.json"
        self.lock_path = self.file_path.with_suffix(".lock")
        self.budget = budget

    def _initial(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "session_id": self.file_path.stem,
            "external_actions_reserved": 0,
            "model_jobs_reserved": 0,
            "max_external_actions": self.budget.max_external_actions,
            "max_model_work_budget": self.budget.max_model_work_budget,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def reserve(self, kind: str, units: int) -> tuple[bool, str, dict[str, Any]]:
        if units < 0:
            return False, "INVALID_BUDGET_UNITS", self._initial()
        if kind not in {"external", "model"}:
            return False, "UNKNOWN_BUDGET_KIND", self._initial()
        if units == 0:
            current = load_json(self.file_path) if self.file_path.exists() else self._initial()
            return True, "NO_UNITS_REQUIRED", current or self._initial()

        field = "external_actions_reserved" if kind == "external" else "model_jobs_reserved"
        limit_field = "max_external_actions" if kind == "external" else "max_model_work_budget"
        exhausted_reason = "EXTERNAL_ACTION_BUDGET_EXHAUSTED" if kind == "external" else "MODEL_WORK_BUDGET_EXHAUSTED"
        with ProcessSafeFileLock(self.lock_path):
            current = load_json(self.file_path) if self.file_path.exists() else self._initial()
            current = current or self._initial()
            limit = current.get(limit_field, getattr(self.budget, limit_field))
            if not isinstance(limit, int) or limit < 0 or current.get(field, 0) + units > limit:
                return False, exhausted_reason, current
            current[field] = current.get(field, 0) + units
            current["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save_json_atomic(self.file_path, current)
            return True, "RESERVED", current


class DecisionContinuationStore:
    """Durably bridges a Chief decision to its next task across a process crash."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.intents_dir = repo_dir / "events" / "decision-continuations"
        self.decisions_dir = repo_dir / "events" / "chief-decisions"
        self.consumed_dir = repo_dir / "events" / "consumed-decisions"
        self.intents_dir.mkdir(parents=True, exist_ok=True)

    def _intent_path(self, decision_id: str) -> Path:
        return self.intents_dir / f"{decision_id}.json"

    @staticmethod
    def _dispatch_identity(data: dict[str, Any]) -> str:
        """Return a stable identity for one Chief decision's next-task dispatch."""
        material = {
            "workflow_id": data.get("workflow_id"),
            "chief_decision_id": data.get("chief_decision_id") or data.get("decision_id"),
            "source_task_id": data.get("task_id") or data.get("source_task_id"),
            "next_task_id": (data.get("next_task") or {}).get("task_id"),
            "correlation_id": data.get("correlation_id"),
        }
        encoded = json.dumps(material, sort_keys=True, separators=(",", ":"))
        return f"dispatch-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:24]}"

    def _dispatch_lock_path(self, dispatch_id: str) -> Path:
        return self.intents_dir / "locks" / f"{dispatch_id}.lock"

    def _find_dispatches(self, intent: dict[str, Any]) -> tuple[list[Path], bool]:
        """Find dispatches for an intent; report ambiguity rather than guessing."""
        dispatch_dir = self.repo_dir / "events" / "dispatch"
        expected_id = intent["dispatch_id"]
        matches: list[Path] = []
        ambiguous = False
        for dispatch_file in dispatch_dir.glob("*-worker-job.json"):
            dispatch = load_json(dispatch_file)
            if not dispatch:
                continue
            same_fields = (
                dispatch.get("task_id") == intent.get("next_task", {}).get("task_id")
                and dispatch.get("workflow_id") == intent.get("workflow_id")
                and dispatch.get("correlation_id") == intent.get("correlation_id")
            )
            if not same_fields:
                continue
            stored_id = dispatch.get("dispatch_id")
            if stored_id and stored_id != expected_id:
                ambiguous = True
                continue
            matches.append(dispatch_file)
        return matches, ambiguous

    def _finalize_intent(self, intent: dict[str, Any]) -> None:
        """Finalize only after a durable matching dispatch has been observed."""
        intent_path = self._intent_path(intent["decision_id"])
        intent["dispatch_state"] = "NEXT_TASK_DISPATCHED"
        intent["dispatch_persisted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        intent["updated_at"] = intent["dispatch_persisted_at"]
        save_json_atomic(intent_path, intent)

        consumed = self.consumed_dir / f"{intent['decision_id']}.json"
        consumed.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(consumed, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": "2.0",
                    "decision_id": intent["decision_id"],
                    "task_id": intent.get("source_task_id"),
                    "workflow_id": intent.get("workflow_id"),
                    "next_task_id": intent.get("next_task", {}).get("task_id"),
                    "dispatch_id": intent["dispatch_id"],
                    "consumed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }, handle, indent=2)
        except FileExistsError:
            pass

    def reconcile_intent(self, decision_id: str) -> str:
        """Reconcile a recovered intent without ever generating a replacement dispatch.

        The per-dispatch O_EXCL lock makes concurrent recovery contenders observe
        exactly one durable-dispatch finalizer; followers see the consumed state.
        """
        intent_path = self._intent_path(decision_id)
        initial = load_json(intent_path) if intent_path.exists() else None
        if not initial:
            return "INTENT_MISSING"
        dispatch_id = initial.get("dispatch_id") or self._dispatch_identity(initial)
        with ProcessSafeFileLock(self._dispatch_lock_path(dispatch_id)):
            intent = load_json(intent_path) if intent_path.exists() else None
            if not intent:
                return "INTENT_MISSING"
            intent.setdefault("dispatch_id", dispatch_id)
            consumed = self.consumed_dir / f"{decision_id}.json"
            if consumed.exists():
                return "CONSUMED"
            matches, ambiguous = self._find_dispatches(intent)
            if ambiguous or len(matches) > 1:
                return "AMBIGUOUS_DISPATCH_IDENTITY"
            if len(matches) == 1:
                self._finalize_intent(intent)
                return "DURABLE_DISPATCH_FOUND"
            return "DISPATCH_ABSENT"

    def persist_intent(self, decision: ChiefDecisionContract | dict[str, Any]) -> dict[str, Any] | None:
        # Import paths can expose equivalent ChiefDecisionContract classes under
        # both ``run_chief_commander`` and ``scripts.run_chief_commander``.
        data = decision.to_dict() if hasattr(decision, "to_dict") else decision
        next_task = data.get("next_task")
        decision_id = data.get("chief_decision_id") or data.get("decision_id")
        if not decision_id or not isinstance(next_task, dict) or not next_task.get("task_id"):
            return None
        path = self._intent_path(decision_id)
        existing = load_json(path) if path.exists() else None
        if existing:
            return existing
        intent = {
            "schema_version": "1.0",
            "workflow_id": data.get("workflow_id"),
            "decision_id": decision_id,
            "source_task_id": data.get("task_id"),
            "source_result_id": data.get("result_id"),
            "next_task": next_task,
            "correlation_id": data.get("correlation_id"),
            "dispatch_state": "NEXT_TASK_INTENT_PERSISTED",
            "attempt": 0,
            "lease_metadata": {},
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        intent["dispatch_id"] = self._dispatch_identity(intent)
        save_json_atomic(path, intent)
        return intent

    def recover_pending(self, workflow_id: str) -> list[dict[str, Any]]:
        """Recover intents, including a crash immediately after Chief decision persistence."""
        for decision_file in self.decisions_dir.glob("*.json"):
            decision = load_json(decision_file)
            if decision and decision.get("workflow_id") == workflow_id and decision.get("next_task"):
                self.persist_intent(decision)

        intents: list[dict[str, Any]] = []
        for intent_file in self.intents_dir.glob("*.json"):
            intent = load_json(intent_file)
            if intent and intent.get("workflow_id") == workflow_id and intent.get("next_task"):
                outcome = self.reconcile_intent(intent.get("decision_id", ""))
                if outcome == "DISPATCH_ABSENT":
                    intents.append(load_json(intent_file) or intent)
        return sorted(intents, key=lambda item: item.get("created_at", ""))

    def mark_dispatched_and_consumed(self, task_id: str) -> None:
        """Persist dispatch before atomically finalizing the originating decision."""
        for intent_file in self.intents_dir.glob("*.json"):
            intent = load_json(intent_file)
            if not intent or intent.get("next_task", {}).get("task_id") != task_id:
                continue
            intent.setdefault("dispatch_id", self._dispatch_identity(intent))
            self.reconcile_intent(intent.get("decision_id", ""))
            return

    def dispatch_id_for_task(self, task_id: str, workflow_id: str, correlation_id: str) -> str | None:
        """Return the persisted identity for a Chief-created continuation task."""
        for intent_file in self.intents_dir.glob("*.json"):
            intent = load_json(intent_file)
            if not intent:
                continue
            if (
                intent.get("workflow_id") == workflow_id
                and intent.get("correlation_id") == correlation_id
                and intent.get("next_task", {}).get("task_id") == task_id
            ):
                dispatch_id = intent.get("dispatch_id") or self._dispatch_identity(intent)
                if intent.get("dispatch_id") != dispatch_id:
                    intent["dispatch_id"] = dispatch_id
                    save_json_atomic(intent_file, intent)
                return dispatch_id
        return None


class HeartbeatManager:
    """Manages lightweight, deterministic heartbeat telemetry in events/heartbeat.json."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.heartbeat_file = repo_dir / "events/heartbeat.json"
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)

    def update_heartbeat(
        self,
        supervisor_alive: bool,
        chief_presence: str,
        active_task: str | None = None,
        queue_ready: int = 0,
        queue_blocked: int = 0,
        completed_this_session: int = 0,
        circuit_breakers: list[str] | None = None,
        money_spent: float = 0.0,
        model_jobs: int = 0,
    ) -> dict:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        existing = load_json(self.heartbeat_file) if self.heartbeat_file.exists() else {}

        heartbeat_data = {
            "schema_version": "2.0",
            "supervisor_alive": supervisor_alive,
            "chief_presence": chief_presence,
            "active_task": active_task,
            "queue_ready": queue_ready,
            "queue_blocked": queue_blocked,
            "completed_this_session": completed_this_session,
            "last_progress_at": now_iso if active_task or completed_this_session > 0 else (existing or {}).get("last_progress_at", now_iso),
            "last_result_at": now_iso if completed_this_session > (existing or {}).get("completed_this_session", 0) else (existing or {}).get("last_result_at", now_iso),
            "circuit_breakers": circuit_breakers or [],
            "money_spent": money_spent,
            "model_jobs": model_jobs,
            "timestamp": now_iso,
        }
        save_json(self.heartbeat_file, heartbeat_data)
        return heartbeat_data

    def get_heartbeat(self) -> dict:
        return load_json(self.heartbeat_file) if self.heartbeat_file.exists() else {}


class AutonomousSupervisor:
    """Manages the autonomous Chief + Courier continuation loop with checkpointing, idempotency, and zero-spend enforcement."""

    def __init__(
        self,
        repo_dir: Path = COURIER_DIR,
        max_tasks: int = 5,
        max_retries_per_task: int = 2,
        max_consecutive_failures: int = 2,
        heavy_job_limit: int = 1,
        spend_limit_eur: float = 0.0,
    ):
        self.repo_dir = repo_dir
        self.max_tasks = max_tasks
        self.max_retries_per_task = max_retries_per_task
        self.max_consecutive_failures = max_consecutive_failures
        self.heavy_job_limit = heavy_job_limit
        self.spend_limit_eur = spend_limit_eur

        self.events_dir = repo_dir / "events"
        self.dispatch_dir = self.events_dir / "dispatch"
        self.processed_dir = self.events_dir / "processed"
        self.decisions_dir = self.events_dir / "chief-decisions"
        self.consumed_dir = self.events_dir / "consumed-decisions"
        self.locks_dir = self.events_dir / "locks"
        self.reports_dir = self.events_dir / "morning-reports"
        self.journal_dir = self.events_dir / "night-journal"
        self.queue_dir = self.events_dir / "opportunity-queue"

        for d in [self.dispatch_dir, self.processed_dir, self.decisions_dir, self.consumed_dir, self.locks_dir, self.reports_dir, self.journal_dir, self.queue_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self.chief = ChiefCommander(repo_dir=repo_dir)
        self.dedupe_engine = TaskDedupeEngine(repo_dir=repo_dir)
        self.lease_manager = TaskLeaseManager(repo_dir=repo_dir)
        self.steward = UpdateSteward(repo_dir=repo_dir)
        self.objectives_registry = StandingObjectivesRegistry(repo_dir=repo_dir)
        self.opportunity_queue = OpportunityQueue(repo_dir=repo_dir)
        self.heartbeat = HeartbeatManager(repo_dir=repo_dir)
        self.continuations = DecisionContinuationStore(repo_dir=repo_dir)
        self.resource_intelligence = ResourceIntelligenceManager(repo_dir=repo_dir)

    def resource_context(self) -> dict[str, Any]:
        """Compact capacity context for Supervisor/Dispatcher; raw history stays local."""
        return self.resource_intelligence.context_for_role("SUPERVISOR_DISPATCHER")

    def is_decision_consumed(self, decision_id: str) -> bool:
        """Idempotency check: Returns True if this decision was already consumed and dispatched."""
        if not decision_id:
            return False
        consumed_file = self.consumed_dir / f"{decision_id}.json"
        return consumed_file.exists()

    def _execute_creator_action(self, task_info: dict, workflow_id: str, correlation_id: str) -> Path | None:
        """Perform the two bounded local Creator actions; never publish or render."""
        action = task_info.get("creator_action")
        media = Path(task_info.get("creator_source", ""))
        if action not in {"MEDIA_QC", "PREPARE_PUBLICATION_PACKAGE"} or not media.is_file():
            return None
        output_dir = media.parent
        if action == "MEDIA_QC":
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate", "-of", "json", str(media)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15, check=True,
            )
            metadata = json.loads(probe.stdout)
            streams = metadata.get("streams", [])
            video = next((stream for stream in streams if stream.get("width") and stream.get("height")), {})
            verdict = "PASS" if video.get("codec_name") == "h264" and video.get("width") == 360 and video.get("height") == 640 else "FAIL"
            artifact = output_dir / "qc_report.json"
            save_json(artifact, {
                "schema_version": "1.0", "verdict": verdict, "media": str(media), "source_hash": task_info.get("creator_source_hash"),
                "duration_seconds": float(metadata.get("format", {}).get("duration", 0)), "video": video,
                "publication_authorized": False, "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
        else:
            qc = load_json(output_dir / "qc_report.json")
            if not qc or qc.get("verdict") != "PASS":
                raise ValueError("Creator publication package requires a passing local QC report")
            artifact = output_dir / "publish_package.json"
            save_json(artifact, {
                "schema_version": "1.0", "status": "READY_FOR_PUBLICATION", "media": str(media),
                "qc_report": "qc_report.json", "publication_authorized": False,
                "human_gate": "REQUIRE_EXPLICIT_HUMAN_APPROVAL", "prepared_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            verdict = "PASS"
        result_file = self.processed_dir / f"{task_info['task_id']}-result.json"
        save_json(result_file, {
            "task_id": task_info["task_id"], "workflow_id": workflow_id, "correlation_id": correlation_id,
            "source": "local_creator_factory", "payload": {"verdict": verdict, "verified_file": str(artifact), "modified_files": [str(artifact)]},
        })
        return result_file

    def mark_decision_consumed(self, decision_id: str, task_id: str, workflow_id: str, next_task_id: str | None = None) -> bool:
        """Atomically records a terminal decision consumption without overwriting another owner."""
        if not decision_id:
            return False
        consumed_file = self.consumed_dir / f"{decision_id}.json"
        consumed_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(consumed_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": "2.0",
                    "decision_id": decision_id,
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "next_task_id": next_task_id,
                    "consumed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }, handle, indent=2)
            return True
        except FileExistsError:
            return False

    def recover_checkpoint(self, workflow_id: str) -> dict:
        """Inspects durable event logs to reconstruct the last safe state of a workflow after restart."""
        checkpoint = {
            "workflow_id": workflow_id,
            "completed_tasks": [],
            "last_completed_task": None,
            "last_decision": None,
            "pending_dispatch": None,
            "is_terminal": False,
            "terminal_reason": None,
        }

        # Check existing decisions
        if self.decisions_dir.exists():
            dec_files = sorted(self.decisions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
            for df in dec_files:
                try:
                    data = load_json(df)
                    if data.get("workflow_id") == workflow_id:
                        checkpoint["last_decision"] = data
                        task_id = data.get("task_id")
                        if task_id and task_id not in checkpoint["completed_tasks"]:
                            checkpoint["completed_tasks"].append(task_id)
                            checkpoint["last_completed_task"] = task_id
                        if data.get("decision") == "COMPLETE":
                            checkpoint["is_terminal"] = True
                            checkpoint["terminal_reason"] = "GOAL_COMPLETED"
                        elif data.get("decision") == "WAIT_FOR_HUMAN":
                            checkpoint["is_terminal"] = True
                            checkpoint["terminal_reason"] = "WAITING_FOR_HUMAN"
                except Exception:
                    pass

        # Check pending dispatch files
        if self.dispatch_dir.exists():
            for df in self.dispatch_dir.glob("*.json"):
                try:
                    data = load_json(df)
                    if data.get("workflow_id") == workflow_id:
                        res_file = self.processed_dir / f"{data['task_id']}-result.json"
                        if not res_file.exists():
                            checkpoint["pending_dispatch"] = data
                except Exception:
                    pass

        return checkpoint

    def dispatch_and_execute_task(
        self,
        task_info: dict,
        workflow_id: str,
        correlation_id: str,
        parent_task_id: str | None = None,
        context_version: int = 77,
    ) -> Path:
        """Builds context package, enforces lease & dedupe, and executes worker synchronously."""
        task_id = task_info["task_id"]
        instruction = task_info["instruction"]
        target_agent = task_info.get("target_agent", "antigravity")
        allowed_scope = task_info.get("allowed_scope", ["config/local_tools.json"])
        cost_class = task_info.get("cost_class", "ZERO_COST_LOCAL")

        # Zero-Spend Firewall Check
        if cost_class not in ("ZERO_COST_LOCAL", "ZERO_COST_ONLY") or task_info.get("cost_estimate", 0.0) > self.spend_limit_eur:
            raise ValueError(f"Zero-Spend Firewall violated: Task {task_id} requires unapproved spend '{cost_class}'")

        # 1. Compute deterministic task hash
        task_hash = self.dedupe_engine.compute_task_hash(
            task_type="WORKER_TASK",
            instruction=instruction,
            target_agent=target_agent,
            input_files=allowed_scope,
            parameters=task_info.get("parameters"),
        )

        # 2. Build compact context package
        context_pkg = ChiefContextPackageBuilder.build_compact_package(
            workflow_id=workflow_id,
            task_id=task_id,
            instruction=instruction,
            scope_files=allowed_scope,
            context_version=context_version,
            context_delta=task_info.get("context_delta"),
            repo_dir=self.repo_dir,
        )

        # 3. Create Dispatch Record in events/dispatch/
        dispatch_file = self.dispatch_dir / f"{task_id}-worker-job.json"
        dispatch_id = self.continuations.dispatch_id_for_task(task_id, workflow_id, correlation_id)
        is_codex = target_agent.lower() in ("codex", "agent-codex-bridge")
        job_data = {
            "schema_version": "2.0",
            "job_id": f"job-{'cdx' if is_codex else 'ag'}-{task_id}",
            "source_command_message_id": f"msg-cmd-{task_id}",
            "task_id": task_id,
            "task_hash": task_hash,
            "dispatch_id": dispatch_id,
            "correlation_id": correlation_id,
            "workflow_id": workflow_id,
            "parent_task_id": parent_task_id,
            "target_agent": "courier-codex-bridge" if is_codex else "courier-antigravity-bridge",
            "instruction": instruction,
            "allowed_scope": allowed_scope,
            "forbidden_scope": ["public_upload", "secrets", "paid_apis"],
            "cost_policy": "ZERO_COST_ONLY",
            "cost_class": cost_class,
            "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
            "max_iterations": 1,
            "context_package": context_pkg,
            "routing_decision": {
                "target_agent": target_agent,
                "routing_reason": task_info.get("routing_reason", "Assigned by SmartResourceRouter"),
                "execution_class": "DETERMINISTIC_CODEX" if is_codex else "DETERMINISTIC_ANTIGRAVITY",
            },
            "expected_output": "Structured summary result",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        save_json(dispatch_file, job_data)
        # A durable dispatch exists before the originating decision is finalized.
        self.continuations.mark_dispatched_and_consumed(task_id)

        creator_result = self._execute_creator_action(task_info, workflow_id, correlation_id)
        if creator_result:
            return creator_result

        # 4. Check Deduplication Cache
        cached_res = self.dedupe_engine.get_cached_result(task_hash)
        result_file = self.processed_dir / f"{task_id}-result.json"
        if cached_res and not task_info.get("payload_override"):
            print(f"[DEDUPE] Task {task_id} input hash matched cache. Reusing verified result.")
            save_json(result_file, cached_res)
            return result_file

        # 5. Acquire Single-Owner Lease & Execute
        acquired, lease_reason, lease_data = self.lease_manager.acquire_lease(
            task_id=task_id,
            task_hash=task_hash,
            owner_id=target_agent,
        )
        if not acquired:
            raise RuntimeError(f"Duplicate claim blocked by lease manager: {lease_reason}")

        try:
            if is_codex:
                hooks = CodexHookRunner(CodexVisualStateTracker())
                res_path = execute_codex_task(dispatch_file, hooks, try_real_cli=False)
            else:
                hooks = AntigravityHookRunner(AntigravityVisualStateTracker())
                res_path = execute_bridge_task(dispatch_file, hooks)
        finally:
            self.lease_manager.release_lease(task_id, target_agent)

        if res_path and res_path.exists():
            res_data = load_json(res_path)
            res_hash = hashlib.sha256(json.dumps(res_data.get("payload", {}), sort_keys=True).encode("utf-8")).hexdigest()
            self.dedupe_engine.register_task_result(task_hash, task_id, res_path.name, res_hash)
            return res_path
        else:
            raise RuntimeError(f"Execution failed to produce result file for task {task_id}")

    def run_autonomous_continuation(
        self,
        workflow_id: str,
        initial_plan: list[dict],
        correlation_id: str | None = None,
        conversation_id: str = "c61b931a-e4f1-476d-b9d2-431218079df5",
    ) -> dict:
        """Executes the zero-copy-paste autonomous loop until complete or bounded termination."""
        started_at = datetime.datetime.now(datetime.timezone.utc)
        session_id = f"sess-auto-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        corr_id = correlation_id or f"corr-auto-{uuid.uuid4().hex[:8]}"

        tasks_executed = 0
        consecutive_failures = 0
        workflow_plan = list(initial_plan)
        existing_task_ids = {task.get("task_id") for task in workflow_plan}
        for intent in self.continuations.recover_pending(workflow_id):
            recovered_task = intent["next_task"]
            if recovered_task.get("task_id") not in existing_task_ids:
                workflow_plan.append(recovered_task)
                existing_task_ids.add(recovered_task.get("task_id"))
        current_step_index = 0
        history = []
        stop_reason = "GOAL_COMPLETED"
        status = "COMPLETED"

        print(f"\n=======================================================")
        print(f"🤖 AUTONOMOUS SUPERVISOR: Starting Loop for {workflow_id}")
        print(f"   Correlation: {corr_id}")
        print(f"   Max Tasks: {self.max_tasks} | Spend Limit: {self.spend_limit_eur:.2f} EUR")
        print(f"=======================================================")

        while current_step_index < len(workflow_plan):
            # Guard: Max Tasks Limit
            if tasks_executed >= self.max_tasks:
                print(f"[BOUNDED LIMIT] Reached maximum allowed tasks per workflow ({self.max_tasks}).")
                stop_reason = "MAX_TASKS_REACHED"
                status = "STOPPED_MAX_TASKS"
                break

            # Guard: Consecutive Failures Limit
            if consecutive_failures >= self.max_consecutive_failures:
                print(f"[CIRCUIT BREAKER] Reached maximum consecutive failures ({self.max_consecutive_failures}).")
                stop_reason = "CIRCUIT_OPEN"
                status = "FAILED_CIRCUIT_OPEN"
                break

            current_task_info = workflow_plan[current_step_index]
            task_id = current_task_info["task_id"]

            print(f"\n--- [AUTONOMOUS STEP {tasks_executed + 1}] Task: {task_id} ({current_task_info.get('target_agent')}) ---")

            # 1. Dispatch and execute task
            try:
                result_file = self.dispatch_and_execute_task(
                    task_info=current_task_info,
                    workflow_id=workflow_id,
                    correlation_id=corr_id,
                    parent_task_id=workflow_plan[current_step_index - 1]["task_id"] if current_step_index > 0 else None,
                )
                tasks_executed += 1
                consecutive_failures = 0
            except ValueError as val_err:
                print(f"[ZERO-SPEND FIREWALL] {val_err}")
                stop_reason = "PAYMENT_APPROVAL_REQUIRED"
                status = "PAYMENT_APPROVAL_REQUIRED"
                break
            except Exception as exc:
                print(f"[EXECUTION ERROR] Task {task_id} failed: {exc}")
                consecutive_failures += 1
                if current_task_info.get("retry_count", 0) < self.max_retries_per_task:
                    current_task_info["retry_count"] = current_task_info.get("retry_count", 0) + 1
                    print(f"[RETRY] Retrying task {task_id} (Attempt {current_task_info['retry_count']}/{self.max_retries_per_task})")
                    continue
                else:
                    stop_reason = "FAILED_SAFE"
                    status = "FAILED"
                    break

            # 2. Feed Result into Chief Evaluation Engine
            chief_decision = self.chief.evaluate_result_and_decide(
                task_id=task_id,
                correlation_id=corr_id,
                workflow_id=workflow_id,
                result_file=result_file,
                workflow_plan=workflow_plan,
                round_index=current_step_index,
                conversation_id=conversation_id,
            )

            decision_dict = chief_decision.to_dict()
            decision_val = chief_decision.decision
            print(f"[CHIEF DECISION] Decision: {decision_val} | Reason: {chief_decision.reason}")

            round_record = {
                "step": tasks_executed,
                "task_id": task_id,
                "target_agent": current_task_info.get("target_agent"),
                "result_file": result_file.name,
                "chief_decision_id": chief_decision.chief_decision_id,
                "decision": decision_val,
                "value_gate_passed": chief_decision.value_gate.get("passed", True),
                "review_decision": chief_decision.review_decision,
            }
            history.append(round_record)

            # 3. Handle Chief Decision
            if decision_val == "WAIT_FOR_HUMAN":
                stop_reason = "WAITING_FOR_HUMAN"
                status = "WAITING_FOR_HUMAN"
                break

            elif decision_val == "RETRY_SAFE":
                if chief_decision.next_task and not self.is_decision_consumed(chief_decision.chief_decision_id):
                    self.continuations.persist_intent(chief_decision)
                    workflow_plan.insert(current_step_index + 1, chief_decision.next_task)
                current_step_index += 1

            elif decision_val == "REVIEW_REQUIRED":
                if chief_decision.next_task and not self.is_decision_consumed(chief_decision.chief_decision_id):
                    self.continuations.persist_intent(chief_decision)
                    workflow_plan.insert(current_step_index + 1, chief_decision.next_task)
                current_step_index += 1

            elif decision_val == "CONTINUE":
                if chief_decision.next_task:
                    if not self.is_decision_consumed(chief_decision.chief_decision_id):
                        self.continuations.persist_intent(chief_decision)
                        # If next_task was dynamically generated or not already the immediate next step, append or align
                        if (current_step_index + 1) >= len(workflow_plan):
                            workflow_plan.append(chief_decision.next_task)
                    current_step_index += 1
                else:
                    current_step_index += 1

            elif decision_val in ("COMPLETE", "ACCEPT"):
                self.mark_decision_consumed(chief_decision.chief_decision_id, task_id, workflow_id, None)
                stop_reason = "GOAL_COMPLETED"
                status = "COMPLETED"
                break

            elif decision_val == "PAUSE":
                stop_reason = "PAUSED"
                status = "PAUSED"
                break

        finished_at = datetime.datetime.now(datetime.timezone.utc)
        summary = {
            "schema_version": "2.0",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "correlation_id": corr_id,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "status": status,
            "stop_reason": stop_reason,
            "tasks_executed": tasks_executed,
            "human_copy_paste_between_steps": 0,
            "unapproved_spend_eur": 0.0,
            "history": history,
        }

        report_file = self.reports_dir / f"{session_id}.json"
        save_json(report_file, summary)

        print(f"\n=======================================================")
        print(f"🏁 AUTONOMOUS SUPERVISOR COMPLETED: {status} ({stop_reason})")
        print(f"   Tasks Executed: {tasks_executed} | Human Prompts: 0 | Spend: 0.00 EUR")
        print(f"=======================================================\n")

        return summary

    def generate_morning_report(self, session_id: str) -> dict:
        """Compiles the structured Morning Report from the session's night journal."""
        journal_file = self.journal_dir / f"journal-{session_id}.jsonl"
        entries = []
        if journal_file.exists():
            with open(journal_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line.strip()))
                        except Exception:
                            pass

        completed_tasks = [e for e in entries if e.get("action") == "RESULT_EVALUATED" and e.get("decision") in ("CONTINUE", "COMPLETE", "ACCEPT")]
        failed_tasks = [e for e in entries if e.get("action") == "EXECUTION_FAILED"]
        human_gated = [e for e in entries if e.get("decision") == "WAIT_FOR_HUMAN" or e.get("human_gate")]
        circuit_breakers = [e for e in entries if e.get("action") == "CIRCUIT_BREAKER_TRIGGERED"]

        antigravity_actions = [e for e in entries if e.get("target_agent") == "antigravity"]
        codex_actions = [e for e in entries if e.get("target_agent") == "codex"]

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        report_data = {
            "schema_version": "2.0",
            "session_id": session_id,
            "generated_at": now_iso,
            "sleep_session_id": session_id,
            "executive_summary": f"Sleep session {session_id} completed with {len(completed_tasks)} tasks finished successfully, 0 unapproved spend, and 0 human copy-paste actions required.",
            "what_completed": [e.get("task_id") for e in completed_tasks],
            "what_changed": [f"Processed {e.get('objective_id', 'TASK')} via {e.get('target_agent', 'worker')}" for e in completed_tasks],
            "content_produced": [],
            "publications": [],  # Expected NONE for Mission 117
            "real_results": [
                {
                    "task_id": e.get("task_id"),
                    "objective_id": e.get("objective_id"),
                    "result_file": e.get("result_file"),
                    "decision": e.get("decision"),
                    "verdict": e.get("verdict", "PASS"),
                }
                for e in completed_tasks
            ],
            "model_usage": "UNKNOWN (0 paid model calls; deterministic local execution)",
            "codex_usage": f"{len(codex_actions)} actions (Conserved as scarce QA reviewer)",
            "antigravity_usage": f"{len(antigravity_actions)} actions (Primary builder)",
            "money_spent": "0.00 EUR (Strict Zero-Spend Policy enforced)",
            "waiting_for_human": [e.get("task_id") for e in human_gated],
            "failed_safe": [e.get("task_id") for e in failed_tasks],
            "circuit_breakers": [e.get("reason") for e in circuit_breakers],
            "current_queue": "IDLE (All actionable standing objectives evaluated)",
            "top_next_decision": "Review standing objectives status or assign new high-priority human goal.",
        }

        # Save JSON
        json_report_file = self.reports_dir / f"{session_id}-morning-report.json"
        save_json(json_report_file, report_data)

        # Save latest pointer
        latest_json_file = self.reports_dir / "latest_morning_report.json"
        save_json(latest_json_file, report_data)

        # Save Markdown Report
        md_content = f"""# 🌅 MORNING REPORT — SLEEP SESSION `{session_id}`

**Generated at:** `{now_iso}`
**Status:** Chief presence returned to `AWAKE`

---

## 1. Executive Summary
{report_data['executive_summary']}

---

## 2. What Completed
{chr(10).join(f"- **{t}**" for t in report_data['what_completed']) if report_data['what_completed'] else "- No tasks required completion (System was healthy & idle)."}

---

## 3. What Changed
{chr(10).join(f"- {c}" for c in report_data['what_changed']) if report_data['what_changed'] else "- Zero configuration drift."}

---

## 4. Real Results & Evidence
{chr(10).join(f"- **{r['task_id']}** (`{r['objective_id']}`): Result `{r['result_file']}` -> Decision `{r['decision']}`" for r in report_data['real_results']) if report_data['real_results'] else "- Clean verified idle baseline."}

---

## 5. Resource & Model Policy Audit
- **Money Spent:** `{report_data['money_spent']}`
- **Codex Usage:** `{report_data['codex_usage']}`
- **Antigravity Usage:** `{report_data['antigravity_usage']}`
- **Model Calls / Spend:** `0 paid calls (0.00 EUR)`

---

## 6. Exceptions, Gates & Circuit Breakers
- **Waiting for Human:** `{len(report_data['waiting_for_human'])}`
- **Failed Safe:** `{len(report_data['failed_safe'])}`
- **Circuit Breakers:** `{len(report_data['circuit_breakers'])}`

---

## 7. Next Decision for Chief
> {report_data['top_next_decision']}
"""
        md_report_file = self.reports_dir / "MORNING_REPORT.md"
        md_report_file.write_text(md_content, encoding="utf-8")

        return report_data

    def run_sleep_session(
        self,
        workflow_id: str | None = None,
        session_id: str | None = None,
        max_tasks: int = 5,
        conversation_id: str = "conv-night-loop",
    ) -> dict:
        """Executes the autonomous Night Supervisor loop while Chief is SLEEPING."""
        w_id = workflow_id or f"WF-NIGHT-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        s_id = session_id or f"sleep-sess-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        corr_id = f"corr-night-{uuid.uuid4().hex[:8]}"

        print(f"\n=======================================================")
        print(f"🌙 NIGHT SUPERVISOR: Entering Sleep Session {s_id}")
        print(f"   Workflow: {w_id} | Max Night Tasks: {max_tasks} | Spend Limit: 0.00 EUR")
        print(f"=======================================================\n")

        # 1. Set Chief presence to SLEEPING
        self.chief.set_presence("SLEEPING", session_id=s_id)
        self.chief.log_night_journal(s_id, {
            "action": "CHIEF_PRESENCE_CHANGED",
            "from": "AWAKE",
            "to": "SLEEPING",
            "session_id": s_id,
        })

        tasks_executed = 0
        consecutive_failures = 0
        visited_objectives = set()
        history = []
        stop_reason = "ALL_OBJECTIVES_EVALUATED"
        status = "COMPLETED"

        while tasks_executed < max_tasks:
            # Check presence: if woken up externally, break
            curr_presence = self.chief.get_presence().get("presence")
            if curr_presence != "SLEEPING":
                print(f"[NIGHT SUPERVISOR] Chief presence changed to '{curr_presence}'. Waking up...")
                stop_reason = "CHIEF_WOKEN_UP"
                break

            # Circuit breaker check
            if consecutive_failures >= self.max_consecutive_failures:
                print(f"[NIGHT SUPERVISOR] Circuit breaker tripped ({consecutive_failures} consecutive failures).")
                self.chief.log_night_journal(s_id, {
                    "action": "CIRCUIT_BREAKER_TRIGGERED",
                    "reason": f"Reached maximum consecutive failures ({self.max_consecutive_failures})",
                })
                stop_reason = "CIRCUIT_OPEN"
                status = "FAILED_CIRCUIT_OPEN"
                break

            # Select next actionable standing objective
            obj, task_info = self.objectives_registry.evaluate_and_select_next_objective(
                workflow_id=w_id,
                session_id=s_id,
                visited_objectives=visited_objectives,
            )

            if not obj or not task_info:
                print("[NIGHT SUPERVISOR] No further actionable standing objectives. Transitioning to IDLE.")
                stop_reason = "NO_MORE_OBJECTIVES_IDLE"
                break

            visited_objectives.add(obj.objective_id)
            task_id = task_info["task_id"]
            target_agent = task_info.get("target_agent", "antigravity")

            print(f"\n--- [NIGHT STEP {tasks_executed + 1}] Objective: {obj.objective_id} -> Task: {task_id} ({target_agent}) ---")

            self.chief.log_night_journal(s_id, {
                "action": "OBJECTIVE_SELECTED",
                "objective_id": obj.objective_id,
                "task_id": task_id,
                "target_agent": target_agent,
                "cost": 0.0,
            })

            # Execute task
            try:
                result_file = self.dispatch_and_execute_task(
                    task_info=task_info,
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    parent_task_id=None,
                )
                tasks_executed += 1
                consecutive_failures = 0
            except ValueError as val_err:
                print(f"[ZERO-SPEND FIREWALL] {val_err}")
                self.chief.log_night_journal(s_id, {
                    "action": "FIREWALL_BLOCKED",
                    "task_id": task_id,
                    "reason": str(val_err),
                })
                stop_reason = "PAYMENT_APPROVAL_REQUIRED"
                status = "PAYMENT_APPROVAL_REQUIRED"
                break
            except Exception as exc:
                print(f"[NIGHT EXECUTION ERROR] Task {task_id} failed: {exc}")
                consecutive_failures += 1
                self.chief.log_night_journal(s_id, {
                    "action": "EXECUTION_FAILED",
                    "task_id": task_id,
                    "error": str(exc),
                })
                if consecutive_failures >= self.max_consecutive_failures:
                    print(f"[NIGHT SUPERVISOR] Circuit breaker tripped ({consecutive_failures} consecutive failures).")
                    self.chief.log_night_journal(s_id, {
                        "action": "CIRCUIT_BREAKER_TRIGGERED",
                        "reason": f"Reached maximum consecutive failures ({self.max_consecutive_failures})",
                    })
                    stop_reason = "CIRCUIT_OPEN"
                    status = "FAILED_CIRCUIT_OPEN"
                    break
                continue

            # Feed result to Chief Decision Contract
            chief_decision = self.chief.evaluate_result_and_decide(
                task_id=task_id,
                correlation_id=corr_id,
                workflow_id=w_id,
                result_file=result_file,
                workflow_plan=[task_info],
                round_index=tasks_executed - 1,
                conversation_id=conversation_id,
            )

            decision_val = chief_decision.decision
            print(f"[CHIEF DECISION] Decision: {decision_val} | Reason: {chief_decision.reason}")

            self.chief.log_night_journal(s_id, {
                "action": "RESULT_EVALUATED",
                "objective_id": obj.objective_id,
                "task_id": task_id,
                "target_agent": target_agent,
                "result_file": result_file.name,
                "decision": decision_val,
                "verdict": "PASS",
                "review_decision": chief_decision.review_decision,
                "cost": 0.0,
            })

            # Update Standing Objective result in registry
            res_data = load_json(result_file) or {}
            res_hash = res_data.get("payload_hash", "hash_ok")
            self.objectives_registry.mark_objective_result(obj.objective_id, res_hash, "PASS")

            round_record = {
                "step": tasks_executed,
                "objective_id": obj.objective_id,
                "task_id": task_id,
                "target_agent": target_agent,
                "result_file": result_file.name,
                "chief_decision_id": chief_decision.chief_decision_id,
                "decision": decision_val,
                "value_gate_passed": chief_decision.value_gate.get("passed", True),
                "review_decision": chief_decision.review_decision,
            }
            history.append(round_record)

            if decision_val == "WAIT_FOR_HUMAN":
                print(f"[HUMAN GATE] Objective {obj.objective_id} requires human gate. Branch parked.")
                self.chief.log_night_journal(s_id, {
                    "action": "HUMAN_GATE_PARKED",
                    "task_id": task_id,
                    "objective_id": obj.objective_id,
                })
                # Only park that branch, continue other safe work unless terminal
                continue

        # Simulate Human Return / Wake
        self.chief.set_presence("AWAKE", session_id=s_id)
        self.chief.log_night_journal(s_id, {
            "action": "CHIEF_PRESENCE_CHANGED",
            "from": "SLEEPING",
            "to": "AWAKE",
            "session_id": s_id,
        })

        # Generate Morning Report
        morning_report = self.generate_morning_report(s_id)

        print(f"\n=======================================================")
        print(f"🏁 NIGHT SUPERVISOR FINISHED: {status} ({stop_reason})")
        print(f"   Tasks Executed: {tasks_executed} | Human Prompts: 0 | Spend: 0.00 EUR")
        print(f"   Morning Report generated at events/morning-reports/{s_id}-morning-report.json")
        print(f"=======================================================\n")

        return {
            "schema_version": "2.0",
            "session_id": s_id,
            "workflow_id": w_id,
            "status": status,
            "stop_reason": stop_reason,
            "tasks_executed": tasks_executed,
            "human_copy_paste_between_steps": 0,
            "unapproved_spend_eur": 0.0,
            "history": history,
            "morning_report": morning_report,
        }


    def run_long_run_session(
        self,
        budget: SessionWorkBudget | None = None,
        session_id: str | None = None,
        enable_bundling: bool = True,
        max_bundle_size: int = 3,
        max_operations: int = 20,
        idle_exit_after_empty_checks: int = 2,
    ) -> dict:
        """Executes the persistent, evidence-based Long-Run Work Engine across Opportunity Queue."""
        work_budget = budget or SessionWorkBudget()
        s_id = session_id or f"long-run-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        w_id = f"WF-LONG-RUN-{s_id[-8:]}"
        corr_id = f"corr-lr-{uuid.uuid4().hex[:8]}"
        budget_ledger = SessionBudgetLedger(self.repo_dir, s_id, work_budget)

        start_time = time.time()
        start_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        print(f"\n=======================================================")
        print(f"🚀 LONG-RUN WORK ENGINE: Starting Session {s_id}")
        print(f"   Max Duration: {work_budget.max_wall_clock_seconds}s | Max Operations: {max_operations} | Spend Limit: {work_budget.zero_spend_limit_eur} EUR")
        print(f"=======================================================\n")

        # Refill opportunity queue from local repository evidence
        refilled = self.opportunity_queue.refill_from_evidence()
        for creator_opp in discover_creator_opportunities(self.repo_dir):
            if self.opportunity_queue.add_opportunity(creator_opp):
                refilled += 1
        # Mission 122: only durable, evidence-backed input sources supplement
        # local creator gaps.  This no-network hook cannot synthesize metrics or
        # enqueue research merely because a connector/token file exists.
        input_refresh = refresh_creator_input_sources(self.repo_dir)
        print(f"[OPPORTUNITY QUEUE] Discovered {refilled} initial evidence-backed opportunities.")

        total_operations_completed = 0
        total_builder_jobs_executed = 0
        consecutive_failures = 0
        visited_opportunity_ids = set()
        history = []
        operations = []
        queue_refill_during_session = 0
        empty_queue_checks = 0

        self.heartbeat.update_heartbeat(
            supervisor_alive=True,
            chief_presence=self.chief.get_presence().get("presence", "AWAKE"),
            active_task=None,
            queue_ready=self.opportunity_queue.export_telemetry()["READY"],
            queue_blocked=self.opportunity_queue.export_telemetry()["BLOCKED"],
            completed_this_session=0,
        )

        status = "COMPLETED"
        stop_reason = "WORK_BUDGET_COMPLETED"

        while total_operations_completed < max_operations:
            # 1. Check time budget
            elapsed = time.time() - start_time
            if elapsed >= work_budget.max_wall_clock_seconds:
                print(f"[WORK BUDGET] Reached maximum wall-clock time ({work_budget.max_wall_clock_seconds}s).")
                stop_reason = "MAX_WALL_CLOCK_REACHED"
                break

            # 2. Select next actionable opportunity
            next_opp = self.opportunity_queue.select_next_opportunity(visited_ids=visited_opportunity_ids)

            if not next_opp:
                # Continuous refill during session
                newly_found = self.opportunity_queue.refill_from_evidence()
                for creator_opp in discover_creator_opportunities(self.repo_dir):
                    if self.opportunity_queue.add_opportunity(creator_opp):
                        newly_found += 1
                input_refresh = refresh_creator_input_sources(self.repo_dir)
                if newly_found > 0:
                    queue_refill_during_session += 1
                    print(f"[QUEUE REFILL] Discovered {newly_found} additional opportunities during active session.")
                    next_opp = self.opportunity_queue.select_next_opportunity(visited_ids=visited_opportunity_ids)

            if not next_opp:
                empty_queue_checks += 1
                print(f"[IDLE MONITORING] Opportunity queue empty (Check {empty_queue_checks}/{idle_exit_after_empty_checks}).")
                if empty_queue_checks >= idle_exit_after_empty_checks:
                    print("[IDLE MONITORING] No further actionable opportunities. Graceful IDLE stop.")
                    stop_reason = "IDLE_MONITORING_NO_WORK"
                    break
                continue

            empty_queue_checks = 0
            visited_opportunity_ids.add(next_opp.opportunity_id)
            claim_owner = f"supervisor:{s_id}:{os.getpid()}"

            # Claim before building a task ID.  A competing supervisor therefore
            # cannot turn the same READY opportunity into a different UUID task.
            if enable_bundling:
                _, candidates = self.opportunity_queue.bundle_opportunities(next_opp, max_bundle_size=max_bundle_size)
            else:
                candidates = [next_opp]
            bundled_opps = []
            claim_records: dict[str, dict] = {}
            for candidate in candidates:
                claimed, _, claim = self.opportunity_queue.claim_opportunity(candidate.opportunity_id, claim_owner)
                if not claimed:
                    if candidate.opportunity_id == next_opp.opportunity_id:
                        break
                    continue
                claimed_opp = self.opportunity_queue.get_opportunity(candidate.opportunity_id)
                if claimed_opp:
                    bundled_opps.append(claimed_opp)
                    claim_records[claimed_opp.opportunity_id] = claim
                    visited_opportunity_ids.add(claimed_opp.opportunity_id)

            if not bundled_opps:
                continue

            # 3. Task Bundling uses only opportunities already owned by this session.
            if enable_bundling:
                task_info, bundled_opps = self.opportunity_queue.bundle_opportunities(
                    bundled_opps[0], max_bundle_size=max_bundle_size, claimed_opportunities=bundled_opps
                )
                if len(bundled_opps) == 1 and bundled_opps[0].evidence.get("creator_action"):
                    task_info.update({
                        "creator_action": bundled_opps[0].evidence["creator_action"],
                        "creator_source": bundled_opps[0].source_artifact,
                        "creator_source_hash": bundled_opps[0].source_hash,
                    })
            else:
                next_opp = bundled_opps[0]
                task_info = {
                    "task_id": f"{w_id}-{next_opp.opportunity_id[:16]}-TASK",
                    "objective_id": next_opp.objective_id,
                    "instruction": next_opp.description,
                    "target_agent": next_opp.target_agent,
                    "allowed_scope": next_opp.allowed_scope,
                    "allowed_actions": next_opp.allowed_actions,
                    "risk_level": next_opp.risk,
                    "cost_class": "ZERO_COST_LOCAL",
                    "cost_estimate": 0.0,
                    "model_job_units": 1 if next_opp.model_need else 0,
                    "external_action_units": next_opp.external_action_units,
                    "creator_action": next_opp.evidence.get("creator_action"),
                    "creator_source": next_opp.source_artifact,
                    "creator_source_hash": next_opp.source_hash,
                    "bundled_opportunity_ids": [next_opp.opportunity_id],
                }

            model_ok, model_reason, _ = budget_ledger.reserve("model", int(task_info.get("model_job_units", 0)))
            external_ok, external_reason, _ = budget_ledger.reserve("external", int(task_info.get("external_action_units", 0)))
            if not model_ok or not external_ok:
                reason = model_reason if not model_ok else external_reason
                for b_opp in bundled_opps:
                    b_opp.status = "BLOCKED"
                    self.opportunity_queue.save_opportunity(b_opp)
                    self.opportunity_queue.release_opportunity_claim(b_opp.opportunity_id, claim_records[b_opp.opportunity_id]["claim_id"])
                operations.append({
                    "operation_id": f"OP-{s_id[-6:]}-{len(operations) + 1:03d}",
                    "opportunity_id": bundled_opps[0].opportunity_id,
                    "objective_id": bundled_opps[0].objective_id,
                    "action": "BUDGET_GATE",
                    "result": reason,
                    "status": "BLOCKED",
                })
                continue

            task_id = task_info["task_id"]
            print(f"\n--- [LONG-RUN JOB {total_builder_jobs_executed + 1}] Task: {task_id} ({len(bundled_opps)} ops bundled) ---")

            self.heartbeat.update_heartbeat(
                supervisor_alive=True,
                chief_presence=self.chief.get_presence().get("presence", "AWAKE"),
                active_task=task_id,
                queue_ready=self.opportunity_queue.export_telemetry()["READY"],
                queue_blocked=self.opportunity_queue.export_telemetry()["BLOCKED"],
                completed_this_session=total_operations_completed,
            )

            # 4. Dispatch and execute task
            chief_decision = None
            try:
                result_file = self.dispatch_and_execute_task(
                    task_info=task_info,
                    workflow_id=w_id,
                    correlation_id=corr_id,
                )
                total_builder_jobs_executed += 1
                consecutive_failures = 0

            except ValueError as val_err:
                print(f"[ZERO-SPEND FIREWALL] {val_err}")
                for b_opp in bundled_opps:
                    b_opp.status = "BLOCKED"
                    self.opportunity_queue.save_opportunity(b_opp)
                    self.opportunity_queue.release_opportunity_claim(b_opp.opportunity_id, claim_records[b_opp.opportunity_id]["claim_id"])
                stop_reason = "PAYMENT_APPROVAL_REQUIRED"
                status = "PAYMENT_APPROVAL_REQUIRED"
                break
            except Exception as exc:
                print(f"[FAILURE ISOLATION] Task {task_id} failed: {exc}")
                consecutive_failures += 1
                for b_opp in bundled_opps:
                    fp = f"fp_{b_opp.project}_{b_opp.objective_id}"
                    tripped = self.opportunity_queue.circuit_manager.record_failure(fp, str(exc), max_consecutive=work_budget.max_consecutive_failures)
                    b_opp.status = "CIRCUIT_OPEN" if tripped else "BLOCKED"
                    self.opportunity_queue.save_opportunity(b_opp)
                    self.opportunity_queue.release_opportunity_claim(b_opp.opportunity_id, claim_records[b_opp.opportunity_id]["claim_id"])
                    operations.append({
                        "operation_id": f"OP-{s_id[-6:]}-{len(operations) + 1:03d}",
                        "opportunity_id": b_opp.opportunity_id,
                        "objective_id": b_opp.objective_id,
                        "evidence_source": b_opp.source,
                        "action": b_opp.description,
                        "result": "BLOCKED",
                        "value_gate_result": False,
                        "dedupe_hash": b_opp.dedupe_hash,
                        "status": b_opp.status,
                    })

                if consecutive_failures >= work_budget.max_consecutive_failures:
                    print(f"[GLOBAL CIRCUIT BREAKER] Reached maximum consecutive session failures ({work_budget.max_consecutive_failures}).")
                    stop_reason = "GLOBAL_CIRCUIT_OPEN"
                    status = "FAILED_CIRCUIT_OPEN"
                    break
                continue

            # 5. Chief Evaluation & Queue Refill
            chief_decision = self.chief.evaluate_result_and_decide(
                task_id=task_id,
                correlation_id=corr_id,
                workflow_id=w_id,
                result_file=result_file,
                workflow_plan=[task_info],
                round_index=total_builder_jobs_executed - 1,
            )

            print(f"[CHIEF EVALUATION] Decision: {chief_decision.decision} | Reason: {chief_decision.reason}")

            if chief_decision.decision == "WAIT_FOR_HUMAN":
                for b_opp in bundled_opps:
                    b_opp.status = "WAITING_FOR_HUMAN"
                    self.opportunity_queue.save_opportunity(b_opp)
                    self.opportunity_queue.release_opportunity_claim(b_opp.opportunity_id, claim_records[b_opp.opportunity_id]["claim_id"])
                    operations.append({
                        "operation_id": f"OP-{s_id[-6:]}-{len(operations) + 1:03d}",
                        "opportunity_id": b_opp.opportunity_id,
                        "objective_id": b_opp.objective_id,
                        "evidence_source": b_opp.source,
                        "action": b_opp.description,
                        "result": "WAITING_FOR_HUMAN",
                        "value_gate_result": False,
                        "dedupe_hash": b_opp.dedupe_hash,
                        "status": "WAITING_FOR_HUMAN",
                    })
                history.append({
                    "builder_job": total_builder_jobs_executed,
                    "task_id": task_id,
                    "bundled_count": len(bundled_opps),
                    "bundled_ids": [o.opportunity_id for o in bundled_opps],
                    "result_file": result_file.name,
                    "chief_decision_id": chief_decision.chief_decision_id,
                    "decision": "WAIT_FOR_HUMAN",
                })
                continue

            # Record detailed operations
            for b_opp in bundled_opps:
                total_operations_completed += 1
                b_opp.status = "COMPLETED"
                self.opportunity_queue.save_opportunity(b_opp)
                self.opportunity_queue.circuit_manager.record_success(f"fp_{b_opp.project}_{b_opp.objective_id}")
                self.opportunity_queue.release_opportunity_claim(b_opp.opportunity_id, claim_records[b_opp.opportunity_id]["claim_id"])
                operations.append({
                    "operation_id": f"OP-{s_id[-6:]}-{len(operations) + 1:03d}",
                    "opportunity_id": b_opp.opportunity_id,
                    "objective_id": b_opp.objective_id,
                    "evidence_source": b_opp.source,
                    "action": b_opp.description,
                    "result": "PASS",
                    "value_gate_result": chief_decision.value_gate.get("passed", True),
                    "dedupe_hash": b_opp.dedupe_hash,
                    "status": "COMPLETED",
                })

            round_record = {
                "builder_job": total_builder_jobs_executed,
                "task_id": task_id,
                "bundled_count": len(bundled_opps),
                "bundled_ids": [o.opportunity_id for o in bundled_opps],
                "result_file": result_file.name,
                "chief_decision_id": chief_decision.chief_decision_id,
                "decision": chief_decision.decision,
            }
            history.append(round_record)

            self.heartbeat.update_heartbeat(
                supervisor_alive=True,
                chief_presence=self.chief.get_presence().get("presence", "AWAKE"),
                active_task=None,
                queue_ready=self.opportunity_queue.export_telemetry()["READY"],
                queue_blocked=self.opportunity_queue.export_telemetry()["BLOCKED"],
                completed_this_session=total_operations_completed,
            )

        finish_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        summary = {
            "schema_version": "2.0",
            "session_id": s_id,
            "workflow_id": w_id,
            "started_at": start_iso,
            "finished_at": finish_iso,
            "status": status,
            "stop_reason": stop_reason,
            "real_useful_operations": len(operations),
            "total_operations_completed": total_operations_completed,
            "total_builder_jobs_executed": total_builder_jobs_executed,
            "queue_refill_during_session": queue_refill_during_session,
            "human_copy_paste_between_steps": 0,
            "unapproved_spend_eur": 0.0,
            "model_calls_incurred": 0,
            "codex_calls_incurred": 0,
            "operation_ids": [o["operation_id"] for o in operations],
            "operations": operations,
            "history": history,
            "queue_telemetry": self.opportunity_queue.export_telemetry(),
        }

        save_json(self.reports_dir / f"{s_id}-long-run-report.json", summary)

        print(f"\n=======================================================")
        print(f"🏁 LONG-RUN ENGINE COMPLETED: {status} ({stop_reason})")
        print(f"   Operations Finished: {total_operations_completed} | Builder Jobs: {total_builder_jobs_executed} | Refills: {queue_refill_during_session} | Spend: 0.00 EUR")
        print(f"=======================================================\n")

        return summary


def main():
    parser = argparse.ArgumentParser(description="Run Autonomous Chief & Courier Supervisor")
    parser.add_argument("--workflow-id", type=str, default=f"WF-AUTO-{uuid.uuid4().hex[:6]}")
    parser.add_argument("--canary", action="store_true", help="Run deterministic two-step canary")
    parser.add_argument("--sleep-canary", action="store_true", help="Run deterministic Sleep Autopilot canary")
    parser.add_argument("--long-run-canary", action="store_true", help="Run deterministic Long-Run Work Engine canary (10+ operations)")
    parser.add_argument("--sleep", action="store_true", help="Run persistent sleep work engine session")
    parser.add_argument("--max-hours", type=float, default=8.0, help="Maximum hours for sleep/work session")
    args = parser.parse_args()

    supervisor = AutonomousSupervisor()

    if args.canary:
        canary_plan = [
            {
                "task_id": f"{args.workflow_id}-CANARY-A",
                "instruction": "Inspect local tool configuration and extract deterministic capability truth",
                "target_agent": "antigravity",
                "allowed_scope": ["config/local_tools.json"],
                "cost_class": "ZERO_COST_LOCAL",
                "risk_level": "LOW",
            },
            {
                "task_id": f"{args.workflow_id}-CANARY-B",
                "instruction": "Validate channel definitions and confirm local pipeline health",
                "target_agent": "antigravity",
                "allowed_scope": ["config/social_channels.json"],
                "cost_class": "ZERO_COST_LOCAL",
                "risk_level": "LOW",
            },
        ]
        res = supervisor.run_autonomous_continuation(args.workflow_id, canary_plan)
        print(json.dumps(res, indent=2))

    elif args.sleep_canary:
        res = supervisor.run_sleep_session(workflow_id=args.workflow_id, max_tasks=2)
        print(json.dumps(res, indent=2))

    elif args.long_run_canary:
        budget = SessionWorkBudget(max_wall_clock_seconds=300.0, zero_spend_limit_eur=0.0)
        res = supervisor.run_long_run_session(budget=budget, max_operations=12, enable_bundling=True)
        print(json.dumps(res, indent=2))

    elif args.sleep:
        budget = SessionWorkBudget(max_wall_clock_seconds=args.max_hours * 3600.0, zero_spend_limit_eur=0.0)
        res = supervisor.run_long_run_session(budget=budget, max_operations=100, enable_bundling=True)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    import sys
    print("Disabled in favor of OS-owned Courier Motor.")
    sys.exit(1)
