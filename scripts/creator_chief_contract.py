#!/usr/bin/env python3
"""Creator Factory Chief Return Contract.

Models deterministic, bounded result payloads returned from Worker -> Dispatcher -> Chief Commander.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass
from typing import Any

from scripts.autonomous_continuation_policy import (
    STRICTLY_PROHIBITED_ACTIONS,
)
from scripts.creator_review_gate import (
    ReviewDecision,
)
from scripts.creator_work_planner import (
    WorkPlan,
)
from scripts.creator_work_queue import (
    validate_finite_exact_zero,
)

CHIEF_CONTRACT_SCHEMA_VERSION = "1.0"


class ChiefResultStatus(str, enum.Enum):
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_EXTERNAL_REVIEW = "WAITING_EXTERNAL_REVIEW"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    PLATFORM_BOUNDARY = "PLATFORM_BOUNDARY"
    NO_USEFUL_NEW_WORK = "NO_USEFUL_NEW_WORK"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ChiefReturnContract:
    """Standardized result payload for Chief Commander."""

    schema_version: str
    task_id: str
    plan_id: str
    content_id: str
    result_status: str
    useful_work_completed: bool
    files_changed: list[str]
    tests_run: int
    tests_passed: int
    tests_failed: int
    state_hash_before: str
    state_hash_after: str
    review_decision: str
    human_gate: bool
    external_gate: bool
    money_spent_eur: float
    recommended_next_action: str
    prohibited_next_actions: list[str]
    evidence_references: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreatorChiefContractBuilder:
    """Builds proven return contracts for Chief Commander."""

    @classmethod
    def build_from_plan(
        cls,
        plan: WorkPlan,
        result_status: str,
        useful_work_completed: bool = False,
        files_changed: list[str] | None = None,
        tests_run: int = 0,
        tests_passed: int = 0,
        tests_failed: int = 0,
        state_hash_after: str | None = None,
        review_decision: str = ReviewDecision.REVIEW_NOT_REQUIRED.value,
        money_spent_eur: float = 0.0,
        recommended_next_action: str = "AWAIT_NEXT_INSTRUCTION",
    ) -> ChiefReturnContract:
        """Construct Chief return contract."""
        ok_money, _ = validate_finite_exact_zero(money_spent_eur)
        if not ok_money:
            raise ValueError(f"Invalid money spent: {money_spent_eur}")

        return ChiefReturnContract(
            schema_version=CHIEF_CONTRACT_SCHEMA_VERSION,
            task_id=plan.task_id,
            plan_id=plan.plan_id,
            content_id=plan.content_id,
            result_status=result_status,
            useful_work_completed=useful_work_completed,
            files_changed=sorted(list(files_changed or [])),
            tests_run=tests_run,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            state_hash_before=plan.source_state_hash,
            state_hash_after=state_hash_after or plan.source_state_hash,
            review_decision=review_decision,
            human_gate=plan.requires_human or plan.blocking_gate == "AUDIENCE_DECISION_GATE",
            external_gate=plan.requires_external_access,
            money_spent_eur=money_spent_eur,
            recommended_next_action=recommended_next_action,
            prohibited_next_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
            evidence_references=sorted(list(plan.evidence_references)),
        )
