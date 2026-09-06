#!/usr/bin/env python3
"""Creator Factory Review Budget & Routing Gate.

Implements deterministic review-decision evaluation without invoking external models.
Adheres to the core invariants:
- MODEL_REVIEW_TRIGGER = INFORMATION_GAIN_NOT_TIME
- NO_CHANGE = NO_REVIEW
- SAME_DIFF_HASH = REUSE_PREVIOUS_REVIEW
- SAME_TEST_HASH + SAME_CODE_HASH = REUSE_PREVIOUS_RESULT
- LOW_RISK_MODEL_REVIEW = OPTIONAL_BATCHED
- MEDIUM_RISK_MODEL_REVIEW = BEFORE_MAIN_PUSH
- HIGH_RISK_MODEL_REVIEW = BEFORE_ACTIVATION
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from scripts.creator_work_planner import (
    RiskClass,
)


class ReviewDecision(str, enum.Enum):
    REVIEW_NOT_REQUIRED = "REVIEW_NOT_REQUIRED"
    REVIEW_REQUIRED_BEFORE_MAIN_PUSH = "REVIEW_REQUIRED_BEFORE_MAIN_PUSH"
    REVIEW_REQUIRED_BEFORE_ACTIVATION = "REVIEW_REQUIRED_BEFORE_ACTIVATION"
    REUSE_PREVIOUS_REVIEW = "REUSE_PREVIOUS_REVIEW"
    BATCH_FOR_LATER_REVIEW = "BATCH_FOR_LATER_REVIEW"
    UNKNOWN_BLOCK = "UNKNOWN_BLOCK"


@dataclass(frozen=True)
class ReviewEvaluationResult:
    """Deterministic result of review budget evaluation."""

    decision: str
    reason_code: str
    risk_class: str
    review_fingerprint: str
    reusable_fingerprint: str | None
    codex_calls_authorized: int  # Must remain 0 during planning

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreatorReviewGate:
    """Deterministic review gate routing decisions."""

    @classmethod
    def evaluate_review_requirement(
        cls,
        *,
        risk_class: str,
        code_hash: str = "",
        test_hash: str = "",
        diff_hash: str = "",
        policy_hash: str = "",
        previous_review_fingerprint: str | None = None,
        previous_code_hash: str | None = None,
        previous_test_hash: str | None = None,
        previous_diff_hash: str | None = None,
        affected_modules: list[str] | None = None,
        external_side_effect_class: str = "NONE",
        money_boundary: bool = False,
        security_boundary: bool = False,
        publication_boundary: bool = False,
    ) -> ReviewEvaluationResult:
        """Evaluate review requirement deterministically."""
        # Compute current review fingerprint
        raw_fp = f"{risk_class}:{code_hash}:{test_hash}:{diff_hash}:{policy_hash}:{external_side_effect_class}:{money_boundary}:{security_boundary}:{publication_boundary}"
        review_fingerprint = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:32]

        # 1. Check for UNKNOWN risk classification
        if risk_class not in {RiskClass.LOW.value, RiskClass.MEDIUM.value, RiskClass.HIGH.value}:
            return ReviewEvaluationResult(
                decision=ReviewDecision.UNKNOWN_BLOCK.value,
                reason_code="UNKNOWN_RISK_FAIL_CLOSED",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=None,
                codex_calls_authorized=0,
            )

        # 2. Critical Boundaries: Security, Money, Publication, or External Mutation
        if money_boundary or security_boundary or publication_boundary or external_side_effect_class == "MUTATION":
            return ReviewEvaluationResult(
                decision=ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value,
                reason_code="CRITICAL_BOUNDARY_REVIEW_REQUIRED",
                risk_class=RiskClass.HIGH.value,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=None,
                codex_calls_authorized=0,
            )

        # 3. Same code and test hash reuse
        if (
            previous_code_hash
            and previous_test_hash
            and code_hash == previous_code_hash
            and test_hash == previous_test_hash
        ):
            return ReviewEvaluationResult(
                decision=ReviewDecision.REUSE_PREVIOUS_REVIEW.value,
                reason_code="SAME_CODE_AND_TEST_HASH_REUSE",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=previous_review_fingerprint,
                codex_calls_authorized=0,
            )

        # 4. Same diff hash reuse
        if previous_diff_hash and diff_hash and diff_hash == previous_diff_hash:
            return ReviewEvaluationResult(
                decision=ReviewDecision.REUSE_PREVIOUS_REVIEW.value,
                reason_code="SAME_DIFF_HASH_REUSE",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=previous_review_fingerprint,
                codex_calls_authorized=0,
            )

        # 5. No changes detected
        if not code_hash and not diff_hash:
            return ReviewEvaluationResult(
                decision=ReviewDecision.REVIEW_NOT_REQUIRED.value,
                reason_code="NO_CHANGES_NO_REVIEW",
                risk_class=RiskClass.LOW.value,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=previous_review_fingerprint,
                codex_calls_authorized=0,
            )

        # 6. Risk-based routing
        if risk_class == RiskClass.LOW.value:
            return ReviewEvaluationResult(
                decision=ReviewDecision.REVIEW_NOT_REQUIRED.value,
                reason_code="LOW_RISK_OPTIONAL_BATCHED",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=None,
                codex_calls_authorized=0,
            )
        elif risk_class == RiskClass.MEDIUM.value:
            return ReviewEvaluationResult(
                decision=ReviewDecision.REVIEW_REQUIRED_BEFORE_MAIN_PUSH.value,
                reason_code="MEDIUM_RISK_BEFORE_MAIN_PUSH",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=None,
                codex_calls_authorized=0,
            )
        elif risk_class == RiskClass.HIGH.value:
            return ReviewEvaluationResult(
                decision=ReviewDecision.REVIEW_REQUIRED_BEFORE_ACTIVATION.value,
                reason_code="HIGH_RISK_BEFORE_ACTIVATION",
                risk_class=risk_class,
                review_fingerprint=review_fingerprint,
                reusable_fingerprint=None,
                codex_calls_authorized=0,
            )

        return ReviewEvaluationResult(
            decision=ReviewDecision.UNKNOWN_BLOCK.value,
            reason_code="UNKNOWN_ROUTING_FALLBACK",
            risk_class=risk_class,
            review_fingerprint=review_fingerprint,
            reusable_fingerprint=None,
            codex_calls_authorized=0,
        )
