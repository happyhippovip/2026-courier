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

        self.locks_dir = repo_dir / "events/locks"
        self.locks_dir.mkdir(parents=True, exist_ok=True)

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
                # Check if process is actually alive on Unix
                if existing_pid and existing_pid != pid:
                    try:
                        os.kill(existing_pid, 0)
                        # Process is still alive
                        raise WorkflowLockedError(
                            f"Workflow {workflow_id} is already locked by PID {existing_pid}."
                        )
                    except OSError:
                        # Stale lock from crashed process -> can safely reclaim
                        print(f"[LOCK] Reclaiming stale lock for {workflow_id} from dead PID {existing_pid}")
            except (json.JSONDecodeError, KeyError):
                pass

        lock_data = {
            "workflow_id": workflow_id,
            "correlation_id": correlation_id or "UNKNOWN",
            "current_task_id": current_task_id or "UNKNOWN",
            "status": "LOCKED",
            "pid": pid,
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
                    "target_agent": res_data.get("source", "antigravity"),
                },
                "reason": "QA verification failed; repair task dispatched.",
                "created_at": now_iso,
            }
        elif verdict == "PASS":
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
                }

            elif payload.get("spawn_followup"):
                next_task_info = payload.get("spawn_followup")
            elif payload.get("next_task"):
                next_task_info = payload.get("next_task")
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
    ) -> dict:
        """Executes a multi-round Level 6 workflow until completion, human gate, or max iterations."""
        if not correlation_id:
            correlation_id = f"corr-wf-{uuid.uuid4().hex[:8]}"

        self.acquire_workflow_lock(workflow_id)

        history = []
        status = "RUNNING"
        stop_reason = "UNKNOWN"
        start_time = time.time()

        print(f"\n=======================================================")
        print(f"=== STARTING LEVEL 6 AUTONOMOUS LOOP: {workflow_id} ===")
        print(f"=== Total Plan Steps: {len(workflow_plan)} | Max Iterations: {self.max_iterations} ===")
        print(f"=======================================================")

        try:
            current_task_info = workflow_plan[0] if workflow_plan else None
            parent_task_id = None

            for iteration in range(self.max_iterations):
                if not current_task_info:
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

                is_codex = "codex" in target_agent_raw
                target_agent_name = "courier-codex-bridge" if is_codex else "courier-antigravity-bridge"
                active_tracker = self.codex_state_tracker if is_codex else self.state_tracker
                active_hooks = self.codex_hooks if is_codex else self.hooks

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
                if cached_res and not payload_override:
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
                    # Advance to next iteration automatically
                    continue

                else:
                    status = "UNKNOWN_ACTION"
                    stop_reason = f"Unrecognized action: {action}"
                    break
            else:
                status = "MAX_ITERATIONS_REACHED"
                stop_reason = f"Terminated after reaching limit of {self.max_iterations} iterations."

        finally:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Level 6 Autonomous Multi-Turn Loop")
    parser.add_argument("--workflow-id", type=str, default=f"wf-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--plan-file", type=Path, help="JSON file containing list of task step objects")
    parser.add_argument("--real-codex", action="store_true", help="Use the installed Codex CLI for Codex-targeted plan steps")
    args = parser.parse_args()

    plan = []
    if args.plan_file and args.plan_file.exists():
        plan = load_json(args.plan_file)

    engine = AutonomousLevel6Loop(max_iterations=args.max_iterations)
    result = engine.run_multi_round_workflow(
        args.workflow_id,
        plan,
        try_real_codex=args.real_codex,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
