#!/usr/bin/env python3
"""Autonomous Chief Commander & Smart Resource Router Engine.

Translates human ideas, goals, and strategic decisions into bounded, multi-turn
autonomous workflows with intelligent resource routing:

Routing Rules:
- ANTIGRAVITY: Primary heavy worker for creative, visual, 3D, UI, media pipelines,
  planning, high-context synthesis, and broad implementation.
- CODEX: Scarce technical specialist reserved for short bounded syntax checks,
  code reviews, test verification, and independent QA audits.
- QUOTA PROTECTION: Never invokes Codex for work Antigravity can safely execute.
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
DECISIONS_DIR = EVENTS_DIR / "chief-decisions"
STATES_DIR = EVENTS_DIR / "agent-states"
LOCKS_DIR = EVENTS_DIR / "locks"
APPROVALS_DIR = EVENTS_DIR / "approvals"

APPROVALS_DIR.mkdir(parents=True, exist_ok=True)

# Import Level 6 Autonomous Engine & Bridge Components
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_thought_curator import ThoughtCurator
    from run_autonomous_loop import AutonomousLevel6Loop
    from run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
    from run_context_sync import UpdateSteward
    from run_bodyguards import BodyguardPoolManager
    from resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
        ReviewDedupeTracker,
    )
except ImportError:
    from scripts.run_thought_curator import ThoughtCurator
    from scripts.run_autonomous_loop import AutonomousLevel6Loop
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
    from scripts.run_context_sync import UpdateSteward
    from scripts.run_bodyguards import BodyguardPoolManager
    from scripts.resource_policy import (
        ResourcePolicyManager,
        CostGate,
        TaskLeaseManager,
        TaskDedupeEngine,
        ChiefContextPackageBuilder,
        ReviewDedupeTracker,
    )




class SmartResourceRouter:
    """Classifies tasks and routes work based on workload type and agent specializations."""

    @staticmethod
    def classify_and_route(task_desc: str, scope_files: list[str], context_delta: dict | None = None) -> tuple[str, str, str]:
        """Determines whether a task should be assigned to ANTIGRAVITY or CODEX.
        
        Returns:
            tuple of (target_agent, routing_reason, execution_class)
        """
        desc_lower = task_desc.lower()
        scope_str = " ".join(scope_files).lower()

        # Keywords indicating scarce technical code review / unit test audits
        codex_triggers = [
            "code review", "syntax audit", "unit test verification", "lint check",
            "security audit", "independent qa verify", "strict schema test", "qa audit"
        ]

        # Check if explicitly an independent technical code check
        for trigger in codex_triggers:
            if trigger in desc_lower:
                return (
                    "codex",
                    f"Scarce technical verification requested: '{trigger}'",
                    "DETERMINISTIC_CODEX"
                )

        # Enforce quota protection: Heavy work, media, 3D, UI, creative, and planning go to Antigravity
        if any(w in desc_lower for w in ["render", "3d", "video", "short", "fruitki", "godot", "asset"]):
            return (
                "antigravity",
                "Primary heavy worker for 3D/video rendering & asset pipeline",
                "DETERMINISTIC_ANTIGRAVITY"
            )

        if any(w in desc_lower for w in ["strategy", "plan", "synthesize", "package", "policy", "discover"]):
            return (
                "antigravity",
                "Primary heavy worker for high-context planning & release synthesis",
                "DETERMINISTIC_ANTIGRAVITY"
            )

        # Default to Antigravity as primary heavy worker for all implementation
        return (
            "antigravity",
            "Default primary worker (Quota Protection active for Codex)",
            "DETERMINISTIC_ANTIGRAVITY"
        )


class ChiefCommander:
    """Autonomous Chief Commander that ingests human ideas, compares memory, and orchestrates execution."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.curator = ThoughtCurator(repo_dir=repo_dir)
        self.steward = UpdateSteward(repo_dir=repo_dir)
        self.loop_engine = AutonomousLevel6Loop(repo_dir=repo_dir)
        self.chief_state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-chief-commander",
            name="Chief Commander",
            role="Autonomous Orchestration & Review",
        )

    def review_runtime_alert(self, alert: dict) -> dict:
        """Create a bounded Chief routing recommendation for a SNITCH alert.

        This deliberately does not start, kill, or restart a worker.  It is a
        durable Courier/Chief decision artifact that a separately authorized
        dispatcher may later consume.
        """
        required = ("message_id", "workflow_id", "correlation_id", "classification", "reason")
        if not all(isinstance(alert.get(field), str) and alert[field] for field in required):
            raise ValueError("Runtime alert lacks required provenance")
        if alert.get("agent_id") != "agent-snitch":
            raise ValueError("Runtime alert source must be agent-snitch")

        description = f"Runtime alert diagnosis: {alert['classification']} — {alert['reason']}"
        target_agent, routing_reason, execution_class = SmartResourceRouter.classify_and_route(
            description, [], {"runtime_alert": alert["message_id"]}
        )

        bodyguard_candidate = None
        if alert.get("classification") in {"SUSPECTED_STALL", "STALLED", "RUNAWAY_RISK", "BLOCKED"}:
            try:
                bg_manager = BodyguardPoolManager(self.repo_dir)
                available = bg_manager.get_available_bodyguards()
                if available:
                    bodyguard_candidate = available[0]["callsign"]
            except Exception:
                pass

        decision = {
            "schema_version": "2.0",
            "decision_id": f"dec-runtime-{uuid.uuid4().hex[:10]}",
            "source_alert_id": alert["message_id"],
            "workflow_id": alert["workflow_id"],
            "correlation_id": alert["correlation_id"],
            "verdict": "RUNTIME_ALERT_REVIEWED",
            "action": "RECOMMEND_SCOPED_DIAGNOSIS",
            "recommended_target_agent": target_agent,
            "recommended_reserve_bodyguard": bodyguard_candidate,
            "execution_class": execution_class,
            "reason": routing_reason,
            "next_task": None,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        decision_dir = self.repo_dir / "events/chief-decisions"
        decision_dir.mkdir(parents=True, exist_ok=True)
        save_json(decision_dir / f"{alert['message_id']}-chief-decision.json", decision)
        return decision


    def formulate_workflow_plan(
        self,
        idea_text: str,
        idea_type: str = "IDEA",
        context_delta: dict | None = None,
        correlation_id: str | None = None
    ) -> tuple[str, list[dict]]:
        """Converts a human idea and Context Delta into a multi-step bounded workflow plan using SmartResourceRouter."""
        workflow_id = f"WF-CHIEF-{uuid.uuid4().hex[:6]}"
        idea_lower = idea_text.lower()

        # Update Steward compiles snapshot
        snapshot = self.steward.generate_context_snapshot(context_delta=context_delta)

        # Step 1: Strategy & Discovery
        step1_desc = f"Formulate execution strategy and inspect context for: {idea_text[:120]}"
        step1_scope = ["config/local_tools.json", "config/teamwork_policy.json"]
        target_1, reason_1, exec_class_1 = SmartResourceRouter.classify_and_route(step1_desc, step1_scope, context_delta)

        step1 = {
            "task_id": f"{workflow_id}-STEP-1-DISCOVER",
            "target_agent": target_1,
            "routing_reason": reason_1,
            "execution_class": exec_class_1,
            "instruction": step1_desc,
            "allowed_scope": step1_scope,
            "context_delta": context_delta,
        }
        self.steward.attach_task_context(step1, snapshot)
        plan = [step1]

        # Step 2: Implementation or QA Audit
        if "test" in idea_lower or "verify" in idea_lower or "audit" in idea_lower:
            step2_desc = f"Perform independent technical QA audit and syntax verification for: {idea_text[:120]}"
            step2_scope = ["config/local_tools.json"]
        else:
            step2_desc = f"Execute core implementation and asset validation for: {idea_text[:120]}"
            step2_scope = ["config/social_channels.json", "config/teamwork_policy.json"]

        target_2, reason_2, exec_class_2 = SmartResourceRouter.classify_and_route(step2_desc, step2_scope, context_delta)
        step2 = {
            "task_id": f"{workflow_id}-STEP-2-{'QA' if target_2 == 'codex' else 'IMPLEMENT'}",
            "target_agent": target_2,
            "routing_reason": reason_2,
            "execution_class": exec_class_2,
            "instruction": step2_desc,
            "allowed_scope": step2_scope,
            "context_delta": context_delta,
        }
        self.steward.attach_task_context(step2, snapshot)
        plan.append(step2)

        # Step 3: Chief Synthesis & Final Acceptance
        step3_desc = f"Finalize results, verify invariants, and assemble completion package for: {idea_text[:120]}"
        step3_scope = ["config/teamwork_policy.json"]
        target_3, reason_3, exec_class_3 = SmartResourceRouter.classify_and_route(step3_desc, step3_scope, context_delta)
        step3 = {
            "task_id": f"{workflow_id}-STEP-3-SYNTHESIZE",
            "target_agent": target_3,
            "routing_reason": reason_3,
            "execution_class": exec_class_3,
            "instruction": step3_desc,
            "allowed_scope": step3_scope,
            "context_delta": context_delta,
        }
        self.steward.attach_task_context(step3, snapshot)
        plan.append(step3)

        return workflow_id, plan

    def execute_human_idea(self, idea_text: str, idea_type: str = "IDEA", dry_run: bool = False) -> dict:
        """Curates human input, verifies against memory, and executes through the autonomous Chief loop."""
        # 1. Step: Idea Sync & Memory Comparison -> Generates Context Delta
        curation = self.curator.curate_idea(idea_text, idea_type)

        # Check for Policy Conflict
        is_conflict = (
            curation.get("classification") in ["CONFLICT", "CONFLICT FOUND"] or
            len(curation.get("conflicts", [])) > 0
        )

        # A human-gate state must have stable provenance.  A later, unrelated
        # Chief decision must never be attached to this blocked idea.
        correlation_id = f"corr-chief-{uuid.uuid4().hex[:8]}"

        if is_conflict:
            print(f"\n[CHIEF] Blocked on policy conflict: {curation.get('conflicts')}")
            self.chief_state_tracker.update_state(
                state="BLOCKED_POLICY_CONFLICT",
                task=f"Policy Conflict: {curation['idea_id']}",
                progress=0.0,
                workflow=curation["idea_id"],
                last_action=f"Blocked dispatch on policy conflict: {[c['rule'] for c in curation.get('conflicts', [])]}",
                next_action="Awaiting explicit human approval event to proceed",
                result=None,
                blocked=True,
                human_gate="REQUIRE_EXPLICIT_HUMAN_APPROVAL",
                correlation_id=correlation_id,
            )
            return {
                "status": "BLOCKED_POLICY_CONFLICT",
                "workflow_id": curation["idea_id"],
                "correlation_id": correlation_id,
                "curation": curation,
                "workflow_plan": [],
                "history": [],
            }

        # 2. Step: Formulate Workflow Plan with Context Delta and Router Selection
        workflow_id, plan = self.formulate_workflow_plan(
            idea_text=idea_text,
            idea_type=idea_type,
            context_delta=curation,
            correlation_id=correlation_id,
        )

        print(f"\n=======================================================")
        print(f"👑 CHIEF COMMANDER: Ingested Human {idea_type}")
        print(f"   Idea: {idea_text}")
        print(f"   Curation Classification: {curation['classification']}")
        print(f"   Context Delta Propagated: ID {curation['idea_id']} (Links: {len(curation.get('memory_references', []))})")
        print(f"   Workflow: {workflow_id} ({len(plan)} Planned Steps)")
        for i, step in enumerate(plan, 1):
            print(f"   Step {i}: [{step['target_agent'].upper()}] {step['instruction'][:60]}... (Reason: {step['routing_reason']})")
        if dry_run:
            print(f"   [DRY RUN] Routing decision completed without executing production tasks.")
        print(f"=======================================================")

        if dry_run:
            return {
                "status": "ROUTED_DRY_RUN",
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "curation": curation,
                "workflow_plan": plan,
                "history": [],
            }

        # Update Chief Visual State
        self.chief_state_tracker.update_state(
            state="RUNNING",
            task=f"Orchestrating {workflow_id}",
            progress=0.0,
            workflow=workflow_id,
            last_action=f"Ingested human {idea_type.lower()}: {idea_text[:60]} (Curation: {curation['classification']})",
            next_action=f"Dispatching Round 1 to {plan[0]['target_agent']}",
            blocked=False,
            human_gate=None,
            correlation_id=correlation_id,
        )

        # Run multi-round autonomous loop
        result = self.loop_engine.run_multi_round_workflow(
            workflow_id=workflow_id,
            workflow_plan=plan,
            correlation_id=correlation_id,
        )

        # Final Chief State Update
        final_state = "COMPLETED" if result["status"] == "COMPLETED" else result["status"]
        self.chief_state_tracker.update_state(
            state=final_state,
            task=f"Completed {workflow_id}" if final_state == "COMPLETED" else f"Paused {workflow_id}",
            progress=1.0 if final_state == "COMPLETED" else 0.5,
            workflow=workflow_id,
            last_action=f"Workflow {workflow_id} concluded with status: {result['status']}",
            next_action="Standby for next human directive",
            result=result["history"][-1]["result_file"] if result["history"] else None,
            blocked=result["status"] in ["BLOCKED_HUMAN_GATE", "BLOCKED_POLICY_CONFLICT"],
            human_gate="REQUIRE_EXPLICIT_HUMAN_APPROVAL" if result["status"] in ["BLOCKED_HUMAN_GATE", "BLOCKED_POLICY_CONFLICT"] else None,
            correlation_id=correlation_id,
        )

        return result


def main():
    parser = argparse.ArgumentParser(description="Run Autonomous Chief Commander")
    parser.add_argument("--idea", type=str, required=True, help="Human idea, goal, or strategic thought")
    parser.add_argument("--type", type=str, default="IDEA", choices=["IDEA", "GOAL", "STRATEGY", "PRIORITY"], help="Input classification")
    args = parser.parse_args()

    chief = ChiefCommander()
    res = chief.execute_human_idea(args.idea, args.type)
    print("\n=== CHIEF EXECUTION SUMMARY ===")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
