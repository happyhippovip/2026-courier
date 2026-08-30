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

# Import Level 6 Autonomous Engine & Bridge Components
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from run_autonomous_loop import AutonomousLevel6Loop
    from run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json
except ImportError:
    from scripts.run_autonomous_loop import AutonomousLevel6Loop
    from scripts.run_antigravity_bridge import AntigravityVisualStateTracker, load_json, save_json


class SmartResourceRouter:
    """Classifies tasks and routes work based on workload type and agent specializations."""

    @staticmethod
    def classify_and_route(task_desc: str, scope_files: list[str]) -> str:
        """Determines whether a task should be assigned to ANTIGRAVITY or CODEX."""
        desc_lower = task_desc.lower()
        scope_str = " ".join(scope_files).lower()

        # Keywords indicating scarce technical code review / unit test audits
        codex_triggers = [
            "code review", "syntax audit", "unit test verification", "lint check",
            "security audit", "independent qa verify", "strict schema test"
        ]

        # Check if explicitly an independent technical code check
        for trigger in codex_triggers:
            if trigger in desc_lower:
                return "codex"

        # Default to Antigravity as primary heavy worker for all creative, visual, media, planning, and broad implementation
        return "antigravity"


class ChiefCommander:
    """Autonomous Chief Commander that ingests human ideas and orchestrates multi-agent execution."""

    def __init__(self, repo_dir: Path = COURIER_DIR):
        self.repo_dir = repo_dir
        self.loop_engine = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=4)
        self.chief_state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-chief-commander",
            name="Chief Commander",
            role="Autonomous Orchestration & Review",
        )

    def formulate_workflow_plan(self, idea_text: str, idea_type: str = "IDEA", correlation_id: str | None = None) -> tuple[str, list[dict]]:
        """Converts a human idea into a multi-step bounded workflow plan."""
        workflow_id = f"WF-CHIEF-{uuid.uuid4().hex[:6]}"
        idea_lower = idea_text.lower()

        # Step 1: Initial Discovery / Context Review (Always Antigravity)
        plan = [
            {
                "task_id": f"{workflow_id}-STEP-1-DISCOVER",
                "target_agent": "antigravity",
                "instruction": f"Formulate execution strategy and inspect context for: {idea_text[:120]}",
                "allowed_scope": ["config/local_tools.json", "config/teamwork_policy.json"],
            }
        ]

        # Step 2: Implementation or Detailed Verification
        if "test" in idea_lower or "verify" in idea_lower or "audit" in idea_lower:
            # Use Codex for independent bounded QA check if explicitly technical
            plan.append({
                "task_id": f"{workflow_id}-STEP-2-QA-AUDIT",
                "target_agent": "codex",
                "instruction": f"Perform independent technical QA verification for: {idea_text[:120]}",
                "allowed_scope": ["config/local_tools.json"],
            })
        else:
            # Continue with Antigravity as primary heavy worker
            plan.append({
                "task_id": f"{workflow_id}-STEP-2-IMPLEMENT",
                "target_agent": "antigravity",
                "instruction": f"Execute core implementation and asset validation for: {idea_text[:120]}",
                "allowed_scope": ["config/social_channels.json", "config/teamwork_policy.json"],
            })

        # Step 3: Chief Synthesis & Final Acceptance (Antigravity)
        plan.append({
            "task_id": f"{workflow_id}-STEP-3-SYNTHESIZE",
            "target_agent": "antigravity",
            "instruction": f"Finalize results, verify invariants, and assemble completion package for: {idea_text[:120]}",
            "allowed_scope": ["config/teamwork_policy.json"],
        })

        return workflow_id, plan

    def execute_human_idea(self, idea_text: str, idea_type: str = "IDEA") -> dict:
        """Processes human input end-to-end through the autonomous Chief loop."""
        workflow_id, plan = self.formulate_workflow_plan(idea_text, idea_type)
        correlation_id = f"corr-chief-{uuid.uuid4().hex[:8]}"

        print(f"\n=======================================================")
        print(f"👑 CHIEF COMMANDER: Ingested Human {idea_type}")
        print(f"   Idea: {idea_text}")
        print(f"   Workflow: {workflow_id} ({len(plan)} Planned Steps)")
        print(f"=======================================================")

        # Update Chief Visual State
        self.chief_state_tracker.update_state(
            state="RUNNING",
            task=f"Orchestrating {workflow_id}",
            progress=0.0,
            workflow=workflow_id,
            last_action=f"Ingested human {idea_type.lower()}: {idea_text[:60]}",
            next_action="Dispatching Round 1 to primary worker",
            blocked=False,
            human_gate=None,
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
            blocked=result["status"] == "BLOCKED_HUMAN_GATE",
            human_gate="REQUIRE_EXPLICIT_HUMAN_APPROVAL" if result["status"] == "BLOCKED_HUMAN_GATE" else None,
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
