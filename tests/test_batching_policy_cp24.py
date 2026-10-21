"""Tests for CP-24 / CQ-24 / GB-BATCH-01: Batching Policy & Independent Verifier Separation

Verifies:
1. Compatible read-only tasks sharing common context are batched to save tokens.
2. Producer + verifier collusion in the same batch is strictly forbidden (independent judgment preserved).
3. Models used solely for copy-pasting/concatenation are rejected with ModelConcatenationForbiddenError.
4. Multiple mutators are serialized into separate execution boundaries.
5. Evidence generated with ['task-contexts', 'independence-requirements', 'usage-evidence'].
"""

import pytest

from courier_core.batching_policy_engine import (
    BatchEligibilityStatus,
    BatchableTask,
    BatchingPolicyEngine,
    ModelConcatenationForbiddenError,
    TaskRole,
)


def test_read_only_tasks_sharing_context_are_approved_with_savings():
    engine = BatchingPolicyEngine()

    tasks = [
        BatchableTask(
            task_id="read-imports",
            role=TaskRole.READER,
            context_source_id="repo:courier-main",
            effect_class="read_only",
            context_tokens_estimate=5000,
        ),
        BatchableTask(
            task_id="read-docstrings",
            role=TaskRole.READER,
            context_source_id="repo:courier-main",
            effect_class="read_only",
            context_tokens_estimate=5000,
        ),
        BatchableTask(
            task_id="read-type-annotations",
            role=TaskRole.READER,
            context_source_id="repo:courier-main",
            effect_class="read_only",
            context_tokens_estimate=5000,
        ),
    ]

    res = engine.evaluate_batch(tasks)

    assert res.allowed is True
    assert res.status == BatchEligibilityStatus.ALLOWED_READ_BATCH
    assert res.token_savings_estimate == 10000  # 5000 * 2 saved passes
    assert len(res.candidate_task_ids) == 3


def test_producer_and_verifier_collusion_is_strictly_forbidden():
    engine = BatchingPolicyEngine()

    tasks = [
        BatchableTask(
            task_id="code-writer-task",
            role=TaskRole.PRODUCER,
            context_source_id="repo:courier-main",
            target_deliverable_id="deliverable:payment_gateway.py",
            effect_class="idempotent",
        ),
        BatchableTask(
            task_id="code-auditor-verifier",
            role=TaskRole.VERIFIER,
            context_source_id="repo:courier-main",
            target_deliverable_id="deliverable:payment_gateway.py",
            effect_class="read_only",
            requires_independent_verdict=True,
        ),
    ]

    res = engine.evaluate_batch(tasks)

    assert res.allowed is False
    assert res.status == BatchEligibilityStatus.FORBIDDEN_PRODUCER_VERIFIER_COLLUSION
    assert "destroys independent judgment" in res.reason


def test_model_used_solely_for_copy_paste_is_forbidden():
    engine = BatchingPolicyEngine()

    tasks = [
        BatchableTask(
            task_id="task-r1",
            role=TaskRole.READER,
            context_source_id="doc:specs.md",
            effect_class="read_only",
        ),
    ]

    with pytest.raises(ModelConcatenationForbiddenError, match="solely to copy-paste or concatenate"):
        engine.evaluate_batch(tasks, use_model_for_aggregation=True)

    # Deterministic hub aggregator succeeds at zero token cost
    agg = engine.deterministic_aggregate([{"part": 1}, {"part": 2}])
    assert agg["model_tokens_spent"] == 0
    assert agg["aggregated_count"] == 2


def test_multiple_mutators_are_rejected_from_batch():
    engine = BatchingPolicyEngine()

    tasks = [
        BatchableTask(
            task_id="mutate-users",
            role=TaskRole.MUTATOR,
            context_source_id="db:main",
            effect_class="non_idempotent",
        ),
        BatchableTask(
            task_id="mutate-orders",
            role=TaskRole.MUTATOR,
            context_source_id="db:main",
            effect_class="non_idempotent",
        ),
    ]

    res = engine.evaluate_batch(tasks)

    assert res.allowed is False
    assert res.status == BatchEligibilityStatus.FORBIDDEN_CONCURRENT_MUTATION


def test_evidence_generation():
    engine = BatchingPolicyEngine()

    sample_tasks = [
        BatchableTask(
            task_id="t-write",
            role=TaskRole.PRODUCER,
            context_source_id="repo:core",
            target_deliverable_id="deliv-1",
        ),
        BatchableTask(
            task_id="t-verify",
            role=TaskRole.VERIFIER,
            context_source_id="repo:core",
            target_deliverable_id="deliv-1",
            requires_independent_verdict=True,
        ),
        BatchableTask(
            task_id="t-read-1",
            role=TaskRole.READER,
            context_source_id="repo:core",
            effect_class="read_only",
        ),
        BatchableTask(
            task_id="t-read-2",
            role=TaskRole.READER,
            context_source_id="repo:core",
            effect_class="read_only",
        ),
    ]

    evidence = engine.generate_batching_evidence(sample_tasks)

    assert evidence["required_evidence"] == ["task-contexts", "independence-requirements", "usage-evidence"]
    assert evidence["independence-requirements"]["producer_verifier_separation_enforced"] is True
    assert evidence["independence-requirements"]["self_review_blocked"] is True
    assert evidence["usage-evidence"]["model_copy_paste_forbidden"] is True
