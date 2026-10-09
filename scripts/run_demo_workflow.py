#!/usr/bin/env python3
"""2026 Courier // Autonomous Operations Visual Demo Workflow Runner.

Executes a complete, deterministic, zero-cost 13-stage live demonstration workflow:
HUMAN IDEA
→ IDEA SYNC (Thought Curator)
→ MEMORY COMPARISON (DECISIONS.md, IDEA_ARCHIVE.md, PROJECT_STATE.md)
→ CONTEXT DELTA (Truth Boundary, Sources Indexed, Target Recommendation)
→ CHIEF COMMANDER (Workflow Formulation)
→ SMART RESOURCE ROUTER (Antigravity Primary / Codex Quota Guard)
→ DETERMINISTIC ANTIGRAVITY WORKER (Job Execution)
→ RESULT_READY (Worker Result Payload)
→ CHIEF REVIEW (Review Router)
→ HUMAN GATE (HUMAN_APPROVAL_REQUIRED)
→ APPROVAL EVENT (Matching workflow_id & correlation_id)
→ RESUME (Next Task Dispatch)
→ COMPLETE (All Rounds Accepted)

All evidence is saved in an isolated local directory: events/demo/
"""

from __future__ import annotations

import argparse
import datetime
import json
import shutil
import sys
import time
import uuid
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR / "scripts"))

