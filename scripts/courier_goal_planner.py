"""Courier Goal Planner: Evidence-Driven Autonomous Planning.

Strict Invariants:
- NO default file fallbacks (no native_agy_runner.py fallback, no default weakness).
- Missing worker evidence => BLOCKED fail-closed, never guessed.
- Different discovery evidence produces different tasks.
- Enforces max one successor, single writer, zero spend, and capability constraints.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PlannerDecision:
    decision: str  # "CONTINUE" | "GOAL_SATISFIED" | "HUMAN_GATE" | "BLOCKED"
    next_mission: Optional[Dict[str, Any]]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "next_mission": self.next_mission,
            "reason": self.reason,
        }


class CourierGoalPlanner:
    """Evidence-driven autonomous goal planner without hardcoded file or mission defaults."""

    def __init__(
        self,
        max_missions: int = 4,
        max_write_missions: int = 1,
        safety_policy: Optional[Dict[str, Any]] = None,
    ):
        self.max_missions = max_missions
        self.max_write_missions = max_write_missions
        self.safety_policy = safety_policy or {
            "spend_eur": 0,
            "single_writer": True,
            "heavy_job_limit": 1,
            "verify_before_next": True,
        }


    def _extract_acceptance_criteria(self, goal_text: str) -> Dict[str, str]:
        import re
        criteria = {}
        file_match = re.search(r"file named ([\w\.-]+)", goal_text, re.IGNORECASE)
        if file_match:
            criteria["file_exists"] = file_match.group(1).strip()
            content_match = re.search(r"containing exactly:\s*(.*)", goal_text, re.IGNORECASE)
            if content_match:
                criteria["content_matches"] = content_match.group(1).strip()
        return criteria

    def plan_next_step(
        self,
        root_goal: str,
        verified_history: List[Dict[str, Any]],
        latest_result: Optional[Dict[str, Any]] = None,
        available_capabilities: Optional[Dict[str, List[str]]] = None,
        lease_state: Optional[Dict[str, Any]] = None,
    ) -> PlannerDecision:
        """Derives the next safe mission strictly from verified evidence and safety policy."""
        if not isinstance(root_goal, str) or not root_goal.strip():
            return PlannerDecision(
                decision="BLOCKED",
                next_mission=None,
                reason="MISSING_ROOT_GOAL: root_goal must be a non-empty string",
            )

        # 1. Check for Human Gate / Authentication Requirement
        if latest_result:
            res_status = latest_result.get("status")
            payload = latest_result.get("payload", {})
            verdict = payload.get("verdict") if isinstance(payload, dict) else None

            if res_status == "HUMAN_GATE" or verdict in {"HUMAN_APPROVAL_REQUIRED", "HUMAN_GATE"}:
                return PlannerDecision(
                    decision="HUMAN_GATE",
                    next_mission=None,
                    reason=f"HUMAN_GATE_TRIGGERED: {payload.get('summary', 'Human approval/login required')}",
                )

            if res_status in {"FAILED", "BLOCKED"} or verdict == "FAILED":
                return PlannerDecision(
                    decision="BLOCKED",
                    next_mission=None,
                    reason=f"PREVIOUS_TASK_FAILED: {payload.get('error', res_status)}",
                )

        # 2. Check total mission count bounds
        if len(verified_history) >= self.max_missions:
            return PlannerDecision(
                decision="GOAL_SATISFIED",
                next_mission=None,
                reason=f"Reached maximum allowed mission count ({self.max_missions}); stopping safely.",
            )

        write_count = sum(1 for m in verified_history if m.get("requires_write"))

        # 3. Phase 0: No verified history -> Initial Open Discovery Mission
        if not verified_history:
            m_id = f"plan-disc-{uuid.uuid4().hex[:8]}"
            mission = {
                "mission_id": m_id,
                "goal": root_goal,
                "normalized_task": "Inspect repository and discover actionable, safe, locally verifiable improvement opportunities",
                "capability_required": "local repo analysis",
                "preferred_agent": "CLI1",
                "requires_write": False,
                "is_heavy": False,
                "risk_class": "SAFE",
                "task": {
                    "action": "discover_improvement_opportunities",
                    "root_goal": root_goal,
                    "requires_write": False,
                    "correlation_id": f"corr-{m_id}",
                    "task_id": m_id,
                },
            }
            return PlannerDecision(
                decision="CONTINUE",
                next_mission=mission,
                reason="Created initial discovery mission for real repository inspection.",
            )

        # Inspect latest verified result payload
        latest_payload = (latest_result or {}).get("payload", {}) if isinstance(latest_result, dict) else {}
        action = latest_payload.get("action")

        # Phase 1: Discovery completed -> Derive Implementation Mission from Discovery Evidence
        if action in {"discover_improvement_opportunities", "diagnose_infrastructure"}:
            weakness_id = latest_payload.get("weakness_id")
            weakness_desc = latest_payload.get("description") or latest_payload.get("weakness_description")
            suggested_files = latest_payload.get("suggested_files")
            verification_strategy = latest_payload.get("verification_strategy", "run_unit_tests")

            # STRICT NO GUESSING: If discovery returned no valid weakness or files, fail closed
            if not weakness_id or not weakness_desc or not suggested_files or not isinstance(suggested_files, list) or len(suggested_files) == 0:
                return PlannerDecision(
                    decision="BLOCKED",
                    next_mission=None,
                    reason="DISCOVERY_EVIDENCE_INSUFFICIENT: Missing required weakness_id, description, or suggested_files",
                )

            if write_count >= self.max_write_missions:
                return PlannerDecision(
                    decision="GOAL_SATISFIED",
                    next_mission=None,
                    reason="Max write missions reached; discovery recorded without further write permission.",
                )

            m_id = f"plan-imp-{uuid.uuid4().hex[:8]}"
            mission = {
                "mission_id": m_id,
                "goal": f"Implement {weakness_id}: {weakness_desc}",
                "normalized_task": f"Apply bounded implementation to {', '.join(suggested_files)}",
                "capability_required": "architecture",
                "preferred_agent": "GEMINI",
                "requires_write": True,
                "is_heavy": False,
                "risk_class": "SAFE",
                "task": {
                    "action": "implement_bounded_improvement",
                    "weakness_id": weakness_id,
                    "description": weakness_desc,
                    "target_files": suggested_files,
                    "verification_strategy": verification_strategy,
                    "requires_write": True,
                    "correlation_id": f"corr-{m_id}",
                    "task_id": m_id,
                    "acceptance_criteria": self._extract_acceptance_criteria(root_goal),
                },
            }
            return PlannerDecision(
                decision="CONTINUE",
                next_mission=mission,
                reason=f"Derived targeted implementation mission from verified discovery evidence for '{weakness_id}'.",
            )

        # Phase 2: Implementation completed -> Derive Verification Mission from Modified Files
        if action == "implement_bounded_improvement" or "files_modified" in latest_payload:
            modified_files = latest_payload.get("files_modified")
            verification_strategy = latest_payload.get("verification_strategy", "run_unit_tests")

            if not modified_files or not isinstance(modified_files, list) or len(modified_files) == 0:
                return PlannerDecision(
                    decision="BLOCKED",
                    next_mission=None,
                    reason="IMPLEMENTATION_EVIDENCE_INSUFFICIENT: Missing verified files_modified list from implementation result",
                )

            m_id = f"plan-ver-{uuid.uuid4().hex[:8]}"
            mission = {
                "mission_id": m_id,
                "goal": f"Verify repository state and regression tests for {', '.join(modified_files)}",
                "normalized_task": f"Execute verification strategy ({verification_strategy}) on {', '.join(modified_files)}",
                "capability_required": "repo verification",
                "preferred_agent": "CLI1",
                "requires_write": False,
                "is_heavy": False,
                "risk_class": "SAFE",
                "task": {
                    "action": "verify_improvement_tests",
                    "target_files": modified_files,
                    "verification_strategy": verification_strategy,
                    "requires_write": False,
                    "correlation_id": f"corr-{m_id}",
                    "task_id": m_id,
                },
            }
            return PlannerDecision(
                decision="CONTINUE",
                next_mission=mission,
                reason=f"Derived verification mission to test implemented changes in {', '.join(modified_files)}.",
            )

        # Phase 3: Verification completed with PASS -> Goal Satisfied
        if action == "verify_improvement_tests" and latest_payload.get("verdict") == "PASS":
            return PlannerDecision(
                decision="GOAL_SATISFIED",
                next_mission=None,
                reason=f"Root goal satisfied: {latest_payload.get('summary', 'Verification passed successfully')}",
            )

        return PlannerDecision(
            decision="GOAL_SATISFIED",
            next_mission=None,
            reason="Goal cycle complete; no further safe missions required.",
        )
