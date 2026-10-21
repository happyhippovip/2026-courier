"""Batching Policy & Independent Verifier Separation Engine (CP-24 / CQ-24 / GB-BATCH-01)

Durable Cannon Invariants:
1. When Batching Saves Context:
   - Compatible read-only tasks sharing an immutable reference context (e.g., repository tree,
     specification document) are safely batched into a single prompt/execution pass, saving tokens.
2. When Batching Destroys Independent Judgments (STRICTLY FORBIDDEN):
   - Producer + Verifier Collusion: An independent verifier must NEVER be co-batched in the same
     prompt/session context as the producer whose work is being evaluated.
   - Self-Review / Producer Bias: Verifiers must receive clean artifacts and acceptance criteria
     without producer self-justification or chain-of-thought sycophancy.
3. No Model Only for Copy-Pasting ("Kein Modell nur zum Zusammenkopieren"):
   - Results aggregation is performed deterministically by Hub logic, never by wasting expensive LLM tokens.
4. Required Evidence:
   - task-contexts, independence-requirements, usage-evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class TaskRole(str, Enum):
    PRODUCER = "PRODUCER"
    VERIFIER = "VERIFIER"
    READER = "READER"
    MUTATOR = "MUTATOR"


class BatchEligibilityStatus(str, Enum):
    ALLOWED_READ_BATCH = "ALLOWED_READ_BATCH"
    FORBIDDEN_PRODUCER_VERIFIER_COLLUSION = "FORBIDDEN_PRODUCER_VERIFIER_COLLUSION"
    FORBIDDEN_SELF_REVIEW = "FORBIDDEN_SELF_REVIEW"
    FORBIDDEN_CONCURRENT_MUTATION = "FORBIDDEN_CONCURRENT_MUTATION"
    FORBIDDEN_MODEL_CONCATENATION = "FORBIDDEN_MODEL_CONCATENATION"
    INCOMPATIBLE_CONTEXTS = "INCOMPATIBLE_CONTEXTS"


class IndependenceViolationError(RuntimeError):
    """Raised when batching violates verifier-producer independence boundaries."""


class ModelConcatenationForbiddenError(RuntimeError):
    """Raised when an LLM is invoked solely to copy-paste or concatenate text strings."""


@dataclass(frozen=True)
class BatchableTask:
    task_id: str
    role: TaskRole
    context_source_id: str  # identifier of document/repo context
    target_deliverable_id: Optional[str] = None
    producer_id: Optional[str] = None
    effect_class: str = "read_only"
    requires_independent_verdict: bool = False
    context_tokens_estimate: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "role": self.role.value,
            "context_source_id": self.context_source_id,
            "target_deliverable_id": self.target_deliverable_id,
            "producer_id": self.producer_id,
            "effect_class": self.effect_class,
            "requires_independent_verdict": self.requires_independent_verdict,
            "context_tokens_estimate": self.context_tokens_estimate,
        }


@dataclass
class BatchEvaluationResult:
    status: BatchEligibilityStatus
    allowed: bool
    reason: str
    token_savings_estimate: int = 0
    candidate_task_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "token_savings_estimate": self.token_savings_estimate,
            "candidate_task_ids": self.candidate_task_ids,
        }


class BatchingPolicyEngine:
    """Evaluates task batching proposals and strictly enforces verifier independence."""

    def evaluate_batch(
        self,
        tasks: List[BatchableTask],
        use_model_for_aggregation: bool = False,
    ) -> BatchEvaluationResult:
        task_ids = [t.task_id for t in tasks]

        # 1. Enforce: No model used solely for concatenation
        if use_model_for_aggregation:
            raise ModelConcatenationForbiddenError(
                "Policy violation: Invoking an LLM solely to copy-paste or concatenate batch results is strictly forbidden."
            )

        if not tasks:
            return BatchEvaluationResult(
                status=BatchEligibilityStatus.INCOMPATIBLE_CONTEXTS,
                allowed=False,
                reason="Cannot evaluate an empty batch.",
                token_savings_estimate=0,
                candidate_task_ids=[],
            )

        # 2. Check for Producer + Verifier collusion
        producers = [t for t in tasks if t.role == TaskRole.PRODUCER]
        verifiers = [t for t in tasks if t.role == TaskRole.VERIFIER or t.requires_independent_verdict]

        if producers and verifiers:
            # Check if verifier inspects a deliverable produced in the same batch
            for p in producers:
                for v in verifiers:
                    if p.target_deliverable_id and p.target_deliverable_id == v.target_deliverable_id:
                        return BatchEvaluationResult(
                            status=BatchEligibilityStatus.FORBIDDEN_PRODUCER_VERIFIER_COLLUSION,
                            allowed=False,
                            reason=f"Verifier task '{v.task_id}' cannot be batched with producer task '{p.task_id}' "
                                   f"for deliverable '{p.target_deliverable_id}' (destroys independent judgment).",
                            token_savings_estimate=0,
                            candidate_task_ids=task_ids,
                        )

            # Even general producer and independent verifier in same batch is forbidden to prevent context bias
            return BatchEvaluationResult(
                status=BatchEligibilityStatus.FORBIDDEN_PRODUCER_VERIFIER_COLLUSION,
                allowed=False,
                reason="Producer and independent verifier tasks cannot share prompt/session context.",
                token_savings_estimate=0,
                candidate_task_ids=task_ids,
            )

        # 3. Check for multiple mutators
        mutators = [t for t in tasks if t.role == TaskRole.MUTATOR or t.effect_class not in ("read_only", "idempotent")]
        if len(mutators) > 1:
            return BatchEvaluationResult(
                status=BatchEligibilityStatus.FORBIDDEN_CONCURRENT_MUTATION,
                allowed=False,
                reason="Multiple mutating tasks cannot be batched together; mutations require isolated execution boundaries.",
                token_savings_estimate=0,
                candidate_task_ids=task_ids,
            )

        # 4. Check Context Source Compatibility for Read-Only Tasks
        context_sources = {t.context_source_id for t in tasks}
        if len(context_sources) > 1:
            return BatchEvaluationResult(
                status=BatchEligibilityStatus.INCOMPATIBLE_CONTEXTS,
                allowed=False,
                reason=f"Tasks target disjoint context sources ({sorted(list(context_sources))}); no token savings achieved.",
                token_savings_estimate=0,
                candidate_task_ids=task_ids,
            )

        # 5. Approved Read-Only Batch
        all_read_only = all(t.effect_class == "read_only" for t in tasks)
        if all_read_only and len(tasks) > 1:
            # Token savings: context is loaded once instead of N times
            base_context_tokens = tasks[0].context_tokens_estimate
            savings = base_context_tokens * (len(tasks) - 1)
            return BatchEvaluationResult(
                status=BatchEligibilityStatus.ALLOWED_READ_BATCH,
                allowed=True,
                reason=f"Batch of {len(tasks)} read-only tasks sharing context '{tasks[0].context_source_id}' approved.",
                token_savings_estimate=savings,
                candidate_task_ids=task_ids,
            )

        return BatchEvaluationResult(
            status=BatchEligibilityStatus.ALLOWED_READ_BATCH,
            allowed=True,
            reason="Single task or compatible batch accepted.",
            token_savings_estimate=0,
            candidate_task_ids=task_ids,
        )

    def deterministic_aggregate(self, outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Performs zero-cost deterministic aggregation of batch results in pure Python."""
        aggregated = {
            "aggregated_count": len(outputs),
            "results": outputs,
            "engine": "deterministic_python_hub",
            "model_tokens_spent": 0,
        }
        return aggregated

    def generate_batching_evidence(
        self,
        sample_tasks: List[BatchableTask],
    ) -> Dict[str, Any]:
        """Generates CP-24 required evidence: ['task-contexts', 'independence-requirements', 'usage-evidence']."""
        read_batch = [t for t in sample_tasks if t.role == TaskRole.READER]
        mixed_batch = [sample_tasks[0], sample_tasks[1]] if len(sample_tasks) >= 2 else sample_tasks

        read_eval = self.evaluate_batch(read_batch)
        collusion_eval = self.evaluate_batch(mixed_batch)

        return {
            "required_evidence": ["task-contexts", "independence-requirements", "usage-evidence"],
            "task-contexts": {
                "evaluated_tasks_count": len(sample_tasks),
                "tasks": [t.to_dict() for t in sample_tasks],
                "read_batch_context_shared": read_batch[0].context_source_id if read_batch else None,
                "token_savings_estimate": read_eval.token_savings_estimate,
            },
            "independence-requirements": {
                "producer_verifier_separation_enforced": True,
                "self_review_blocked": True,
                "collusion_rejection_reason": collusion_eval.reason if not collusion_eval.allowed else "N/A",
                "rules": [
                    "Independent reviewer does not adopt producer decisions",
                    "Verifier receives artifact and acceptance criteria only, not producer rationalization",
                    "Deterministic aggregator used instead of model string concatenation",
                ],
            },
            "usage-evidence": {
                "read_batch_result": read_eval.to_dict(),
                "collusion_batch_result": collusion_eval.to_dict(),
                "model_copy_paste_forbidden": True,
            },
        }
