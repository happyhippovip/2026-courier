#!/usr/bin/env python3
"""Autonomous Multi-Turn Level-6 Orchestration Loop Engine.

Implements the verified Level-6 autonomous cycle:
TASK -> DISPATCH -> AGENT BRIDGE -> RESULT_READY -> CHIEF REVIEW -> NEXT_TASK -> LOOP

Guards:
- Finite iteration guard (MAX_ITERATIONS).
- Deterministic workflow lock (prevents concurrent supervisors on same workflow).
- Atomic deduplication & replay protection.
- Immediate stop on HUMAN_APPROVAL_REQUIRED (BLOCKED_HUMAN_GATE).
- Strict preservation of workflow_id, task_id, parent_task_id, correlation_id, and lineage.
- Real-time updates to AgentVisualState machine-readable contract.
- Crash / restart recovery (resumes from last valid uncompleted state).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from scripts.host_guardian import HostGuardian, AdmissionState
import threading
import time
import uuid
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent

EVENTS_DIR = COURIER_DIR / "events"
SCHEMAS_DIR = COURIER_DIR / "schemas"

DISPATCH_DIR = EVENTS_DIR / "dispatch"
PROCESSED_DIR = EVENTS_DIR / "processed"
INCOMING_DIR = EVENTS_DIR / "incoming"
DECISIONS_DIR = EVENTS_DIR / "chief-decisions"
STATES_DIR = EVENTS_DIR / "agent-states"
LOCKS_DIR = EVENTS_DIR / "locks"
WORKFLOWS_DIR = EVENTS_DIR / "workflows"

# Import verified Antigravity Bridge runner components
try:
    from run_antigravity_bridge import (
        AntigravityHookRunner,
        AntigravityVisualStateTracker,
        execute_bridge_task,
        load_json,
        save_json,
    )
    from run_codex_bridge import (
        CodexHookRunner,
        CodexVisualStateTracker,
        execute_codex_task,
    )
    from run_context_sync import UpdateSteward
    from resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
        ReviewDedupeTracker,
    )
except ImportError:
    from scripts.run_antigravity_bridge import (
        AntigravityHookRunner,
        AntigravityVisualStateTracker,
        execute_bridge_task,
        load_json,
        save_json,
    )
    from scripts.run_codex_bridge import (
        CodexHookRunner,
        CodexVisualStateTracker,
        execute_codex_task,
    )
    from scripts.run_context_sync import UpdateSteward
    from scripts.resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
        ReviewDedupeTracker,
    )

try:
    from google_builder_worker import execute_google_task
except ImportError:
    try:
        from scripts.google_builder_worker import execute_google_task
    except ImportError:
        execute_google_task = None



class WorkflowLockedError(Exception):
    """Raised when a workflow lock file cannot be acquired."""


class AutonomousLevel6Loop:
    """Orchestrates an autonomous multi-turn Level 6 loop across Antigravity and Codex bridges."""

    def __init__(
        self,
        repo_dir: Path = COURIER_DIR,
        max_iterations: int | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.repo_dir = repo_dir
        if max_iterations is None:
            self.max_iterations = ResourcePolicyManager.get_default_iterations(repo_dir=repo_dir)
        else:
            self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.host_guardian = HostGuardian(max_heavy_local_jobs=1)

        self.locks_dir = repo_dir / "events/locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.workflows_dir = repo_dir / "events/workflows"
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

        self.steward = UpdateSteward(repo_dir=repo_dir)

        self.state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-antigravity-bridge",
            name="Antigravity Bridge",
            role="Courier Level 6 Automation",
        )
        self.hooks = AntigravityHookRunner(self.state_tracker)

        self.codex_state_tracker = CodexVisualStateTracker(
            agent_id="agent-codex-bridge",
            name="Codex Bridge",
            role="Courier Level 6 Automation",
        )
        self.codex_hooks = CodexHookRunner(self.codex_state_tracker)

        self.lease_manager = TaskLeaseManager(repo_dir=repo_dir)
        self.dedupe_engine = TaskDedupeEngine(repo_dir=repo_dir)

    def save_workflow_state(self, workflow_id: str, state_data: dict) -> Path:
        """Atomically saves durable workflow state to events/workflows/{workflow_id}-state.json."""
        self.workflows_dir.mkdir(parents=True, exist_ok=True)
        target_file = self.workflows_dir / f"{workflow_id}-state.json"
        tmp_file = self.workflows_dir / f".{workflow_id}.{os.getpid()}.{threading.get_ident()}.statetmp"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        state_data.setdefault("updated_at", now_iso)

        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, target_file)
        return target_file

    def load_workflow_state(self, workflow_id: str) -> dict | None:
        """Loads durable workflow state from disk if it exists."""
        target_file = self.workflows_dir / f"{workflow_id}-state.json"
        if not target_file.exists():
            return None
        try:
            return load_json(target_file)
        except Exception:
            return None

    def reconcile_workflow_progress(self, workflow_plan: list[dict]) -> tuple[int, list[dict]]:
        """Inspects disk events to find the earliest uncompleted step index and recovered history."""
        recovered_history = []
        first_uncompleted_index = len(workflow_plan)

        for idx, step in enumerate(workflow_plan):
            task_id = step.get("task_id")
            if not task_id:
                first_uncompleted_index = idx
                break

            dec_file = self.repo_dir / f"events/chief-decisions/{task_id}-chief-decision.json"
            res_file = self.repo_dir / f"events/processed/{task_id}-result.json"

            if dec_file.exists():
                try:
                    dec_data = load_json(dec_file)
                    if dec_data.get("verdict") in ("ACCEPTED", "PASS"):
                        recovered_history.append({
                            "round": idx + 1,
                            "task_id": task_id,
                            "target_agent": step.get("target_agent", "antigravity"),
                            "parent_task_id": workflow_plan[idx - 1].get("task_id") if idx > 0 else None,
                            "correlation_id": dec_data.get("correlation_id", ""),
                            "verdict": dec_data.get("verdict"),
                            "action": dec_data.get("action", "DISPATCH_NEXT_WORKFLOW_TASK"),
                            "result_file": res_file.name if res_file.exists() else "",
                            "decision_file": dec_file.name,
                        })
                        continue
                except Exception:
                    pass

            first_uncompleted_index = idx
            break

        return first_uncompleted_index, recovered_history

    def acquire_workflow_lock(
        self,
        workflow_id: str,
        correlation_id: str | None = None,
        current_task_id: str | None = None,
    ) -> Path:
        """Acquires a deterministic, process-aware lock file persisting real workflow metadata."""
        lock_file = self.locks_dir / f"{workflow_id}.lock"
        pid = os.getpid()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if lock_file.exists():
            try:
                data = load_json(lock_file)
                existing_pid = data.get("pid")
                existing_create_time = data.get("process_create_time")
                
                if existing_pid and existing_pid != pid:
                    import psutil
                    try:
                        p = psutil.Process(existing_pid)
                        # Process exists, check if it's the exact same process by creation time
                        if not existing_create_time or p.create_time() == existing_create_time:
                            raise WorkflowLockedError(
                                f"Workflow {workflow_id} is already locked by PID {existing_pid}."
                            )
                        else:
                            # PID was reused by a different process -> can safely reclaim
                            print(f"[LOCK] PID {existing_pid} reused; reclaiming stale lock for {workflow_id}")
                    except psutil.NoSuchProcess:
                        # Stale lock from crashed process -> can safely reclaim
                        print(f"[LOCK] Reclaiming stale lock for {workflow_id} from dead PID {existing_pid}")
            except (json.JSONDecodeError, KeyError):
                pass

        import psutil
        lock_data = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id or "UNKNOWN",
            "current_task_id": current_task_id or "UNKNOWN",
            "status": "LOCKED",
            "pid": pid,
            "process_create_time": psutil.Process(pid).create_time(),
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        save_json(lock_file, lock_data)
        return lock_file

    def release_workflow_lock(self, workflow_id: str) -> None:
        """Releases the workflow lock file."""
        lock_file = self.locks_dir / f"{workflow_id}.lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
            except OSError:
                pass

    def check_human_approval(
        self,
        workflow_id: str,
        correlation_id: str,
        task_id: str | None = None,
    ) -> dict | None:
        """Checks events/approvals/ for an explicit human gate approval or rejection event.
        
        Strict validation: Both workflow_id AND correlation_id MUST match to prevent cross-workflow approvals.
        """
        approvals_dir = self.repo_dir / "events/approvals"
        if not approvals_dir.exists():
            return None
        for appr_file in sorted(approvals_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = load_json(appr_file)
                # Strict matching on workflow_id and correlation_id
                if data.get("workflow_id") == workflow_id and data.get("correlation_id") == correlation_id:
                    return data
            except Exception:
                pass
        return None

    def evaluate_chief_decision(
        self,
        task_id: str,
        correlation_id: str,
        result_file: Path,
        workflow_id: str,
        round_index: int,
        workflow_plan: list[dict] | None = None,
    ) -> dict:
        """Acts as Chief Review Router, evaluating worker output and generating a ChiefDecision event."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        decision_file = self.repo_dir / f"events/chief-decisions/{task_id}-chief-decision.json"

        result_data = load_json(result_file)
        payload = result_data.get("payload", {})
        verdict = payload.get("verdict", "FAIL")

        # 1. Check for Human Approval Gate Requirement
        if payload.get("requires_human_approval") or payload.get("human_gate_required") or verdict in ["HUMAN_GATE", "HUMAN_APPROVAL_REQUIRED"]:
            # Check if an approval event was already persisted for this exact workflow and correlation
            approval_event = self.check_human_approval(workflow_id, correlation_id, task_id)
            if approval_event:
                appr_action = approval_event.get("decision") or approval_event.get("action", "")
                if appr_action == "APPROVE":
                    print(f"[CHIEF REVIEW] Validated Human Approval consumed for {workflow_id} (corr: {correlation_id}): APPROVED by {approval_event.get('operator', 'HUMAN')}")
                    verdict = "ACCEPTED"
                elif appr_action == "REJECT":
                    print(f"[CHIEF REVIEW] Validated Human Rejection consumed for {workflow_id} (corr: {correlation_id}): REJECTED by {approval_event.get('operator', 'HUMAN')}")
                    decision = {
                        "schema_version": "2.0",
                        "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                        "task_id": task_id,
                        "correlation_id": correlation_id,
                        "workflow_id": workflow_id,
                        "round_index": round_index,
                        "verdict": "REJECTED",
                        "action": "STOP_ON_HUMAN_REJECTION",
                        "next_task": None,
                        "reason": f"Workflow task explicitly rejected by human operator: {approval_event.get('reason', 'None')}",
                        "created_at": now_iso,
                    }
                    save_json(decision_file, decision)
                    return decision
            else:
                decision = {
                    "schema_version": "2.0",
                    "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "workflow_id": workflow_id,
                    "round_index": round_index,
                    "verdict": "HUMAN_APPROVAL_REQUIRED",
                    "action": "STOP_AT_HUMAN_GATE",
                    "next_task": None,
                    "reason": "Task payload flagged for explicit human approval before advancing.",
                    "created_at": now_iso,
                }
                save_json(decision_file, decision)
                return decision

        if verdict == "NEEDS_FIX":
            decision = {
                "schema_version": "2.0",
                "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                "task_id": task_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "round_index": round_index,
                "verdict": "NEEDS_FIX",
                "action": "QUEUE_SCOPED_REPAIR_TASK",
                "next_task": {
                    "task_id": f"repair-{task_id}",
                    "instruction": f"Fix defects reported in {task_id}",
                    "allowed_scope": payload.get("target_file", []),
                    "target_agent": result_data.get("source", "antigravity"),
                },
                "reason": "QA verification failed; repair task dispatched.",
                "created_at": now_iso,
            }
        elif verdict in ("PASS", "ACCEPTED"):
            # Determine if there is a next task in the workflow plan
            next_task_info = None
            if workflow_plan and (round_index + 1) < len(workflow_plan):
                next_step = workflow_plan[round_index + 1]
                next_task_info = {
                    "task_id": next_step.get("task_id", f"{workflow_id}-round-{round_index + 2}"),
                    "instruction": next_step.get("instruction", "Execute next step"),
                    "allowed_scope": next_step.get("allowed_scope", []),
                    "target_agent": next_step.get("target_agent", "antigravity"),
                    "payload_override": next_step.get("payload_override"),
                    "parameters": next_step.get("parameters"),
                }

            if next_task_info:
                decision = {
                    "schema_version": "2.0",
                    "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "workflow_id": workflow_id,
                    "round_index": round_index,
                    "verdict": "ACCEPTED",
                    "action": "DISPATCH_NEXT_WORKFLOW_TASK",
                    "next_task": next_task_info,
                    "reason": f"Round {round_index + 1} passed; advancing to Round {round_index + 2}.",
                    "created_at": now_iso,
                }
            else:
                decision = {
                    "schema_version": "2.0",
                    "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                    "task_id": task_id,
                    "correlation_id": correlation_id,
                    "workflow_id": workflow_id,
                    "round_index": round_index,
                    "verdict": "ACCEPTED",
                    "action": "COMPLETE_WORKFLOW",
                    "next_task": None,
                    "reason": "All planned workflow rounds successfully executed.",
                    "created_at": now_iso,
                }
        elif verdict in ("PAUSED_PROVIDER_LIMIT", "QUOTA_EXCEEDED") or (payload and any(k in str(payload.get("error", "")).upper() for k in ("QUOTA", "RATE_LIMIT", "RESOURCE_EXHAUSTED", "429"))):
            decision = {
                "schema_version": "2.0",
                "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                "task_id": task_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "round_index": round_index,
                "verdict": "PAUSED_PROVIDER_LIMIT",
                "action": "PAUSE_ON_PROVIDER_LIMIT",
                "next_task": None,
                "reason": payload.get("error", "Provider quota / rate limit encountered. Workflow paused safely without losing progress."),
                "created_at": now_iso,
            }
        else:
            decision = {
                "schema_version": "2.0",
                "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                "task_id": task_id,
                "correlation_id": correlation_id,
                "workflow_id": workflow_id,
                "round_index": round_index,
                "verdict": "FAILED",
                "action": "STOP_ON_FAILURE",
                "next_task": None,
                "reason": payload.get("error", "Unknown execution failure"),
                "created_at": now_iso,
            }

        save_json(decision_file, decision)
        self.steward.refresh_snapshot_after_event("CHIEF_DECISION_SAVED", task_id)
        return decision

    def run_multi_round_workflow(
        self,
        workflow_id: str,
        workflow_plan: list[dict],
        correlation_id: str | None = None,
        try_real_codex: bool = False,
        initial_history: list[dict] | None = None,
        start_step_index: int = 0,
    ) -> dict:
        """Executes a multi-round Level 6 workflow until completion, human gate, or max iterations."""
        if not correlation_id:
            correlation_id = f"corr-wf-{uuid.uuid4().hex[:8]}"

        self.acquire_workflow_lock(workflow_id)

        history = list(initial_history or [])
        status = "RUNNING"
        stop_reason = "UNKNOWN"
        start_time = time.time()

        print(f"\n=======================================================")
        print(f"=== STARTING LEVEL 6 AUTONOMOUS LOOP: {workflow_id} ===")
        print(f"=== Total Plan Steps: {len(workflow_plan)} | Start Step: {start_step_index + 1} | Max Iterations: {self.max_iterations} ===")
        print(f"=======================================================")

        # Persist initial durable state
        self.save_workflow_state(workflow_id, {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "workflow_plan": workflow_plan,
            "current_step_index": start_step_index,
            "status": "RUNNING",
            "stop_reason": "IN_PROGRESS",
            "history": history,
        })

        try:
            current_task_info = workflow_plan[start_step_index] if (workflow_plan and start_step_index < len(workflow_plan)) else None
            parent_task_id = history[-1].get("task_id") if history else None

            for iteration in range(start_step_index, start_step_index + self.max_iterations):
                if not current_task_info or iteration >= len(workflow_plan):
                    status = "COMPLETED"
                    stop_reason = "PLAN_COMPLETED"
                    break

                if (time.time() - start_time) > self.timeout_seconds:
                    status = "TIMEOUT"
                    stop_reason = "MAX_TIMEOUT_EXCEEDED"
                    break

                task_id = current_task_info.get("task_id", f"{workflow_id}-step-{iteration + 1}")
                instruction = current_task_info.get("instruction", "Execute step")
                allowed_scope = current_task_info.get("allowed_scope", [])
                payload_override = current_task_info.get("payload_override")
                target_agent_raw = current_task_info.get("target_agent", "antigravity").lower()

                
                # --- HOST GUARDIAN ADMISSION CHECK ---
                admission = self.host_guardian.evaluate_admission()
                if admission == AdmissionState.CLOSED:
                    self.host_guardian.stabilize([])
                    admission = self.host_guardian.evaluate_admission()
                    if admission == AdmissionState.CLOSED:
                        status = "RESOURCE_PAUSE"
                        stop_reason = f"Host admission is CLOSED ({self.host_guardian.state.name}). Lane hibernating."
                        break

                is_heavy = "codex" in target_agent_raw or "engineer" in target_agent_raw
                has_lease = False
                if is_heavy:
                    if not self.host_guardian.request_heavy_lease():
                        self.host_guardian.stabilize([])
                        if not self.host_guardian.request_heavy_lease():
                            status = "RESOURCE_PAUSE"
                            if self.host_guardian.cleanup_unknown:
                                stop_reason = "Host admission blocked (LIGHT_ONLY) due to UNCLEAN previous shutdown (cleanup UNKNOWN)."
                            elif self.host_guardian.state.name == "LIGHT_ONLY":
                                stop_reason = "Host pressure limits heavy jobs. LIGHT_ONLY active. Lane hibernating."
                            else:
                                stop_reason = "MAX_HEAVY_LOCAL_JOBS exceeded. Lane hibernating."
                            break
                    has_lease = True
                
                is_codex = "codex" in target_agent_raw
                is_google = "google" in target_agent_raw or "builder" in target_agent_raw
                if is_codex:
                    target_agent_name = "courier-codex-bridge"
                    active_tracker = self.codex_state_tracker
                    active_hooks = self.codex_hooks
                elif is_google:
                    target_agent_name = "google-mac"
                    active_tracker = self.state_tracker
                    active_hooks = self.hooks
                else:
                    target_agent_name = "courier-antigravity-bridge"
                    active_tracker = self.state_tracker
                    active_hooks = self.hooks

                print(f"\n--- [ROUND {iteration + 1}/{self.max_iterations}] Task: {task_id} (Target: {target_agent_name}) ---")

                # 1. Update visual state
                active_tracker.update_state(
                    state="RUNNING",
                    task=task_id,
                    progress=float(iteration) / float(len(workflow_plan)),
                    workflow=workflow_id,
                    last_action=f"Starting round {iteration + 1}: {task_id}",
                    next_action=f"Executing {target_agent_name} task",
                    blocked=False,
                    human_gate=None,
                )

                # 2. Stage WorkerJob in dispatch/
                dispatch_file = self.repo_dir / f"events/dispatch/{task_id}-worker-job.json"
                task_hash = self.dedupe_engine.compute_task_hash(
                    task_type="WORKER_TASK",
                    instruction=instruction,
                    target_agent=target_agent_name,
                    input_files=allowed_scope,
                    parameters=current_task_info.get("parameters"),
                )

                ctx_ver_raw = current_task_info.get("context_version")
                ctx_ver_int = int(str(ctx_ver_raw).lstrip("v")) if (ctx_ver_raw and str(ctx_ver_raw).lstrip("v").isdigit()) else 73
                context_pkg = ChiefContextPackageBuilder.build_compact_package(
                    workflow_id=workflow_id,
                    task_id=task_id,
                    instruction=instruction,
                    scope_files=allowed_scope,
                    context_version=ctx_ver_int,
                    context_delta=current_task_info.get("context_delta"),
                    repo_dir=self.repo_dir,
                )

                job_data = {
                    "schema_version": "2.0",
                    "job_id": f"job-{'cdx' if is_codex else 'ag'}-{task_id}",
                    "source_command_message_id": f"msg-cmd-{task_id}",
                    "task_id": task_id,
                    "task_hash": task_hash,
                    "correlation_id": correlation_id,
                    "workflow_id": workflow_id,
                    "parent_task_id": parent_task_id,
                    "target_agent": target_agent_name,
                    "instruction": instruction,
                    "allowed_scope": allowed_scope,
                    "forbidden_scope": ["public_upload", "secrets", "paid_apis"],
                    "cost_policy": "ZERO_COST_ONLY",
                    "human_gate_policy": "STOP_ON_HUMAN_GATE_ONLY",
                    "max_iterations": 1,
                    "context_package": context_pkg,
                    "context_delta": current_task_info.get("context_delta"),
                    "context_version": current_task_info.get("context_version"),
                    "context_snapshot_hash": current_task_info.get("context_snapshot_hash"),
                    "bounded_context": current_task_info.get("bounded_context"),
                    "parameters": current_task_info.get("parameters"),
                    "routing_decision": {
                        "target_agent": target_agent_name,
                        "routing_reason": current_task_info.get("routing_reason", "Assigned by SmartResourceRouter"),
                        "execution_class": "REAL_CODEX_CLI" if (is_codex and try_real_codex) else ("DETERMINISTIC_CODEX" if is_codex else "DETERMINISTIC_ANTIGRAVITY"),
                    },
                    "expected_output": "Structured summary result",
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                save_json(dispatch_file, job_data)

                # 3. Deduplication Check & Single-Owner Lease Enforcement
                cached_res = self.dedupe_engine.get_cached_result(task_hash)
                if cached_res and not payload_override and cached_res.get("payload", {}).get("verdict") not in ("PAUSED_PROVIDER_LIMIT", "FAILED"):
                    print(f"[DEDUPE] Identical task input hash ({task_hash[:12]}...) found. Reusing verified result without executing model.")
                    result_file = self.repo_dir / f"events/processed/{task_id}-result.json"
                    save_json(result_file, cached_res)
                else:
                    acquired, lease_reason, lease_data = self.lease_manager.acquire_lease(
                        task_id=task_id,
                        task_hash=task_hash,
                        owner_id=target_agent_name,
                    )
                    if not acquired:
                        print(f"[COST GATE] Duplicate builder dispatch blocked for task {task_id}: Already claimed by {lease_data.get('owner_id')}.")
                        decision = {
                            "schema_version": "2.0",
                            "decision_id": f"dec-{uuid.uuid4().hex[:10]}",
                            "task_id": task_id,
                            "correlation_id": correlation_id,
                            "workflow_id": workflow_id,
                            "round_index": iteration,
                            "verdict": "DUPLICATE_DISPATCH_BLOCKED",
                            "action": "STOP_ON_DUPLICATE_CLAIM",
                            "next_task": None,
                            "reason": f"Single-owner lease violation: Task already claimed by {lease_data.get('owner_id')}.",
                            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                        decision_file = self.repo_dir / f"events/chief-decisions/{task_id}-chief-decision.json"
                        save_json(decision_file, decision)
                        history.append({
                            "round": iteration + 1,
                            "task_id": task_id,
                            "target_agent": target_agent_name,
                            "verdict": "DUPLICATE_DISPATCH_BLOCKED",
                            "action": "STOP_ON_DUPLICATE_CLAIM",
                        })
                        status = "STOPPED_DUPLICATE_DISPATCH"
                        stop_reason = "DUPLICATE_BUILDER_DISPATCH_BLOCKED"
                        break

                    try:
                        if is_codex:
                            result_file = execute_codex_task(
                                dispatch_file,
                                active_hooks,
                                try_real_cli=try_real_codex,
                            )
                        elif is_google and execute_google_task:
                            result_file = execute_google_task(
                                dispatch_file,
                                active_hooks,
                                repo_dir=self.repo_dir,
                            )
                        else:
                            result_file = execute_bridge_task(dispatch_file, active_hooks)
                    finally:
                        self.lease_manager.release_lease(task_id, target_agent_name)

                    if result_file and result_file.exists():
                        res_data = load_json(result_file)
                        res_hash = hashlib.sha256(json.dumps(res_data.get("payload", {}), sort_keys=True).encode("utf-8")).hexdigest()
                        self.dedupe_engine.register_task_result(task_hash, task_id, result_file.name, res_hash)

                # If payload override specified (for simulating human approval gate or specific return condition)
                if payload_override:
                    res_data = load_json(result_file)
                    res_data["payload"].update(payload_override)
                    save_json(result_file, res_data)

                # 4. Chief Review Router Evaluation
                decision = self.evaluate_chief_decision(
                    task_id=task_id,
                    correlation_id=correlation_id,
                    result_file=result_file,
                    workflow_id=workflow_id,
                    round_index=iteration,
                    workflow_plan=workflow_plan,
                )

                action = decision["action"]
                verdict = decision["verdict"]

                if has_lease:
                    self.host_guardian.release_heavy_lease(cleanup_proven=True)
                    has_lease = False

                round_record = {
                    "round": iteration + 1,
                    "task_id": task_id,
                    "target_agent": target_agent_name,
                    "parent_task_id": parent_task_id,
                    "correlation_id": correlation_id,
                    "verdict": verdict,
                    "action": action,
                    "result_file": str(result_file.name),
                    "decision_file": f"{task_id}-chief-decision.json",
                }
                history.append(round_record)

                print(f"[ROUND {iteration + 1} RESULT ({target_agent_name})] Verdict: {verdict} -> Action: {action}")

                # 5. Handle Action routing
                if action == "STOP_AT_HUMAN_GATE":
                    status = "BLOCKED_HUMAN_GATE"
                    stop_reason = "HUMAN_APPROVAL_REQUIRED"
                    active_tracker.update_state(
                        state="BLOCKED_HUMAN_GATE",
                        task=task_id,
                        progress=float(iteration + 1) / float(len(workflow_plan)),
                        workflow=workflow_id,
                        last_action=f"Stopped at Human Gate: {task_id}",
                        next_action=None,
                        blocked=True,
                        human_gate="REQUIRE_EXPLICIT_HUMAN_APPROVAL",
                    )
                    break

                elif action == "STOP_ON_HUMAN_REJECTION":
                    status = "REJECTED_BY_HUMAN"
                    stop_reason = "HUMAN_OPERATOR_REJECTED"
                    active_tracker.update_state(
                        state="REJECTED",
                        task=task_id,
                        progress=float(iteration + 1) / float(len(workflow_plan)),
                        workflow=workflow_id,
                        last_action=f"Workflow explicitly rejected by human operator: {decision.get('reason')}",
                        next_action=None,
                        blocked=True,
                        human_gate=None,
                    )
                    break

                elif action == "STOP_ON_FAILURE":
                    status = "FAILED"
                    stop_reason = "EXECUTION_FAILURE"
                    active_tracker.update_state(
                        state="FAILED",
                        task=task_id,
                        progress=float(iteration + 1) / float(len(workflow_plan)),
                        workflow=workflow_id,
                        last_action=f"Failed on task: {task_id}",
                        next_action=None,
                        blocked=True,
                    )
                    break

                elif action == "PAUSE_ON_PROVIDER_LIMIT":
                    status = "PAUSED_PROVIDER_LIMIT"
                    stop_reason = f"Provider rate/quota limit reached: {decision.get('reason')}"
                    active_tracker.update_state(
                        state="PAUSED_PROVIDER_LIMIT",
                        task=task_id,
                        progress=float(iteration) / float(len(workflow_plan)),
                        workflow=workflow_id,
                        last_action=f"Paused due to provider limits: {task_id}",
                        next_action=f"Retry {task_id} when quota restores",
                        blocked=True,
                    )
                    break

                elif action == "COMPLETE_WORKFLOW":
                    status = "COMPLETED"
                    stop_reason = "ALL_STEPS_ACCEPTED"
                    active_tracker.update_state(
                        state="COMPLETED",
                        task=task_id,
                        progress=1.0,
                        workflow=workflow_id,
                        last_action=f"Workflow {workflow_id} successfully completed by {target_agent_name}",
                        next_action=None,
                        blocked=False,
                        human_gate=None,
                    )
                    break

                elif action in ("DISPATCH_NEXT_WORKFLOW_TASK", "QUEUE_SCOPED_REPAIR_TASK"):
                    parent_task_id = task_id
                    current_task_info = decision.get("next_task")
                    self.save_workflow_state(workflow_id, {
                        "workflow_id": workflow_id,
                        "correlation_id": correlation_id,
                        "workflow_plan": workflow_plan,
                        "current_step_index": iteration + 1,
                        "status": "RUNNING",
                        "stop_reason": f"Step {iteration + 1} completed; advancing to step {iteration + 2}",
                        "history": history,
                    })
                    continue

                else:
                    status = "UNKNOWN_ACTION"
                    stop_reason = f"Unrecognized action: {action}"
                    break
            else:
                status = "MAX_ITERATIONS_REACHED"
                stop_reason = f"Terminated after reaching limit of {self.max_iterations} iterations."

        finally:
            if 'has_lease' in locals() and has_lease:
                self.host_guardian.release_heavy_lease(cleanup_proven=False)
            final_step_index = len(workflow_plan) if status == "COMPLETED" else len(history)
            self.save_workflow_state(workflow_id, {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "workflow_plan": workflow_plan,
                "current_step_index": final_step_index,
                "status": status,
                "stop_reason": stop_reason,
                "history": history,
            })
            self.release_workflow_lock(workflow_id)

        print(f"\n=== LEVEL 6 LOOP FINISHED: {status} ({stop_reason}) ===")
        print(f"Total Rounds Completed: {len(history)}")
        return {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id,
            "status": status,
            "stop_reason": stop_reason,
            "rounds_completed": len(history),
            "history": history,
        }

    def resume_workflow(
        self,
        workflow_id: str,
        correlation_id: str,
        workflow_plan: list[dict],
        from_round_index: int = 1,
        try_real_codex: bool = False,
    ) -> dict:
        """Resumes a paused workflow starting from from_round_index after validating matching human approval."""
        approval = self.check_human_approval(workflow_id, correlation_id)
        if not approval:
            return {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "status": "BLOCKED_HUMAN_GATE",
                "stop_reason": "NO_MATCHING_APPROVAL_FOUND",
                "history": [],
            }

        appr_action = approval.get("decision") or approval.get("action", "")
        if appr_action == "REJECT":
            return {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "status": "REJECTED_BY_HUMAN",
                "stop_reason": "HUMAN_OPERATOR_REJECTED",
                "history": [],
            }

        remaining_plan = workflow_plan[from_round_index:]
        if not remaining_plan:
            return {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "status": "COMPLETED",
                "stop_reason": "NO_REMAINING_STEPS",
                "history": [],
            }

        print(f"\n[RESUME] Resuming workflow {workflow_id} from Step {from_round_index + 1} ({len(remaining_plan)} steps remaining)...")
        return self.run_multi_round_workflow(
            workflow_id=workflow_id,
            workflow_plan=remaining_plan,
            correlation_id=correlation_id,
            try_real_codex=try_real_codex,
        )

    def resume_interrupted_workflow(
        self,
        workflow_id: str,
        try_real_codex: bool = False,
    ) -> dict:
        """Resumes an interrupted or paused workflow from durable disk state without human relay."""
        state = self.load_workflow_state(workflow_id)
        if not state:
            return {
                "workflow_id": workflow_id,
                "correlation_id": "",
                "status": "NOT_FOUND",
                "stop_reason": f"Workflow state for {workflow_id} not found on disk.",
                "history": [],
            }

        workflow_plan = state.get("workflow_plan", [])
        correlation_id = state.get("correlation_id", f"corr-wf-{uuid.uuid4().hex[:8]}")
        prev_status = state.get("status")

        if prev_status == "COMPLETED":
            print(f"[RESUME] Workflow {workflow_id} is already COMPLETED.")
            return state

        # If it was blocked by a human gate, verify if human approval is present
        if prev_status == "BLOCKED_HUMAN_GATE":
            approval = self.check_human_approval(workflow_id, correlation_id)
            if not approval:
                print(f"[RESUME] Workflow {workflow_id} remains BLOCKED_HUMAN_GATE (no matching approval).")
                return state
            appr_action = approval.get("decision") or approval.get("action", "")
            if appr_action == "REJECT":
                state["status"] = "REJECTED_BY_HUMAN"
                state["stop_reason"] = "HUMAN_OPERATOR_REJECTED"
                self.save_workflow_state(workflow_id, state)
                return state

        # Reconcile disk state against plan
        first_uncompleted_idx, recovered_history = self.reconcile_workflow_progress(workflow_plan)

        state_history = state.get("history", [])
        effective_history = recovered_history if len(recovered_history) >= len(state_history) else state_history

        if first_uncompleted_idx >= len(workflow_plan):
            print(f"[RESUME] All steps in workflow {workflow_id} are already accepted on disk. Marking COMPLETED.")
            state["status"] = "COMPLETED"
            state["stop_reason"] = "ALL_STEPS_ACCEPTED"
            state["history"] = effective_history
            state["current_step_index"] = len(workflow_plan)
            self.save_workflow_state(workflow_id, state)
            return state

        print(f"\n[RESUME] Unattended resume for {workflow_id}: starting from Step {first_uncompleted_idx + 1}/{len(workflow_plan)}...")
        return self.run_multi_round_workflow(
            workflow_id=workflow_id,
            workflow_plan=workflow_plan,
            correlation_id=correlation_id,
            try_real_codex=try_real_codex,
            initial_history=effective_history,
            start_step_index=first_uncompleted_idx,
        )

    def auto_resume_pending_workflows(self, try_real_codex: bool = False) -> list[dict]:
        """Discovers and automatically resumes any pending/interrupted workflows on disk."""
        results = []
        if not self.workflows_dir.exists():
            return results

        state_files = sorted(self.workflows_dir.glob("*-state.json"))
        for sf in state_files:
            try:
                state = load_json(sf)
            except Exception:
                continue

            wf_id = state.get("workflow_id")
            if not wf_id:
                continue

            status = state.get("status")
            if status in ("RUNNING", "INTERRUPTED", "RESOURCE_PAUSE", "PAUSED_RESOURCE_PRESSURE", "PAUSED_PROVIDER_LIMIT"):
                print(f"[AUTO_RESUME] Found interrupted workflow {wf_id} ({status}). Resuming unattended...")
                res = self.resume_interrupted_workflow(wf_id, try_real_codex=try_real_codex)
                results.append(res)
            elif status == "BLOCKED_HUMAN_GATE":
                appr = self.check_human_approval(wf_id, state.get("correlation_id", ""))
                if appr:
                    print(f"[AUTO_RESUME] Approval found for previously blocked workflow {wf_id}. Resuming unattended...")
                    res = self.resume_interrupted_workflow(wf_id, try_real_codex=try_real_codex)
                    results.append(res)

        return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Level 6 Autonomous Multi-Turn Loop")
    parser.add_argument("--workflow-id", type=str, default=f"wf-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--plan-file", type=Path, help="JSON file containing list of task step objects")
    parser.add_argument("--real-codex", action="store_true", help="Use the installed Codex CLI for Codex-targeted plan steps")
    parser.add_argument("--resume-workflow", type=str, help="Resume an interrupted workflow by ID")
    parser.add_argument("--auto-resume", action="store_true", help="Auto-resume all pending/interrupted workflows")
    args = parser.parse_args()

    engine = AutonomousLevel6Loop(max_iterations=args.max_iterations)

    if args.auto_resume:
        res_list = engine.auto_resume_pending_workflows(try_real_codex=args.real_codex)
        print(json.dumps(res_list, indent=2))
        return 0

    if args.resume_workflow:
        result = engine.resume_interrupted_workflow(args.resume_workflow, try_real_codex=args.real_codex)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "COMPLETED" else 1

    plan = []
    if args.plan_file and args.plan_file.exists():
        plan = load_json(args.plan_file)

    result = engine.run_multi_round_workflow(
        args.workflow_id,
        plan,
        try_real_codex=args.real_codex,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
