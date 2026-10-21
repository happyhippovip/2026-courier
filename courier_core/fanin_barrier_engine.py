"""Fan-In Barrier, Mandatory Branch Gate & Superfluous Work Cancellation Engine (CP-25 / CQ-25 / GB-FANIN-01)

Durable Cannon Invariants:
1. Pflichtbarriere bleibt bestehen (Mandatory Barrier is Non-Negotiable):
   - Mandatory branch dependencies can NEVER be downgraded to optional to force early completion.
   - If any mandatory branch fails or remains unfulfilled, the goal fails closed (PASS_BLOCKED).
2. Fehlende optionale Evidenz wird ausgewiesen:
   - Non-critical/optional branches can be bypassed if the primary goal is met, but missing optional
     evidence is explicitly declared in the result manifest (no silent omission).
3. Abbruch überflüssiger ungestarteter Arbeit:
   - As soon as the terminal outcome is decided, pending unstarted tasks are cancelled to yield slots
     for cluster fairness.
4. Laufende Effekte werden nicht blind verworfen:
   - In-flight tasks with committed or pending external effects are gracefully bounded and awaited,
     never killed blindly without effect receipts.
5. Required Evidence:
   - dependency-contract, branch-policy, accepted-result.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class BranchCriticality(str, Enum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"


class BranchExecutionState(str, Enum):
    PENDING_UNSTARTED = "PENDING_UNSTARTED"
    IN_FLIGHT = "IN_FLIGHT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MandatoryBarrierViolationError(RuntimeError):
    """Raised when an attempt is made to claim success while mandatory branch criteria are missing."""


@dataclass(frozen=True)
class BranchSpecification:
    branch_id: str
    criticality: BranchCriticality
    effect_class: str  # "idempotent", "non_idempotent", "read_only"
    deliverable_name: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "criticality": self.criticality.value,
            "effect_class": self.effect_class,
            "deliverable_name": self.deliverable_name,
        }


@dataclass
class FanInGoalContract:
    goal_id: str
    project_id: str
    branches: Dict[str, BranchSpecification] = field(default_factory=dict)

    def add_branch(
        self,
        branch_id: str,
        criticality: BranchCriticality,
        effect_class: str = "idempotent",
        deliverable_name: str = "",
    ) -> None:
        self.branches[branch_id] = BranchSpecification(
            branch_id=branch_id,
            criticality=criticality,
            effect_class=effect_class,
            deliverable_name=deliverable_name or branch_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "project_id": self.project_id,
            "branches": {k: b.to_dict() for k, b in self.branches.items()},
        }


@dataclass
class TerminalFanInReceipt:
    goal_id: str
    passed: bool
    verdict: str  # "PASS", "FAIL_MANDATORY_UNFULFILLED"
    reason: str
    completed_mandatory_branches: List[str]
    unfulfilled_mandatory_branches: List[str]
    missing_optional_evidence: List[str]
    cancelled_superfluous_branches: List[str]
    gracefully_awaited_inflight_branches: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "passed": self.passed,
            "verdict": self.verdict,
            "reason": self.reason,
            "completed_mandatory_branches": sorted(self.completed_mandatory_branches),
            "unfulfilled_mandatory_branches": sorted(self.unfulfilled_mandatory_branches),
            "missing_optional_evidence": sorted(self.missing_optional_evidence),
            "cancelled_superfluous_branches": sorted(self.cancelled_superfluous_branches),
            "gracefully_awaited_inflight_branches": sorted(self.gracefully_awaited_inflight_branches),
        }


class FanInBarrierEngine:
    """Evaluates multi-branch completion, guards mandatory barriers, and cancels unstarted work safely."""

    def evaluate_terminal_fanin(
        self,
        goal: FanInGoalContract,
        branch_states: Dict[str, BranchExecutionState],
        inflight_has_effects: Optional[Dict[str, bool]] = None,
    ) -> TerminalFanInReceipt:
        has_effects = inflight_has_effects or {}

        completed_mandatory: List[str] = []
        unfulfilled_mandatory: List[str] = []
        missing_optional: List[str] = []
        cancelled_superfluous: List[str] = []
        gracefully_awaited: List[str] = []

        # 1. Audit all branches defined in goal contract
        for b_id, b_spec in goal.branches.items():
            state = branch_states.get(b_id, BranchExecutionState.PENDING_UNSTARTED)

            if b_spec.criticality == BranchCriticality.MANDATORY:
                if state == BranchExecutionState.COMPLETED:
                    completed_mandatory.append(b_id)
                else:
                    unfulfilled_mandatory.append(b_id)
            else:  # OPTIONAL
                if state != BranchExecutionState.COMPLETED:
                    missing_optional.append(b_id)

        # 2. Check Mandatory Barrier
        if unfulfilled_mandatory:
            # Goal fails closed; mandatory dependencies are never downgraded
            return TerminalFanInReceipt(
                goal_id=goal.goal_id,
                passed=False,
                verdict="FAIL_MANDATORY_UNFULFILLED",
                reason=f"Mandatory barrier unfulfilled: {sorted(unfulfilled_mandatory)} must complete before goal PASS.",
                completed_mandatory_branches=completed_mandatory,
                unfulfilled_mandatory_branches=unfulfilled_mandatory,
                missing_optional_evidence=missing_optional,
                cancelled_superfluous_branches=[],
                gracefully_awaited_inflight_branches=[],
            )

        # 3. All Mandatory Branches Met: Evaluate Superfluous / In-flight Branches
        for b_id, b_spec in goal.branches.items():
            state = branch_states.get(b_id, BranchExecutionState.PENDING_UNSTARTED)

            # Check unstarted work to cancel
            if state == BranchExecutionState.PENDING_UNSTARTED:
                cancelled_superfluous.append(b_id)

            # Check in-flight tasks: Do not blind-kill if active external effects exist
            elif state == BranchExecutionState.IN_FLIGHT:
                if has_effects.get(b_id, False):
                    gracefully_awaited.append(b_id)
                else:
                    cancelled_superfluous.append(b_id)

        return TerminalFanInReceipt(
            goal_id=goal.goal_id,
            passed=True,
            verdict="PASS",
            reason="All mandatory branches verified complete; optional evidence and surplus work audited.",
            completed_mandatory_branches=completed_mandatory,
            unfulfilled_mandatory_branches=[],
            missing_optional_evidence=missing_optional,
            cancelled_superfluous_branches=cancelled_superfluous,
            gracefully_awaited_inflight_branches=gracefully_awaited,
        )

    def generate_fanin_evidence(
        self,
        goal: FanInGoalContract,
        branch_states: Dict[str, BranchExecutionState],
        inflight_has_effects: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        """Generates CP-25 required evidence: ['dependency-contract', 'branch-policy', 'accepted-result']."""
        receipt = self.evaluate_terminal_fanin(goal, branch_states, inflight_has_effects)

        return {
            "required_evidence": ["dependency-contract", "branch-policy", "accepted-result"],
            "dependency-contract": goal.to_dict(),
            "branch-policy": {
                "mandatory_downgrade_allowed": False,
                "superfluous_unstarted_cancellation": True,
                "blind_kill_inflight_effects_prohibited": True,
                "fairness_slot_yield_enforced": True,
            },
            "accepted-result": receipt.to_dict(),
        }
