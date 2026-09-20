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
    ReviewBudgetManager = None
    ResourceIntelligenceManager = None
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
    
    




from dataclasses import dataclass, field, asdict


def save_json_atomic(path: Path, data: dict) -> None:
    """Durably persist Chief decisions without exposing a partial JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}.{uuid.uuid4().hex[:6]}")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@dataclass
class ChiefDecisionContract:
    schema_version: str = "2.0"
    chief_decision_id: str = ""
    conversation_id: str = "c61b931a-e4f1-476d-b9d2-431218079df5"
    chief_turn_id: str = ""
    workflow_id: str = ""
    task_id: str = ""
    correlation_id: str = ""
    result_id: str = ""
    decision: str = "COMPLETE"  # Allowed: CONTINUE, ACCEPT, RETRY_SAFE, HANDOFF, REVIEW_REQUIRED, WAIT_FOR_HUMAN, COMPLETE, PAUSE
    next_task: dict | None = None
    risk_level: str = "LOW"
    cost_class: str = "ZERO_COST_LOCAL"
    review_decision: str = "NO_REVIEW"
    value_gate: dict = field(default_factory=dict)
    reason: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.chief_decision_id:
            self.chief_decision_id = f"dec-chief-{uuid.uuid4().hex[:10]}"
        if not self.chief_turn_id:
            self.chief_turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        if not self.created_at:
            self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        allowed_decisions = {
            "CONTINUE", "ACCEPT", "RETRY_SAFE", "HANDOFF",
            "REVIEW_REQUIRED", "WAIT_FOR_HUMAN", "COMPLETE", "PAUSE"
        }
        if self.decision not in allowed_decisions:
            raise ValueError(f"Invalid Chief decision '{self.decision}'. Must be one of {allowed_decisions}")

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_value_gate(result_payload: dict, task_desc: str = "") -> dict:
    """Evaluates whether a task result creates real information or advances production."""
    creates_new_info = bool(result_payload.get("data") or result_payload.get("output") or result_payload.get("metrics") or result_payload.get("summary"))
    fixes_problem = bool(result_payload.get("fixed_defects") or result_payload.get("repaired"))
    advances_prod = bool(result_payload.get("verdict") in ("PASS", "ACCEPTED", "SUCCESS") or result_payload.get("status") in ("COMPLETED", "READY"))
    reduces_risk = bool(result_payload.get("risk_reduced") or result_payload.get("lint_passed") or result_payload.get("tests_passed"))
    testable_benefit = bool(result_payload.get("testable_artifact") or result_payload.get("verified_file") or creates_new_info or advances_prod)

    # If explicitly flagged as zero-value or noop
    if result_payload.get("is_noop") or result_payload.get("zero_value"):
        creates_new_info = False
        fixes_problem = False
        advances_prod = False
        reduces_risk = False
        testable_benefit = False

    passed = any([creates_new_info, fixes_problem, advances_prod, reduces_risk, testable_benefit])
    return {
        "creates_new_information": creates_new_info,
        "fixes_verified_problem": fixes_problem,
        "advances_production": advances_prod,
        "reduces_risk_cost": reduces_risk,
        "testable_benefit": testable_benefit,
        "passed": passed,
    }


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
        self.resource_intelligence = None
        self.chief_state_tracker = AntigravityVisualStateTracker(
            agent_id="agent-chief-commander",
            name="Chief Commander",
            role="Autonomous Orchestration & Review",
            repo_dir=repo_dir,
        )

    def resource_context(self) -> dict:
        """Compact canonical capacity references for Chief decisions only."""
        return {} if not self.resource_intelligence else self.resource_intelligence.context_for_role("CHIEF_COMMANDER")

    def set_presence(self, presence_state: str, session_id: str | None = None) -> dict:
        """Sets persistent Chief presence (AWAKE, SLEEPING, VACATION) and updates visual tracking."""
        allowed = {"AWAKE", "SLEEPING", "VACATION"}
        if presence_state not in allowed:
            raise ValueError(f"Invalid presence state '{presence_state}'. Must be one of {allowed}")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        presence_file = self.repo_dir / "events/chief_presence.json"
        presence_data = {
            "schema_version": "2.0",
            "presence": presence_state,
            "session_id": session_id,
            "updated_at": now_iso,
        }
        save_json(presence_file, presence_data)

        if presence_state == "SLEEPING":
            self.chief_state_tracker.update_state(
                state="SLEEPING",
                task="Resting (Zzz...)",
                progress=1.0,
                position_hint="fireplace",
                workflow="NIGHT_AUTOPILOT",
                last_action="Chief is resting. Autonomous night loop active.",
                next_action="Zzz...",
                blocked=False,
            )
        elif presence_state == "AWAKE":
            self.chief_state_tracker.update_state(
                state="IDLE",
                task="Command & Strategy",
                progress=0.0,
                position_hint="command_table",
                workflow=None,
                last_action="Chief is awake and monitoring operations.",
                next_action="Standby for human directive",
                blocked=False,
            )

        return presence_data

    def get_presence(self) -> dict:
        """Reads the durable Chief presence record."""
        presence_file = self.repo_dir / "events/chief_presence.json"
        if not presence_file.exists():
            return {
                "schema_version": "2.0",
                "presence": "AWAKE",
                "session_id": None,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        data = load_json(presence_file)
        if data and "presence" in data:
            return data
        return {
            "schema_version": "2.0",
            "presence": "AWAKE",
            "session_id": None,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    def log_night_journal(self, session_id: str, entry: dict) -> Path:
        """Appends an atomic JSON entry to the session's night journal."""
        journal_dir = self.repo_dir / "events/night-journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / f"journal-{session_id}.jsonl"

        entry_record = dict(entry)
        if "timestamp" not in entry_record:
            entry_record["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if "chief_presence" not in entry_record:
            entry_record["chief_presence"] = self.get_presence().get("presence", "SLEEPING")

        with open(journal_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_record) + "\n")

        return journal_file

    def evaluate_result_and_decide(
        self,
        task_id: str,
        correlation_id: str,
        workflow_id: str,
        result_file: Path,
        workflow_plan: list[dict] | None = None,
        round_index: int = 0,
        conversation_id: str = "c61b931a-e4f1-476d-b9d2-431218079df5",
        chief_turn_id: str | None = None,
    ) -> ChiefDecisionContract:
        """Evaluates a completed worker result and produces a persisted ChiefDecisionContract."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result_data = load_json(result_file)
        payload = result_data.get("payload", {})
        verdict = payload.get("verdict", "PASS")
        result_id = result_data.get("result_id") or result_file.name

        # 1. Evaluate Value Gate
        value_gate_res = evaluate_value_gate(payload)

        # 2. Evaluate Review Budget
        review_decision = "NO_REVIEW"
        try:
            rb_mgr = ReviewBudgetManager(self.repo_dir)
            review_eval = rb_mgr.evaluate_review_requirement(
                task_id=task_id,
                task_instruction=result_data.get("instruction", ""),
                target_agent=result_data.get("source", "antigravity"),
                diff_files=payload.get("modified_files", []),
            )
            review_decision = review_eval.get("decision", "NO_REVIEW")
        except Exception:
            review_decision = "NO_REVIEW"

        # 3. Check for Human Approval Gate Requirement
        if payload.get("requires_human_approval") or payload.get("human_gate_required") or verdict in ["HUMAN_GATE", "HUMAN_APPROVAL_REQUIRED"]:
            approvals_dir = self.repo_dir / "events/approvals"
            approval_event = None
            if approvals_dir.exists():
                for af in sorted(approvals_dir.glob("*.json"), reverse=True):
                    try:
                        ad = load_json(af)
                        if ad.get("workflow_id") == workflow_id and (ad.get("task_id") == task_id or ad.get("correlation_id") == correlation_id):
                            approval_event = ad
                            break
                    except Exception:
                        pass

            if approval_event:
                if approval_event.get("decision") == "APPROVE" or approval_event.get("action") == "APPROVE":
                    verdict = "ACCEPTED"
                else:
                    decision_obj = ChiefDecisionContract(
                        conversation_id=conversation_id,
                        chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                        workflow_id=workflow_id,
                        task_id=task_id,
                        correlation_id=correlation_id,
                        result_id=result_id,
                        decision="COMPLETE",
                        next_task=None,
                        risk_level="HIGH",
                        cost_class="ZERO_COST_LOCAL",
                        review_decision=review_decision,
                        value_gate=value_gate_res,
                        reason=f"Rejected by human operator: {approval_event.get('reason', 'None')}",
                        evidence_refs=[str(result_file.name)],
                        created_at=now_iso,
                    )
                    self._persist_decision(task_id, decision_obj)
                    return decision_obj
            else:
                decision_obj = ChiefDecisionContract(
                    conversation_id=conversation_id,
                    chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                    workflow_id=workflow_id,
                    task_id=task_id,
                    correlation_id=correlation_id,
                    result_id=result_id,
                    decision="WAIT_FOR_HUMAN",
                    next_task=None,
                    risk_level="HIGH",
                    cost_class="ZERO_COST_LOCAL",
                    review_decision=review_decision,
                    value_gate=value_gate_res,
                    reason="Task payload flagged for explicit human approval before advancing.",
                    evidence_refs=[str(result_file.name)],
                    created_at=now_iso,
                )
                self._persist_decision(task_id, decision_obj)
                return decision_obj

        # 4. Handle Needs Fix / Retry
        if verdict == "NEEDS_FIX":
            repair_task = {
                "task_id": f"{workflow_id}-REPAIR-{round_index + 1}",
                "instruction": f"Fix defects reported in {task_id}",
                "allowed_scope": payload.get("target_files", ["config/local_tools.json"]),
                "target_agent": result_data.get("source", "antigravity"),
                "cost_class": "ZERO_COST_LOCAL",
                "risk_level": "MEDIUM",
            }
            decision_obj = ChiefDecisionContract(
                conversation_id=conversation_id,
                chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                task_id=task_id,
                correlation_id=correlation_id,
                result_id=result_id,
                decision="RETRY_SAFE",
                next_task=repair_task,
                risk_level="MEDIUM",
                cost_class="ZERO_COST_LOCAL",
                review_decision=review_decision,
                value_gate=value_gate_res,
                reason="QA verification failed; repair task dispatched.",
                evidence_refs=[str(result_file.name)],
                created_at=now_iso,
            )
            self._persist_decision(task_id, decision_obj)
            return decision_obj

        # 5. Handle Review Required
        if review_decision in ("IMMEDIATE_REVIEW_REQUIRED", "REVIEW_REQUIRED_BEFORE_PUSH"):
            review_task = {
                "task_id": f"{workflow_id}-REVIEW-{round_index + 1}",
                "instruction": f"Perform independent technical QA review on {task_id} delta",
                "allowed_scope": payload.get("target_files", ["config/local_tools.json"]),
                "target_agent": "codex",
                "cost_class": "ZERO_COST_LOCAL",
                "risk_level": "HIGH",
            }
            decision_obj = ChiefDecisionContract(
                conversation_id=conversation_id,
                chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                task_id=task_id,
                correlation_id=correlation_id,
                result_id=result_id,
                decision="REVIEW_REQUIRED",
                next_task=review_task,
                risk_level="HIGH",
                cost_class="ZERO_COST_LOCAL",
                review_decision=review_decision,
                value_gate=value_gate_res,
                reason="Review Budget flagged change as requiring independent Codex review.",
                evidence_refs=[str(result_file.name)],
                created_at=now_iso,
            )
            self._persist_decision(task_id, decision_obj)
            return decision_obj

        # 6. Handle Pass & Check Next Task
        next_task_info = None
        if workflow_plan and (round_index + 1) < len(workflow_plan):
            next_step = workflow_plan[round_index + 1]
            next_task_info = {
                "task_id": next_step.get("task_id", f"{workflow_id}-round-{round_index + 2}"),
                "instruction": next_step.get("instruction", "Execute next step"),
                "allowed_scope": next_step.get("allowed_scope", []),
                "target_agent": next_step.get("target_agent", "antigravity"),
                "payload_override": next_step.get("payload_override"),
                "cost_class": next_step.get("cost_class", "ZERO_COST_LOCAL"),
                "risk_level": next_step.get("risk_level", "LOW"),
            }

        # Value Gate check: If Value Gate fails and there is no explicit planned next task, complete
        if not value_gate_res["passed"] and not next_task_info:
            decision_obj = ChiefDecisionContract(
                conversation_id=conversation_id,
                chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                task_id=task_id,
                correlation_id=correlation_id,
                result_id=result_id,
                decision="COMPLETE",
                next_task=None,
                risk_level="LOW",
                cost_class="ZERO_COST_LOCAL",
                review_decision=review_decision,
                value_gate=value_gate_res,
                reason="Value Gate indicates zero additional information gain; completing workflow.",
                evidence_refs=[str(result_file.name)],
                created_at=now_iso,
            )
            self._persist_decision(task_id, decision_obj)
            return decision_obj

        if next_task_info:
            decision_obj = ChiefDecisionContract(
                conversation_id=conversation_id,
                chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                task_id=task_id,
                correlation_id=correlation_id,
                result_id=result_id,
                decision="CONTINUE",
                next_task=next_task_info,
                risk_level=next_task_info.get("risk_level", "LOW"),
                cost_class=next_task_info.get("cost_class", "ZERO_COST_LOCAL"),
                review_decision=review_decision,
                value_gate=value_gate_res,
                reason=f"Step {round_index + 1} passed; automatically continuing to {next_task_info['task_id']}.",
                evidence_refs=[str(result_file.name)],
                created_at=now_iso,
            )
        else:
            decision_obj = ChiefDecisionContract(
                conversation_id=conversation_id,
                chief_turn_id=chief_turn_id or f"turn-{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                task_id=task_id,
                correlation_id=correlation_id,
                result_id=result_id,
                decision="COMPLETE",
                next_task=None,
                risk_level="LOW",
                cost_class="ZERO_COST_LOCAL",
                review_decision=review_decision,
                value_gate=value_gate_res,
                reason="All workflow plan steps successfully completed and accepted by Chief.",
                evidence_refs=[str(result_file.name)],
                created_at=now_iso,
            )

        self._persist_decision(task_id, decision_obj)
        return decision_obj

    def _persist_decision(self, task_id: str, decision: ChiefDecisionContract) -> Path:
        decision_dir = self.repo_dir / "events/chief-decisions"
        decision_dir.mkdir(parents=True, exist_ok=True)
        decision_file = decision_dir / f"{task_id}-chief-decision.json"
        save_json_atomic(decision_file, decision.to_dict())
        return decision_file

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
        save_json_atomic(decision_dir / f"{alert['message_id']}-chief-decision.json", decision)
        return decision


    def formulate_workflow_plan(
        self,
        idea_text: str,
        idea_type: str = "IDEA",
        context_delta: dict | None = None,
        correlation_id: str | None = None
    ) -> tuple[str, list[dict]]:
        """Converts a human idea and Context Delta into a multi-step bounded workflow plan using SmartResourceRouter."""
        import json
        import uuid
        workflow_id = f"WF-CHIEF-{uuid.uuid4().hex[:6]}"
        idea_lower = idea_text.lower()

        # Update Steward compiles snapshot
        snapshot = self.steward.generate_context_snapshot(context_delta=context_delta)

        # Support explicit JSON plans for generic testing without a full LLM pass
        if idea_text.strip().startswith("[") and idea_text.strip().endswith("]"):
            try:
                explicit_steps = json.loads(idea_text.strip())
                plan = []
                for i, step in enumerate(explicit_steps):
                    task_id = f"{workflow_id}-STEP-{i+1}"
                    s = {
                        "task_id": task_id,
                        "target_agent": step.get("target_agent", "antigravity"),
                        "instruction": step.get("instruction", "").replace("{task_id}", task_id),

                        "allowed_scope": step.get("allowed_scope", []),
                        "context_delta": context_delta,
                        "routing_reason": "Explicit goal parsing"
                    }
                    if "mode" in step:
                        s["mode"] = step["mode"]
                    if "artifacts" in step:
                        s["artifacts"] = step["artifacts"]
                    if "artifacts" in step:
                        s["artifacts"] = step["artifacts"]
                    self.steward.attach_task_context(s, snapshot)
                    plan.append(s)
                return workflow_id, plan
            except Exception as e:
                pass # fallback to generic 3-step

        # Step 1: Strategy & Discovery
        step1_desc = f"Formulate execution strategy and inspect context for: {idea_text}"

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
            step2_desc = f"Perform independent technical QA audit and syntax verification for: {idea_text}"
            step2_scope = ["config/local_tools.json"]
        else:
            step2_desc = f"Execute core implementation and asset validation for: {idea_text}"
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
        step3_desc = f"Finalize results, verify invariants, and assemble completion package for: {idea_text}"
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
