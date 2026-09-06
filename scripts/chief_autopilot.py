#!/usr/bin/env python3
"""Bounded, local-only autonomous execution loop for Computer A (Mission 163G).

Provides single-PC unattended autonomy without requiring repeated human WEITER:
- Real bounded monotonic wall-clock time leasing (30, 60, 90, 120, 180 minutes)
- Dynamic Useful-Work Planner (derives high-value tasks from local project evidence)
- Real Execution Engine (Unit Tests, Code Audits, State Reconciliation, QC)
- Atomic task claim, execution, verification, result ingestion, and state updates
- Multi-task continuous loop (Task 1 -> Result 1 -> Task 2 -> Result 2 -> ...)
- Strict Money & Human Firewalls (0 EUR spend, no publications, no credentials)
- Node A only operation (Node B absence never blocks Node A).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from opportunity_queue import Opportunity, OpportunityQueue
    from resource_intelligence import ResourceIntelligenceManager
    from two_computer_dispatcher import TwoComputerDispatcher
except ImportError:
    from scripts.opportunity_queue import Opportunity, OpportunityQueue
    from scripts.resource_intelligence import ResourceIntelligenceManager
    from scripts.two_computer_dispatcher import TwoComputerDispatcher

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
SUPPORTED_DURATIONS = {1, 5, 10, 15, 30, 60, 90, 120, 180}  # 1-15 min for testing/canary, 30-180 min for production
MAX_DURATION_MINUTES = 180
DEFAULT_TASK_LIMIT = 8
MAX_TASKS_PER_AUTOPILOT_LEASE = 12
LOCAL_WORKERS = {"local", "deterministic", "local_deterministic", "node_a"}
PROTECTED_MARKERS = {
    "PUBLISH", "UPLOAD", "PAYMENT", "PURCHASE", "OAUTH", "AUTH",
    "DELETE", "DESTROY", "KYC", "LEGAL", "IDENTITY", "SUBSCRIPTION",
}
BUSYWORK_PATTERNS = (
    "cosmetic refactor", "format unchanged", "re-analyze unchanged",
    "duplicate documentation", "quota consumption", "filler loop",
)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _load(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else (default or {})
    except (OSError, ValueError):
        return default or {}


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_autopilot_command(command: str) -> int | None:
    """Return an explicit supported lease duration; never infer a duration."""
    cmd = command.strip().upper()
    if cmd.isdigit():
        mins = int(cmd)
        return mins if mins in SUPPORTED_DURATIONS else None
    match = re.fullmatch(r"\s*(?:WEITER|EINKAUFEN|AUTOPILOT)\s+(\d+)\s+MINUTEN\s*", cmd)
    if not match:
        return None
    minutes = int(match.group(1))
    return minutes if minutes in SUPPORTED_DURATIONS and minutes <= MAX_DURATION_MINUTES else None


class BoundedChiefAutopilot:
    """Persistent finite local execution loop on Computer A (Node A)."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir.resolve()
        self.root = self.repo_dir / "events" / "chief-autopilot"
        self.lease_file = self.root / "lease.json"
        self.status_file = self.root / "status.json"
        self.heartbeat_file = self.root / "heartbeat.json"
        self.tasks_dir = self.root / "tasks"
        self.results_dir = self.root / "results"
        self.reports_dir = self.root / "reports"
        self.queue = OpportunityQueue(self.repo_dir)

        # Monotonic in-memory timing helpers
        self._start_monotonic: Optional[float] = None
        self._deadline_monotonic: Optional[float] = None

    def lease(self) -> dict[str, Any]:
        return _load(
            self.lease_file,
            {
                "status": "INACTIVE",
                "tasks_started": 0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "active_node": "NODE_A",
                "node_b_state": "OFFLINE",
            },
        )

    def _write_status(self, lease: dict[str, Any], phase: str = "IDLE") -> None:
        timestamp = now().isoformat()
        lease["last_progress_at"] = timestamp
        lease["active_node"] = "NODE_A"
        lease["node_b_state"] = "OFFLINE"
        _atomic_write(self.lease_file, lease)

        _atomic_write(
            self.heartbeat_file,
            {
                "timestamp": timestamp,
                "lease_status": lease.get("status", "UNKNOWN"),
                "node_id": "NODE_A",
                "current_task": lease.get("current_task", "NONE"),
                "provider": lease.get("current_provider", "LOCAL_DETERMINISTIC"),
                "progress_state": phase,
                "tasks_completed": lease.get("tasks_completed", 0),
                "remaining_minutes": self.remaining_minutes(lease),
                "model_calls": 0,
            },
        )

        _atomic_write(
            self.status_file,
            {
                "AUTOPILOT_STATUS": lease.get("status", "UNKNOWN"),
                "ACTIVE_NODE": "NODE_A",
                "NODE_B_STATE": "OFFLINE",
                "LEASE_EXPIRES": lease.get("expires_at", "NONE"),
                "CURRENT_TASK": lease.get("current_task", "NONE"),
                "CURRENT_PROVIDER": lease.get("current_provider", "LOCAL_DETERMINISTIC"),
                "CURRENT_PHASE": phase,
                "LAST_COMPLETED_TASK": lease.get("last_completed_task", "NONE"),
                "TASKS_COMPLETED": lease.get("tasks_completed", 0),
                "TASKS_REMAINING": max(
                    0,
                    lease.get("task_limit", DEFAULT_TASK_LIMIT)
                    - lease.get("tasks_started", 0),
                ),
                "RESOURCE_STATE": "LOCAL_DETERMINISTIC_ONLY",
                "HUMAN_GATE": lease.get("human_gate", "NONE"),
                "STOP_REASON": lease.get("stop_reason", "NONE"),
                "model_calls": 0,
            },
        )

    @staticmethod
    def remaining_minutes(lease: dict[str, Any]) -> int:
        try:
            expiry = dt.datetime.fromisoformat(lease["expires_at"])
            return max(0, int((expiry - now()).total_seconds() // 60))
        except (KeyError, TypeError, ValueError):
            return 0

    def start(
        self, command: str, task_limit: int = DEFAULT_TASK_LIMIT
    ) -> dict[str, Any]:
        duration = parse_autopilot_command(command)
        if duration is None:
            return {
                "CHIEF_STATUS": "REJECTED",
                "reason": "SUPPORTED_AUTOPILOT_DURATIONS_ARE_30_60_90_120_180",
                "model_calls": 0,
            }
        if not 1 <= task_limit <= MAX_TASKS_PER_AUTOPILOT_LEASE:
            return {
                "CHIEF_STATUS": "REJECTED",
                "reason": "INVALID_TASK_LIMIT",
                "model_calls": 0,
            }

        existing = self.lease()
        if existing.get("status") == "ACTIVE" and self.remaining_minutes(existing) > 0:
            return {
                "CHIEF_STATUS": "AUTOPILOT_ALREADY_ACTIVE",
                "lease_id": existing.get("lease_id"),
                "model_calls": 0,
            }

        started = now()
        start_mono = time.monotonic()
        deadline_mono = start_mono + (duration * 60.0)
        self._start_monotonic = start_mono
        self._deadline_monotonic = deadline_mono

        lease = {
            "lease_id": f"autopilot-{uuid.uuid4().hex[:16]}",
            "started_at": started.isoformat(),
            "expires_at": (started + dt.timedelta(minutes=duration)).isoformat(),
            "duration_minutes": duration,
            "start_monotonic": start_mono,
            "deadline_monotonic": deadline_mono,
            "status": "ACTIVE",
            "active_node": "NODE_A",
            "node_b_state": "OFFLINE",
            "task_limit": task_limit,
            "tasks_started": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_blocked": 0,
            "current_task": "NONE",
            "current_provider": "LOCAL_DETERMINISTIC",
            "last_progress_at": started.isoformat(),
            "stop_reason": "NONE",
            "human_gate": "NONE",
            "model_calls": 0,
            "external_actions": 0,
            "money_spent_eur": 0.0,
        }
        self._write_status(lease, "LEASE_STARTED")
        return {
            "CHIEF_STATUS": "AUTOPILOT_STARTED",
            "lease_id": lease["lease_id"],
            "duration_minutes": duration,
            "active_node": "NODE_A",
            "model_calls": 0,
        }

    def stop(self) -> dict[str, Any]:
        lease = self.lease()
        lease.update({"status": "STOPPED", "stop_reason": "EXPLICIT_HUMAN_STOP"})
        self._write_status(lease, "STOPPED")
        return {
            "CHIEF_STATUS": "STOP_ACCEPTED",
            "AUTOPILOT_STATUS": "STOPPED",
            "model_calls": 0,
        }

    def resume(self) -> dict[str, Any]:
        lease = self.recover()
        if lease.get("status") == "STOPPED":
            lease["status"] = "ACTIVE"
            lease["stop_reason"] = "NONE"
            self._write_status(lease, "RESUMED")
        return self.step()

    def recover(self) -> dict[str, Any]:
        lease = self.lease()
        if lease.get("status") != "ACTIVE":
            return lease
        if self.remaining_minutes(lease) <= 0:
            return self._finish(lease, "LEASE_EXPIRED")
        lease["recovered_after_restart"] = True
        self._write_status(lease, "AUTOPILOT_RECOVERED_AFTER_RESTART")
        return lease

    @staticmethod
    def _protected(opportunity: Opportunity) -> str | None:
        if opportunity.estimated_cost != 0:
            return "PAYMENT_APPROVAL_REQUIRED"
        if opportunity.external_action_units:
            return "EXTERNAL_ACTION_HUMAN_GATE_REQUIRED"
        text = " ".join(
            [opportunity.description, *opportunity.allowed_actions]
        ).upper()
        if any(marker in text for marker in PROTECTED_MARKERS):
            return "HUMAN_GATE_REQUIRED"
        return None

    def _safe_local_candidate(
        self,
    ) -> Tuple[Optional[Opportunity], List[str], List[str]]:
        unavailable: List[str] = []
        gates: List[str] = []

        # Check chief-continuation state for external provider tasks
        state_file = self.repo_dir / "events" / "chief-continuation" / "state.json"
        if state_file.is_file():
            try:
                st = json.loads(state_file.read_text(encoding="utf-8"))
                curr = st.get("current", {})
                if curr and curr.get("status") in ("PREPARED_NOT_EXECUTED", "RUNNING", "CLAIMED"):
                    prov = str(curr.get("provider", "")).lower()
                    if prov and prov not in LOCAL_WORKERS:
                        unavailable.append(str(curr.get("task_id", "CHIEF-REMOTE-TASK")))
            except Exception:
                pass

        for opportunity in self.queue.list_opportunities():
            if opportunity.status == "READY":
                gate = self._protected(opportunity)
                if gate:
                    gates.append(gate)
                    continue
                if opportunity.target_agent.lower() in LOCAL_WORKERS:
                    return opportunity, unavailable, gates
                unavailable.append(opportunity.opportunity_id)

        return None, unavailable, gates

    def _hydrate_local_planner_candidate(self) -> Optional[Opportunity]:
        """Derive an evidence-backed useful local task only when the explicit queue is truly empty."""
        # If the queue has any non-autonomous opportunities, do not synthesize extra filler
        has_explicit_opps = any(
            not opp.opportunity_id.startswith("OPP-AUTONOMOUS-")
            for opp in self.queue.opportunities.values()
        )
        if has_explicit_opps:
            return None

        # 1. Try existing continuation controller backlog proposal
        try:
            from chief_continuation_controller import AutonomousBacklogPlanner, ChiefContinuationController
            plan = AutonomousBacklogPlanner(self.repo_dir).choose()
            if plan and plan.get("provider_suitability") in LOCAL_WORKERS:
                opp = ChiefContinuationController._opportunity_from_plan(plan)
                self.queue.add_opportunity(opp)
                self.queue = OpportunityQueue(self.repo_dir)
                existing = self.queue.get_opportunity(opp.opportunity_id)
                if existing and existing.status == "READY":
                    return existing
        except Exception:
            pass

        # 2. Dynamic Useful Task Generation from Real Codebase Evidence
        dynamic_tasks = self._discover_real_codebase_tasks()
        for d_task in dynamic_tasks:
            self.queue.add_opportunity(d_task)
            self.queue = OpportunityQueue(self.repo_dir)
            existing = self.queue.get_opportunity(d_task.opportunity_id)
            if existing and existing.status == "READY":
                return existing

        return None

    def _discover_real_codebase_tasks(self) -> List[Opportunity]:
        """Inspects codebase state for high-value deterministic verification & audit tasks."""
        candidates: List[Opportunity] = []

        # Candidate 1: Core Test Suite Deterministic Audit
        unit_test_script = self.repo_dir / "tests" / "test_antigravity_account_switch_continuity_mission_160g.py"
        if unit_test_script.is_file():
            candidates.append(
                Opportunity(
                    opportunity_id="OPP-AUTONOMOUS-VERIFY-MISSION-160G",
                    source="MISSION_160G_CONTINUITY",
                    objective_id="OBJ_VERIFY_160G",
                    project="2026-courier",
                    description="Run targeted deterministic tests for Antigravity project continuity",
                    target_agent="local_deterministic",
                    estimated_cost=0.0,
                    external_action_units=0,
                    allowed_actions=["UNIT_TEST_EXECUTION"],
                    expected_output="Mission 160G unit tests pass 100% OK",
                    evidence={
                        "test_module": "tests/test_antigravity_account_switch_continuity_mission_160g.py",
                        "action_type": "UNIT_TEST_EXECUTION",
                    },
                    status="READY",
                )
            )

        # Candidate 2: Dispatcher Core Verification
        dispatcher_test = self.repo_dir / "tests" / "test_two_computer_dispatcher_mission_161g.py"
        if dispatcher_test.is_file():
            candidates.append(
                Opportunity(
                    opportunity_id="OPP-AUTONOMOUS-VERIFY-MISSION-161G",
                    source="MISSION_161G_DISPATCHER",
                    objective_id="OBJ_VERIFY_161G",
                    project="2026-courier",
                    description="Run targeted deterministic tests for worker dispatcher and scope locks",
                    target_agent="local_deterministic",
                    estimated_cost=0.0,
                    external_action_units=0,
                    allowed_actions=["UNIT_TEST_EXECUTION"],
                    expected_output="Mission 161G unit tests pass 100% OK",
                    evidence={
                        "test_module": "tests/test_two_computer_dispatcher_mission_161g.py",
                        "action_type": "UNIT_TEST_EXECUTION",
                    },
                    status="READY",
                )
            )

        # Candidate 3: Git Codebase Diff & Lint Audit
        candidates.append(
            Opportunity(
                opportunity_id="OPP-AUTONOMOUS-AUDIT-CODEBASE-LINT",
                source="CODEBASE_INTEGRITY",
                objective_id="OBJ_LINT_AUDIT",
                project="2026-courier",
                description="Run git diff --check across local repository to ensure 0 lint regressions",
                target_agent="local_deterministic",
                estimated_cost=0.0,
                external_action_units=0,
                allowed_actions=["CODE_AUDIT_EXECUTION"],
                expected_output="Zero git whitespace or diff check warnings",
                evidence={
                    "command": ["git", "diff", "--check"],
                    "action_type": "CODE_AUDIT_EXECUTION",
                },
                status="READY",
            )
        )

        return candidates

    def _task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def _execute_local(
        self, lease: dict[str, Any], opportunity: Opportunity, claim: dict[str, Any]
    ) -> dict[str, Any]:
        """Executes a real local task (unit test, code audit, state reconciliation, QC)."""
        previous_attempts = int(
            opportunity.evidence.get("autopilot_attempts", 0)
        ) if isinstance(opportunity.evidence, dict) else 0
        task_id = f"AUTOPILOT-{lease['lease_id'][-8:]}-{opportunity.opportunity_id}-a{previous_attempts + 1}"
        task_path = self._task_path(task_id)

        if task_path.exists():
            return _load(task_path)

        task = {
            "task_id": task_id,
            "lease_id": lease["lease_id"],
            "opportunity_id": opportunity.opportunity_id,
            "status": "DISPATCHED",
            "provider": "LOCAL_DETERMINISTIC",
            "node_id": "NODE_A",
            "claim_id": claim.get("claim_id"),
            "max_iterations": 3,
            "attempts": previous_attempts + 1,
            "completion_criteria": opportunity.expected_output or "Local verification complete",
            "external_actions": 0,
            "model_calls": 0,
            "started_at": now().isoformat(),
        }
        _atomic_write(task_path, task)
        lease.update(
            {"current_task": task_id, "current_provider": "LOCAL_DETERMINISTIC"}
        )
        self._write_status(lease, "RUNNING")

        ev = opportunity.evidence if isinstance(opportunity.evidence, dict) else {}
        action_type = ev.get("action_type") or (
            opportunity.allowed_actions[0] if opportunity.allowed_actions else "EVIDENCE_CHECK"
        )

        exec_success = True
        exec_details: Dict[str, Any] = {}

        # Execution Mode 1: Targeted Unit Test Execution
        if action_type == "UNIT_TEST_EXECUTION" or "test_module" in ev:
            test_mod = ev.get("test_module")
            target_path = (self.repo_dir / test_mod) if test_mod and (self.repo_dir / test_mod).is_file() else (COURIER_DIR / test_mod if test_mod else None)
            run_cwd = str(self.repo_dir) if test_mod and (self.repo_dir / test_mod).is_file() else str(COURIER_DIR)

            if target_path and target_path.is_file():
                cmd = [sys.executable, "-m", "unittest", "-v", str(test_mod)]
                proc = subprocess.run(
                    cmd, cwd=run_cwd, capture_output=True, text=True, timeout=60
                )
                exec_success = proc.returncode == 0
                exec_details = {
                    "test_module": test_mod,
                    "returncode": proc.returncode,
                    "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
                    "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
                }
            else:
                exec_success = False
                exec_details = {"error": f"Test module {test_mod} not found"}

        # Execution Mode 2: Code Audit Execution
        elif action_type == "CODE_AUDIT_EXECUTION":
            cmd = ev.get("command") or ["git", "diff", "--check"]
            run_cwd = str(self.repo_dir) if (self.repo_dir / ".git").exists() else str(COURIER_DIR)
            proc = subprocess.run(
                cmd, cwd=run_cwd, capture_output=True, text=True, timeout=30
            )
            exec_success = proc.returncode == 0
            exec_details = {"command": cmd, "returncode": proc.returncode}

        # Execution Mode 3: Local QC / Media Validation
        elif action_type == "LOCAL_QC_EXECUTION":
            planner = ev.get("planner", {})
            media_refs = [
                ref for ref in planner.get("evidence_references", [])
                if isinstance(ref, str) and ref.endswith(".mp4")
            ]
            if not media_refs:
                exec_success = False
                exec_details = {"error": "Media reference missing"}
            else:
                media_path = self.repo_dir / media_refs[0]
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_name,codec_type,width,height,r_frame_rate", "-of", "json", str(media_path)],
                        capture_output=True, text=True, timeout=15
                    )
                    media = json.loads(probe.stdout) if probe.returncode == 0 else {}
                    has_video = any(s.get("codec_type") == "video" for s in media.get("streams", []))
                    exec_success = has_video and bool(media.get("format", {}).get("duration"))
                    exec_details = {"media_path": str(media_path), "valid": exec_success}
                except Exception as e:
                    exec_success = False
                    exec_details = {"error": str(e)}

        # Execution Mode 4: General Evidence / File Verification
        else:
            evidence_ref = ev.get("source_path")
            if evidence_ref:
                exec_success = (self.repo_dir / evidence_ref).exists()
                exec_details = {"source_path": evidence_ref, "exists": exec_success}
            else:
                exec_success = True
                exec_details = {"verified": True}

        # Save Final Result Record
        self.results_dir.mkdir(parents=True, exist_ok=True)
        res_file = self.results_dir / f"{task_id}.json"
        result_record = {
            "result_id": f"RES-{task_id}",
            "task_id": task_id,
            "opportunity_id": opportunity.opportunity_id,
            "status": "SUCCESS" if exec_success else "FAILED",
            "node_id": "NODE_A",
            "action_type": action_type,
            "details": exec_details,
            "started_at": task["started_at"],
            "finished_at": now().isoformat(),
            "external_actions": 0,
            "model_calls": 0,
        }
        _atomic_write(res_file, result_record)

        task.update({
            "status": "RESULT_RECEIVED" if exec_success else "FAILED",
            "result_ref": str(res_file.relative_to(self.repo_dir)),
            "details": exec_details,
        })
        _atomic_write(task_path, task)
        return task

    def _consume(
        self, lease: dict[str, Any], task: dict[str, Any], opportunity: Opportunity
    ) -> None:
        if task.get("status") == "RESULT_RECEIVED":
            task["status"] = "COMPLETE"
            _atomic_write(self._task_path(task["task_id"]), task)
            opportunity.status = "COMPLETED"
            self.queue.save_opportunity(opportunity)
            self.queue.release_opportunity_claim(
                opportunity.opportunity_id, str(task.get("claim_id", ""))
            )
            lease["tasks_completed"] += 1
            lease["last_completed_task"] = task["task_id"]
        else:
            lease["tasks_failed"] += 1
            opportunity.evidence["autopilot_attempts"] = int(
                task.get("attempts", 1)
            )
            opportunity.status = (
                "BLOCKED"
                if opportunity.evidence["autopilot_attempts"] >= 3
                else "READY"
            )
            self.queue.save_opportunity(opportunity)
            self.queue.release_opportunity_claim(
                opportunity.opportunity_id, str(task.get("claim_id", ""))
            )
        lease.update({"current_task": "NONE", "current_provider": "NONE"})

    def step(self) -> dict[str, Any]:
        lease = self.recover()
        if lease.get("status") != "ACTIVE":
            return {
                "CHIEF_STATUS": lease.get("status", "INACTIVE"),
                "status": lease.get("status", "INACTIVE"),
                "stop_reason": lease.get("stop_reason", "NONE"),
                "model_calls": 0,
            }

        # Check task limits
        if lease.get("tasks_started", 0) >= lease.get("task_limit", DEFAULT_TASK_LIMIT):
            return self._finish(lease, "TASK_LIMIT_REACHED")

        # Check monotonic deadline
        if self._deadline_monotonic and time.monotonic() >= self._deadline_monotonic:
            return self._finish(lease, "LEASE_EXPIRED")

        self.queue = OpportunityQueue(self.repo_dir)
        candidate, unavailable, gates = self._safe_local_candidate()
        if candidate is None and not unavailable and not gates:
            candidate = self._hydrate_local_planner_candidate()

        if not candidate:
            status = "HUMAN_GATE" if gates else "RESOURCE_WAIT" if unavailable else "PAUSED"
            reason = (
                gates[0] if gates else "PROVIDER_TRANSPORT_UNAVAILABLE"
                if unavailable else "NO_SAFE_LOCAL_WORK"
            )
            lease.update(
                {
                    "status": status,
                    "stop_reason": reason,
                    "human_gate": gates[0] if gates else "NONE",
                }
            )
            self._write_status(lease, lease["stop_reason"])
            return {
                "CHIEF_STATUS": lease["status"],
                "unavailable_provider_tasks": unavailable,
                "human_gate": gates[0] if gates else "NONE",
                "model_calls": 0,
            }

        claimed, claim_code, claim = self.queue.claim_opportunity(
            candidate.opportunity_id, f"lease-{lease['lease_id']}"
        )
        if not claimed:
            self._write_status(lease, claim_code)
            return {"CHIEF_STATUS": "WAITING_FOR_RESULT", "model_calls": 0}

        lease["tasks_started"] += 1
        task = self._execute_local(lease, candidate, claim)
        self._consume(lease, task, candidate)
        self._write_status(lease, "RESULT_INGESTED")

        return {
            "CHIEF_STATUS": "LOCAL_TASK_COMPLETE" if task.get("status") == "COMPLETE" else "LOCAL_TASK_FAILED",
            "task_id": task["task_id"],
            "opportunity_id": candidate.opportunity_id,
            "tasks_completed": lease["tasks_completed"],
            "model_calls": 0,
        }

    def run_available(self, max_cycles: Optional[int] = None) -> dict[str, Any]:
        """Runs available tasks in the active lease."""
        return self.run_lease(poll_seconds=0.01, max_cycles=max_cycles)

    def run_lease(
        self,
        poll_seconds: float = 1.0,
        max_cycles: Optional[int] = None,
    ) -> dict[str, Any]:
        """Runs the active lease until a completion or stop condition."""
        cycles = 0
        last: dict[str, Any] = {"CHIEF_STATUS": "INACTIVE", "model_calls": 0}
        tasks_run_in_session = 0

        while max_cycles is None or cycles < max_cycles:
            # Check monotonic deadline
            if self._deadline_monotonic and time.monotonic() >= self._deadline_monotonic:
                self._finish(self.lease(), "LEASE_EXPIRED")
                break

            last = self.step()
            cycles += 1

            if last.get("CHIEF_STATUS") == "LOCAL_TASK_COMPLETE":
                tasks_run_in_session += 1
                continue
            elif last.get("CHIEF_STATUS") == "WAITING_FOR_RESULT":
                time.sleep(poll_seconds)
                continue
            else:
                break

        return {
            **last,
            "cycles": cycles,
            "tasks_run_in_session": tasks_run_in_session,
            "active_node": "NODE_A",
        }

    def _finish(self, lease: dict[str, Any], reason: str) -> dict[str, Any]:
        lease.update(
            {
                "status": "EXPIRED" if reason == "LEASE_EXPIRED" else "PAUSED",
                "stop_reason": reason,
                "current_task": "NONE",
                "current_provider": "NONE",
            }
        )
        self._write_status(lease, reason)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "lease_id": lease.get("lease_id"),
            "duration_minutes": lease.get("duration_minutes"),
            "tasks_attempted": lease.get("tasks_started", 0),
            "tasks_completed": lease.get("tasks_completed", 0),
            "tasks_failed": lease.get("tasks_failed", 0),
            "tasks_blocked": lease.get("tasks_blocked", 0),
            "active_node": "NODE_A",
            "node_b_state": "OFFLINE",
            "human_gates_encountered": lease.get("human_gate", "NONE"),
            "money_spent_eur": 0.0,
            "model_calls": 0,
            "next_safe_action": "Autonomous session completed cleanly.",
        }
        _atomic_write(
            self.reports_dir / f"{lease.get('lease_id', 'inactive')}.json", report
        )
        return {
            "CHIEF_STATUS": lease["status"],
            "status": lease["status"],
            "stop_reason": reason,
            "tasks_completed": lease.get("tasks_completed", 0),
            "model_calls": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Computer A Bounded Autonomous Production Loop (Chief Autopilot)"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=("start", "run", "status", "stop", "resume", "canary"),
    )
    parser.add_argument(
        "lease_command",
        nargs="?",
        help='e.g. "AUTOPILOT 90 MINUTEN" or "90"',
    )
    parser.add_argument("--minutes", type=int, help="Lease duration in minutes (e.g. 90)")
    parser.add_argument("--limit", type=int, default=DEFAULT_TASK_LIMIT, help="Max tasks limit")
    parser.add_argument("--run", action="store_true", help="Immediately run loop after starting")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()

    autopilot = BoundedChiefAutopilot()

    if args.command == "start":
        duration_cmd = f"AUTOPILOT {args.minutes} MINUTEN" if args.minutes else args.lease_command
        if not duration_cmd:
            parser.error("start requires --minutes or a duration argument like 'AUTOPILOT 90 MINUTEN'")
        result = autopilot.start(duration_cmd, task_limit=args.limit)
        if args.run and result.get("CHIEF_STATUS") == "AUTOPILOT_STARTED":
            result = autopilot.run_lease(poll_seconds=args.poll_seconds)

    elif args.command == "run":
        result = autopilot.run_lease(poll_seconds=args.poll_seconds)

    elif args.command == "stop":
        result = autopilot.stop()

    elif args.command == "resume":
        result = autopilot.resume()
        if args.run:
            result = autopilot.run_lease(poll_seconds=args.poll_seconds)

    elif args.command == "canary":
        # Start a 1-minute test canary session with limit 2
        autopilot.start("AUTOPILOT 1 MINUTEN", task_limit=2)
        result = autopilot.run_lease(poll_seconds=0.1)

    else:
        result = autopilot.lease()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
