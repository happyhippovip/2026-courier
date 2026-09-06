#!/usr/bin/env python3
"""Creator Factory Autonomous Continuation Policy.

Evaluates proposed creator operations and ready-work items to determine
what can safely proceed autonomously without Chief/Human involvement.
"""

from __future__ import annotations

import enum
from dataclasses import asdict, dataclass
from typing import Any

from scripts.creator_work_queue import (
    CreatorWorkQueueItem,
    QueueItemStatus,
    validate_finite_exact_zero,
)

POLICY_SCHEMA_VERSION = "1.0"


class PolicyDecision(str, enum.Enum):
    ALLOW_LOCAL = "ALLOW_LOCAL"
    DENY = "DENY"
    WAIT_HUMAN = "WAIT_HUMAN"
    WAIT_REVIEW = "WAIT_REVIEW"
    WAIT_EXTERNAL = "WAIT_EXTERNAL"
    UNKNOWN = "UNKNOWN"


PERMITTED_AUTONOMOUS_ACTIONS = {
    "ASSET_VALIDATION",
    "METADATA_LINTING",
    "LOCAL_QC_EXECUTION",
    "PREVIEW_GENERATION",
    "INVENTORY_REFRESH",
    "QUEUE_DEDUPLICATION",
    "PACKAGING_VERIFICATION",
    "PACKAGE_PREPARATION",
    "SOURCE_DISCOVERY",
    "PROPOSAL_PREPARATION",
}

STRICTLY_PROHIBITED_ACTIONS = {
    "AUDIENCE_CLASSIFICATION",
    "SET_PUBLICATION_AUTHORIZED_TRUE",
    "CREATE_REAL_APPROVAL_RECORD",
    "REAL_YOUTUBE_UPLOAD",
    "PUBLIC_RELEASE",
    "SPEND_MONEY",
    "SUBSCRIPTION_OR_CREDIT_CHANGE",
    "EXTERNAL_DESTRUCTIVE_OPERATIONS",
    "IDENTITY_OR_KYC_DECLARATIONS",
}


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Deterministic result of policy evaluation."""

    decision: str
    reason_code: str
    permitted_actions: list[str]
    prohibited_actions: list[str]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutonomousContinuationPolicyEngine:
    """Evaluates whether work may proceed autonomously."""

    @classmethod
    def evaluate_queue_item(cls, item: CreatorWorkQueueItem) -> PolicyEvaluationResult:
        """Evaluate a queue item against autonomous continuation rules."""
        # 1. Strict Money Gate check
        ok_money, money_code = validate_finite_exact_zero(item.money_limit_eur)
        if not ok_money:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="MONEY_POLICY_VIOLATION",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"money_limit_eur": item.money_limit_eur, "money_code": money_code},
            )

        # 2. External calls check
        if item.maximum_external_calls > 0:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="EXTERNAL_CALLS_PROHIBITED",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"maximum_external_calls": item.maximum_external_calls},
            )

        # 3. Check for explicitly prohibited actions
        if item.action_type in STRICTLY_PROHIBITED_ACTIONS:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="PROHIBITED_ACTION",
                permitted_actions=[],
                prohibited_actions=[item.action_type],
                details={"action_type": item.action_type},
            )

        # 4. Human gate check
        if item.requires_human or item.status == QueueItemStatus.WAITING_FOR_HUMAN_DECISION.value:
            return PolicyEvaluationResult(
                decision=PolicyDecision.WAIT_HUMAN.value,
                reason_code="HUMAN_GATE_REQUIRED",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"status": item.status, "action_type": item.action_type},
            )

        # 5. Independent review check
        if item.requires_independent_review or item.status == QueueItemStatus.WAITING_FOR_TECHNICAL_REVIEW.value:
            return PolicyEvaluationResult(
                decision=PolicyDecision.WAIT_REVIEW.value,
                reason_code="TECHNICAL_REVIEW_REQUIRED",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"status": item.status, "action_type": item.action_type},
            )

        # 6. External platform waiting check
        if item.status == QueueItemStatus.WAITING_FOR_EXTERNAL_PLATFORM.value:
            return PolicyEvaluationResult(
                decision=PolicyDecision.WAIT_EXTERNAL.value,
                reason_code="EXTERNAL_PLATFORM_WAIT",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"status": item.status},
            )

        # 7. Complete no action
        if item.status == QueueItemStatus.COMPLETE_NO_ACTION.value:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="COMPLETE_NO_ACTION_REQUIRED",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"status": item.status},
            )

        # 8. Permitted local autonomous work
        if (
            item.status == QueueItemStatus.READY_FOR_AUTONOMOUS_LOCAL_WORK.value
            and item.action_type in PERMITTED_AUTONOMOUS_ACTIONS
        ):
            return PolicyEvaluationResult(
                decision=PolicyDecision.ALLOW_LOCAL.value,
                reason_code="AUTONOMOUS_LOCAL_WORK_PERMITTED",
                permitted_actions=[item.action_type],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"action_type": item.action_type, "allowed_side_effects": item.allowed_side_effect_class},
            )

        # 9. Fail closed on unknown
        return PolicyEvaluationResult(
            decision=PolicyDecision.UNKNOWN.value,
            reason_code="UNPROVEN_STATE_OR_UNKNOWN_ACTION",
            permitted_actions=[],
            prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
            details={"action_type": item.action_type, "status": item.status},
        )

    @classmethod
    def evaluate_proposed_action(
        cls,
        action_name: str,
        target_content_id: str,
        cost_eur: Any = 0.0,
    ) -> PolicyEvaluationResult:
        """Evaluate a raw proposed action string."""
        ok_money, money_code = validate_finite_exact_zero(cost_eur)
        if not ok_money:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="MONEY_POLICY_VIOLATION",
                permitted_actions=[],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"cost_eur": cost_eur, "money_code": money_code},
            )

        if action_name in STRICTLY_PROHIBITED_ACTIONS:
            return PolicyEvaluationResult(
                decision=PolicyDecision.DENY.value,
                reason_code="PROHIBITED_ACTION",
                permitted_actions=[],
                prohibited_actions=[action_name],
                details={"action_name": action_name},
            )

        if action_name in PERMITTED_AUTONOMOUS_ACTIONS:
            return PolicyEvaluationResult(
                decision=PolicyDecision.ALLOW_LOCAL.value,
                reason_code="AUTONOMOUS_LOCAL_WORK_PERMITTED",
                permitted_actions=[action_name],
                prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
                details={"action_name": action_name, "content_id": target_content_id},
            )

        # Fail closed on any unknown action
        return PolicyEvaluationResult(
            decision=PolicyDecision.UNKNOWN.value,
            reason_code="UNKNOWN_ACTION_DENIED_BY_DEFAULT",
            permitted_actions=[],
            prohibited_actions=sorted(list(STRICTLY_PROHIBITED_ACTIONS)),
            details={"action_name": action_name},
        )
