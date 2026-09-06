#!/usr/bin/env python3
"""Mission PRODUCT-5 — Autonomous Work Session Controller.

Coordinates multi-step, multi-branch autonomous execution sessions without
requiring manual user prompts.

Features:
1. End-to-end Session Lifecycle:
   STARTING -> RUNNING -> WAITING_RESULT -> WAITING_DEPENDENCY -> SAFE_IDLE ->
   WAITING_HUMAN / WAITING_MONEY / WAITING_PUBLICATION -> RECOVERING -> STOP_SUCCESS -> STOPPED.
2. Zero-Prompt Sequential Execution (A -> B -> C -> D -> E -> STOP_SUCCESS).
3. Multi-Branch Isolation: Gated branches (Human, Money, Pub) wait locally while safe branches continue.
4. Restart Continuity: Authoritative session state persisted to disk; no duplicated work.
5. Deterministic-first: 0 model calls during iteration, idle, snapshots, and reporting.
6. Integrates seamlessly with Product-3 Cockpit, Product-4 Discovery, Product-2C Queue,
   Product-3C Bridge, Product-4C Parallel Schemas, and Product-5C Message Stamps.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from autonomous_opportunity_discovery import (
        AutonomousOpportunityDiscoveryEngine,
        CanonicalOpportunity,
    )
except ImportError:
    from scripts.autonomous_opportunity_discovery import (
        AutonomousOpportunityDiscoveryEngine,
        CanonicalOpportunity,
    )


def load_json_safe(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def sha256_digest(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class SessionAccounting:
    useful_tasks_completed: int = 0
    valuable_state_transitions: int = 0
    branches_completed: int = 0
    branches_waiting: int = 0
    duplicates_avoided: int = 0
    model_calls_avoided: int = 0
    manual_intermediate_prompts: int = 0
    safe_idle_periods: int = 0
    human_gates_encountered: int = 0
    money_gates_encountered: int = 0
    publication_gates_encountered: int = 0
    recoveries_performed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AutonomousSessionState:
    session_id: str
    status: str = "STARTING"  # STARTING, RUNNING, WAITING_RESULT, WAITING_DEPENDENCY, SAFE_IDLE, WAITING_HUMAN, WAITING_MONEY, WAITING_PUBLICATION, RECOVERING, STOP_SUCCESS, STOPPED, FAILED_SYSTEMIC
    goal_set: list[str] = field(default_factory=list)
    active_branches: dict[str, Any] = field(default_factory=dict)
    waiting_branches: dict[str, Any] = field(default_factory=dict)
    completed_tasks: list[str] = field(default_factory=list)
    completed_fingerprints: list[str] = field(default_factory=list)
    human_gates: list[dict] = field(default_factory=list)
    money_gates: list[dict] = field(default_factory=list)
    publication_gates: list[dict] = field(default_factory=list)
    last_processed_event: str = ""
    last_useful_transition: str = ""
    next_wake_condition: str = "ON_NEW_EVIDENCE"
    stop_reason: Optional[str] = None
    pid: int = field(default_factory=os.getpid)
    started_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    accounting: SessionAccounting = field(default_factory=SessionAccounting)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["accounting"] = self.accounting.to_dict()
        return d


def is_pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class AutonomousWorkSessionController:
    """Authoritative session coordinator for continuous unattended autonomy."""

    def __init__(self, session_id: Optional[str] = None, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.events_dir = repo_dir / "events"
        self.autonomy_dir = self.events_dir / "autonomy-runtime"
        self.queue_dir = self.events_dir / "opportunity-queue"
        self.anomalies_dir = self.events_dir / "anomalies"
        self.autonomy_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.anomalies_dir.mkdir(parents=True, exist_ok=True)

        self.session_file = self.autonomy_dir / "session_controller_state.json"
        self.discovery_engine = AutonomousOpportunityDiscoveryEngine(repo_dir=self.repo_dir)

        # Restore from disk if exists, else initialize
        saved = load_json_safe(self.session_file)
        if saved and isinstance(saved, dict) and "session_id" in saved and (not session_id or saved["session_id"] == session_id):
            acc_data = saved.get("accounting", {})
            acc = SessionAccounting(**acc_data) if isinstance(acc_data, dict) else SessionAccounting()

            # Check liveness immediately on restore: RUNNING without fresh liveness is not live
            loaded_status = saved.get("status", "RUNNING")
            loaded_pid = saved.get("pid")
            is_live = False
            if loaded_pid and isinstance(loaded_pid, int) and is_pid_alive(loaded_pid):
                try:
                    up_time = datetime.datetime.fromisoformat(saved.get("updated_at", ""))
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    if (now_utc - up_time).total_seconds() < 900:
                        is_live = True
                except Exception:
                    is_live = False

            if loaded_status == "RUNNING" and not is_live:
                loaded_status = "STALE_RUNNING_OFFLINE"

            self.session = AutonomousSessionState(
                session_id=saved["session_id"],
                status=loaded_status,
                goal_set=saved.get("goal_set", []),
                active_branches=saved.get("active_branches", {}),
                waiting_branches=saved.get("waiting_branches", {}),
                completed_tasks=saved.get("completed_tasks", []),
                completed_fingerprints=saved.get("completed_fingerprints", []),
                human_gates=saved.get("human_gates", []),
                money_gates=saved.get("money_gates", []),
                publication_gates=saved.get("publication_gates", []),
                last_processed_event=saved.get("last_processed_event", ""),
                last_useful_transition=saved.get("last_useful_transition", ""),
                next_wake_condition=saved.get("next_wake_condition", "ON_NEW_EVIDENCE"),
                stop_reason=saved.get("stop_reason") or (f"PROCESS_INACTIVE_OR_TERMINATED_PID_{loaded_pid}" if loaded_status == "STALE_RUNNING_OFFLINE" else None),
                pid=loaded_pid if loaded_pid else os.getpid(),
                started_at=saved.get("started_at", ""),
                updated_at=saved.get("updated_at", ""),
                accounting=acc,
            )
            for tid in self.session.completed_tasks:
                self.discovery_engine.completed_signatures.add(tid)
            for fp in self.session.completed_fingerprints:
                self.discovery_engine.completed_signatures.add(fp)
            if loaded_status == "STALE_RUNNING_OFFLINE":
                self._save_session()
        else:
            sid = session_id or f"sess-auto-{uuid.uuid4().hex[:8]}"
            self.session = AutonomousSessionState(session_id=sid, pid=os.getpid())
            self._save_session()

    def reconcile_process_liveness(self) -> str:
        """Distinguishes persisted desire/state from authoritative live process."""
        recorded_pid = getattr(self.session, "pid", None)
        if self.session.status == "RUNNING":
            is_live = False
            if recorded_pid and isinstance(recorded_pid, int) and is_pid_alive(recorded_pid):
                try:
                    up_time = datetime.datetime.fromisoformat(self.session.updated_at)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    if (now_utc - up_time).total_seconds() < 900:
                        is_live = True
                except Exception:
                    is_live = False
            if not is_live:
                self.session.status = "STALE_RUNNING_OFFLINE"
                self.session.stop_reason = f"PROCESS_INACTIVE_OR_TERMINATED_PID_{recorded_pid}"
                self._save_session()
                return "STALE_RUNNING_OFFLINE"
        return self.session.status

    def _save_session(self) -> None:
        self.session.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save_json_atomic(self.session_file, self.session.to_dict())

    def start_session(self, initial_goals: Optional[list[str]] = None) -> AutonomousSessionState:
        """Starts or resumes an autonomous session."""
        if initial_goals:
            for g in initial_goals:
                if g not in self.session.goal_set:
                    self.session.goal_set.append(g)
        self.session.status = "RUNNING"
        self._save_session()
        return self.session

    def process_result(self, task_id: str, outcome: str, worker: str = "antigravity", branch: str = "MAIN") -> None:
        """Ingests a task result, unblocking dependencies and updating accounting."""
        self.session.last_processed_event = f"RESULT_{task_id}_{outcome}"

        if outcome == "SUCCESS":
            if task_id not in self.session.completed_tasks:
                self.session.completed_tasks.append(task_id)
                self.session.accounting.useful_tasks_completed += 1
                self.session.accounting.valuable_state_transitions += 1
                self.session.last_useful_transition = f"TASK_COMPLETED_{task_id}"

            self.discovery_engine.completed_signatures.add(task_id)
            if task_id in self.session.active_branches:
                del self.session.active_branches[task_id]

            # Ingest into discovery engine to unblock subsequent items
            self.discovery_engine.discover_opportunities(new_result={"task_id": task_id, "outcome": "SUCCESS"})

        elif outcome == "FAIL":
            if task_id in self.session.active_branches:
                del self.session.active_branches[task_id]
            # Record failed branch
            self.session.waiting_branches[task_id] = {"status": "FAILED", "worker": worker, "branch": branch}

        self._save_session()

    def run_next_step(
        self,
        active_goals: Optional[list[dict]] = None,
        open_loops: Optional[list[dict]] = None,
        sequenced_chains: Optional[list[dict]] = None,
    ) -> tuple[str, list[dict]]:
        """Executes one deterministic loop iteration."""
        if self.session.status in ("STOP_SUCCESS", "STOPPED", "FAILED_SYSTEMIC"):
            return self.session.status, []

        # 1. Check for systemic anomalies
        anom_file = self.anomalies_dir / "anomaly_ledger.json"
        anom_map = load_json_safe(anom_file, {})
        has_systemic_anomaly = any(
            v.get("severity") == "CRITICAL" and not v.get("resolved", False) and v.get("affected_scope") == "SYSTEMIC"
            for v in anom_map.values()
        )
        if has_systemic_anomaly:
            self.session.status = "FAILED_SYSTEMIC"
            self.session.stop_reason = "CRITICAL_SYSTEMIC_ANOMALY"
            self._save_session()
            return "FAILED_SYSTEMIC", []

        # 2. Discover new candidate opportunities
        new_opps = self.discovery_engine.discover_opportunities(
            active_goals=active_goals,
            open_loops=open_loops,
            sequenced_chains=sequenced_chains,
        )

        # 3. Categorize all pending opportunities in queue
        all_ready_candidates: list[CanonicalOpportunity] = []
        human_gated_items: list[CanonicalOpportunity] = []
        money_gated_items: list[CanonicalOpportunity] = []
        pub_gated_items: list[CanonicalOpportunity] = []

        for opp in self.discovery_engine.discovered_opportunities.values():
            if opp.status == "DONE" or opp.dedupe_hash in self.session.completed_fingerprints or opp.opportunity_id in self.session.completed_tasks:
                continue

            # Respect message completion stamps (Codex Product-5C)
            if opp.message_stamp:
                stamp_st = opp.message_stamp.get("status")
                if stamp_st == "DONE":
                    continue
                if stamp_st == "CLAIMED":
                    self.session.accounting.duplicates_avoided += 1
                    continue

            if opp.status == "READY":
                all_ready_candidates.append(opp)
            elif opp.status == "HUMAN_GATE":
                human_gated_items.append(opp)
            elif opp.status == "MONEY_GATE":
                money_gated_items.append(opp)
            elif opp.status == "PUBLICATION_GATE":
                pub_gated_items.append(opp)

        # Update gate records
        self.session.human_gates = [{"task_id": o.opportunity_id, "desc": o.description} for o in human_gated_items]
        self.session.money_gates = [{"task_id": o.opportunity_id, "desc": o.description, "cost": o.estimated_cost} for o in money_gated_items]
        self.session.publication_gates = [{"task_id": o.opportunity_id, "desc": o.description} for o in pub_gated_items]

        if human_gated_items:
            self.session.accounting.human_gates_encountered = len(human_gated_items)
        if money_gated_items:
            self.session.accounting.money_gates_encountered = len(money_gated_items)
        if pub_gated_items:
            self.session.accounting.publication_gates_encountered = len(pub_gated_items)

        # 4. Dispatch eligible READY work
        dispatched_this_round: list[dict] = []
        if all_ready_candidates:
            # Sort by priority descending
            all_ready_candidates.sort(key=lambda o: o.priority, reverse=True)
            for candidate in all_ready_candidates:
                # Mark ACTIVE in session
                self.session.active_branches[candidate.opportunity_id] = {
                    "task_id": candidate.opportunity_id,
                    "description": candidate.description,
                    "provider": candidate.provider,
                    "target_agent": candidate.target_agent,
                    "dispatched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                dispatched_this_round.append(candidate.to_dict())

            self.session.status = "RUNNING"
            self.session.accounting.model_calls_avoided += len(dispatched_this_round)

        elif self.session.active_branches:
            self.session.status = "WAITING_RESULT"

        else:
            # Check if all sequenced chains / goals are complete
            all_chains_complete = True
            if sequenced_chains:
                for ch in sequenced_chains:
                    steps = ch.get("steps", [])
                    if not all(s.get("step_id") in self.session.completed_tasks for s in steps):
                        all_chains_complete = False
                        break

            if sequenced_chains and all_chains_complete:
                self.session.status = "STOP_SUCCESS"
                self.session.stop_reason = "ALL_GOALS_COMPLETED"
            elif human_gated_items and not money_gated_items and not pub_gated_items:
                self.session.status = "WAITING_HUMAN"
            elif money_gated_items and not human_gated_items:
                self.session.status = "WAITING_MONEY"
            elif pub_gated_items:
                self.session.status = "WAITING_PUBLICATION"
            elif human_gated_items or money_gated_items:
                self.session.status = "WAITING_HUMAN"
            else:
                self.session.status = "SAFE_IDLE"
                self.session.accounting.safe_idle_periods += 1

        self._save_session()
        return self.session.status, dispatched_this_round

    def get_cockpit_snapshot(self) -> dict[str, Any]:
        """Returns read-only session snapshot for Product-3 Cockpit without LLM calls."""
        return {
            "session_id": self.session.session_id,
            "status": self.session.status,
            "goal_set": self.session.goal_set,
            "active_branches": list(self.session.active_branches.values()),
            "waiting_branches": self.session.waiting_branches,
            "completed_count": len(self.session.completed_tasks),
            "last_useful_result": self.session.last_useful_transition or "None",
            "next_wake_condition": self.session.next_wake_condition,
            "human_gates": self.session.human_gates,
            "money_gates": self.session.money_gates,
            "publication_gates": self.session.publication_gates,
            "stop_reason": self.session.stop_reason,
            "accounting": self.session.accounting.to_dict(),
            "model_calls": 0,
        }

    def generate_end_session_report(self) -> dict[str, Any]:
        """Generates structured session report without LLM calls."""
        return {
            "session_id": self.session.session_id,
            "final_status": self.session.status,
            "stop_reason": self.session.stop_reason or "SAFE_IDLE_REACHED",
            "tasks_completed": self.session.completed_tasks,
            "active_at_end": list(self.session.active_branches.keys()),
            "human_gates_pending": self.session.human_gates,
            "money_gates_pending": self.session.money_gates,
            "publication_gates_pending": self.session.publication_gates,
            "accounting": self.session.accounting.to_dict(),
            "recommended_next_action": "Resume unattended session when new evidence arrives or human approves pending gate",
            "model_calls": 0,
        }