from run_thought_curator import ThoughtCurator
from run_chief_commander import ChiefCommander, SmartResourceRouter
from run_autonomous_loop import AutonomousLevel6Loop


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class DemoOrchestrator:
    """Orchestrates an isolated, deterministic live demonstration of the multi-agent operations loop."""

    def __init__(self, repo_dir: Path = REPO_DIR, evidence_dir: Path | None = None):
        self.repo_dir = repo_dir
        self.evidence_dir = evidence_dir or (repo_dir / "events/demo")
        self.curator = ThoughtCurator(repo_dir=repo_dir)
        self.chief = ChiefCommander(repo_dir=repo_dir)
        self.loop = AutonomousLevel6Loop(repo_dir=repo_dir, max_iterations=4)

    def reset_demo_environment(self) -> None:
        """Cleans isolated demo evidence directory and sets agent states to clean IDLE."""
        if self.evidence_dir.exists():
            shutil.rmtree(self.evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        (self.evidence_dir / "approvals").mkdir(parents=True, exist_ok=True)
        (self.evidence_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (self.evidence_dir / "results").mkdir(parents=True, exist_ok=True)
        (self.evidence_dir / "decisions").mkdir(parents=True, exist_ok=True)

        print(f"[DEMO RESET] Evidence directory reset at {self.evidence_dir}")

    def _read_recorded_human_gate(self, workflow_id: str, correlation_id: str) -> dict | None:
        """Return one approval already stored for this workflow. This method does not write one."""
        approvals_dir = self.repo_dir / "events/approvals"
        if not approvals_dir.is_dir():
            return None
        matches = []
        for path in sorted(approvals_dir.glob("*.json")):
            try:
                data = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("workflow_id") != workflow_id or data.get("correlation_id") != correlation_id:
                continue
            decision = data.get("decision") or data.get("action")
            if decision not in ("APPROVE", "REJECT"):
                continue
            if not isinstance(data.get("approval_id"), str) or not data["approval_id"]:
                continue
            matches.append(data)
        if len(matches) != 1:
            return None
        return matches[0]

    def run_live_demo(
        self,
        raw_idea: str = "Optimiere FruitKI 3D Video-Render Pipeline und erstelle Release-Metadaten",
        idea_type: str = "GOAL",
        correlation_id: str | None = None,
    ) -> dict:
        """Executes the demo. A human gate counts only when its approval file is already on disk."""
        demo_id = f"demo-{uuid.uuid4().hex[:8]}"
        if not correlation_id:
            correlation_id = f"corr-demo-{uuid.uuid4().hex[:8]}"
        start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

        print("\n=======================================================")
        print(f"🎬 STARTING AUTONOMOUS OPERATIONS LIVE DEMO: {demo_id}")
        print(f"   Correlation ID: {correlation_id}")
        print(f"   Human Input: '{raw_idea}' ({idea_type})")
        print("=======================================================")

        # STAGE 1 & 2: Human Idea Ingestion & Thought Curator Memory Indexing
        print("\n[STAGE 1 & 2] IDEA SYNC & MEMORY COMPARISON...")
        context_delta = self.curator.curate_idea(raw_idea, idea_type)
        idea_id = context_delta["idea_id"]
        save_json(self.evidence_dir / "context_delta.json", context_delta)
        print(f"   -> Idea ID: {idea_id} | Classification: {context_delta['classification']}")
        print(f"   -> Indexed Sources: {list(context_delta['sources_indexed'].keys())}")

        # STAGE 3 & 4: Chief Plan Formulation & Smart Resource Routing
        print("\n[STAGE 3 & 4] CHIEF PLAN FORMULATION & SMART RESOURCE ROUTER...")
        workflow_id, plan = self.chief.formulate_workflow_plan(
            idea_text=raw_idea,
            idea_type=idea_type,
            context_delta=context_delta,
            correlation_id=correlation_id,
        )
        save_json(self.evidence_dir / "workflow_plan.json", {"workflow_id": workflow_id, "plan": plan})
        print(f"   -> Workflow ID: {workflow_id} ({len(plan)} Steps Planned)")
        for idx, step in enumerate(plan, 1):
            print(f"      Step {idx}: [{step['target_agent'].upper()}] {step['task_id']} ({step['routing_reason']})")

        # Configure Step 1 to trigger the Human Approval Gate for demonstration
        plan[0]["payload_override"] = {
            "requires_human_approval": True,
            "verdict": "HUMAN_APPROVAL_REQUIRED",
        }

        # STAGE 5: Execute Round 1 with Antigravity Worker
        print("\n[STAGE 5] EXECUTING WORKER ROUND 1...")
        round1_res = self.loop.run_multi_round_workflow(
            workflow_id=workflow_id,
            workflow_plan=plan,
            correlation_id=correlation_id,
        )
        print(f"   -> Round 1 Result: Status={round1_res['status']} (Stop Reason={round1_res['stop_reason']})")
        assert round1_res["status"] == "BLOCKED_HUMAN_GATE", "Step 1 must pause at Human Gate!"

        # Copy worker job, result, and decision to isolated demo evidence
        step1_task = plan[0]["task_id"]
        for pattern, dest_subdir in [
            (f"{step1_task}-worker-job.json", "tasks"),
            (f"{step1_task}-result.json", "results"),
            (f"{step1_task}-chief-decision.json", "decisions"),
        ]:
            src_file = self.repo_dir / f"events/{'dispatch' if 'worker-job' in pattern else ('processed' if 'result' in pattern else 'chief-decisions')}" / pattern
            if src_file.exists():
                shutil.copy(src_file, self.evidence_dir / dest_subdir / pattern)

        recorded_gate = self._read_recorded_human_gate(workflow_id, correlation_id)
        gate_decision = None
        if recorded_gate is not None:
            gate_decision = recorded_gate.get("decision") or recorded_gate.get("action")

        resume_res = None
        if gate_decision == "APPROVE":
            print(f"\n[STAGE 6] Recorded human gate read back: {recorded_gate['approval_id']}")
            print("\n[STAGE 7] WORKFLOW RESUMPTION...")
            resume_res = self.loop.resume_workflow(
                workflow_id=workflow_id,
                correlation_id=correlation_id,
                workflow_plan=plan,
                from_round_index=1,
            )
            print(f"   -> Resume Execution Result: Status={resume_res['status']} (Stop Reason={resume_res['stop_reason']})")
            if resume_res.get("status") == "COMPLETED":
                for step in plan[1:]:
                    st_task = step["task_id"]
                    for pattern, dest_subdir in [
                        (f"{st_task}-worker-job.json", "tasks"),
                        (f"{st_task}-result.json", "results"),
                        (f"{st_task}-chief-decision.json", "decisions"),
                    ]:
                        src_file = self.repo_dir / f"events/{'dispatch' if 'worker-job' in pattern else ('processed' if 'result' in pattern else 'chief-decisions')}" / pattern
                        if src_file.exists():
                            shutil.copy(src_file, self.evidence_dir / dest_subdir / pattern)
        else:
            print("\n[STAGE 6] No recorded human gate. Not reporting success.")

        completed = gate_decision == "APPROVE" and resume_res is not None and resume_res.get("status") == "COMPLETED"
        status = "COMPLETED" if completed else "BLOCKED_HUMAN_GATE"
        history_rounds = len(round1_res["history"])
        if resume_res is not None:
            history_rounds += len(resume_res["history"])
        manifest = {
            "schema_version": "2.0",
            "demo_id": demo_id,
            "created_at": start_time,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": status,
            "human_input": {
                "raw_idea": raw_idea,
                "type": idea_type,
                "idea_id": idea_id,
            },
            "context_delta": context_delta,
            "workflow": {
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "plan": plan,
            },
            "human_gate": {
                "approval_id": recorded_gate.get("approval_id") if recorded_gate else None,
                "decision": gate_decision or "NOT_RECORDED",
                "read_back": recorded_gate is not None,
            },
            "execution_summary": {
                "total_rounds": history_rounds,
                "final_verdict": "ACCEPTED" if completed else "NOT_RECORDED",
                "final_status": status,
                "costs_eur": 0.0,
                "model_calls": 0,
            },
            "isolation_verified": False,
            "truth_boundaries_verified": False,
        }

        save_json(self.evidence_dir / "demo_evidence_manifest.json", manifest)

        print(f"   Evidence Manifest written to: {self.evidence_dir}/demo_evidence_manifest.json")
        if completed:
            print("\n=======================================================")
            print(f"✅ LIVE DEMO COMPLETED SUCCESSFULLY: {manifest['status']}")
            print("=======================================================\n")
        return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Live Studio Demo Workflow")
    parser.add_argument("--reset", action="store_true", help="Reset isolated demo evidence directory before running")
    parser.add_argument("--idea", type=str, default="Optimiere FruitKI 3D Video-Render Pipeline und erstelle Release-Metadaten", help="Human input text")
    parser.add_argument("--type", type=str, default="GOAL", help="Idea type (GOAL, IDEA, TASK)")
    args = parser.parse_args()

    orchestrator = DemoOrchestrator()
    if args.reset:
        orchestrator.reset_demo_environment()

    manifest = orchestrator.run_live_demo(raw_idea=args.idea, idea_type=args.type)
    return 0 if manifest["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
