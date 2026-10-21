"""Tests for CP-29 / CQ-29 / GB-REASONING-01: Reasoning Evaluation Engine & Deterministic Test Oracle.

Verifies:
1. Immutable frozen task set with deterministic inputs and oracles.
2. Rejection of selection based on text length / verbosity ("Keine Wahl nach Textlänge").
3. Demonstrable improvement detection when high reasoning passes an oracle that standard failed.
4. Detection of verbosity inflation when high reasoning produces more tokens without improved correctness.
5. Reuse and ingestion of existing historical results.
6. Evidence generated with ['fixed-task-set', 'existing-results', 'test-oracle'].
"""

import hashlib
import pytest

from courier_core.reasoning_evaluation_engine import (
    ComparisonVerdict,
    FrozenTask,
    ReasoningEvaluationEngine,
    ReasoningLevel,
    TaskDifficulty,
    TaskResultRecord,
)


def test_fixed_task_set_immutability_and_hash():
    """Frozen evaluation tasks have deterministic signatures and immutable inputs."""
    task = FrozenTask(
        task_id="eval-01",
        input_payload="sort [5, 2, 8, 1]",
        expected_result_digest=hashlib.sha256(b"[1, 2, 5, 8]").hexdigest(),
        difficulty=TaskDifficulty.ROUTINE,
    )
    assert task.task_id == "eval-01"
    assert len(task.frozen_sha256) == 64

    # FrozenTask is immutable dataclass
    with pytest.raises(Exception):
        task.input_payload = "modified"


def test_verbosity_inflation_flagged_when_standard_already_correct():
    """When standard reasoning passes, longer outputs with more tokens are flagged as verbosity inflation."""
    engine = ReasoningEvaluationEngine()

    oracle = lambda out: "[1, 2, 5, 8]" in out

    rec_std = TaskResultRecord.create(
        task_id="eval-01",
        reasoning_level=ReasoningLevel.STANDARD,
        output_payload="Result: [1, 2, 5, 8]",
        token_count=15,
        oracle=oracle,
    )

    # High reasoning produces a 500-token verbose explanation of bubble sort
    verbose_text = "Let us think step by step through every pairwise comparison... " * 15 + "Result: [1, 2, 5, 8]"
    rec_high = TaskResultRecord.create(
        task_id="eval-01",
        reasoning_level=ReasoningLevel.HIGH,
        output_payload=verbose_text,
        token_count=520,
        oracle=oracle,
    )

    engine.ingest_result(rec_std)
    engine.ingest_result(rec_high)

    verdict = engine.compare_reasoning_efficiency("eval-01")
    assert verdict.standard_passed is True
    assert verdict.high_passed is True
    assert verdict.reasoning_improved_decision is False
    assert verdict.verbosity_only_inflation is True
    assert verdict.recommended_level == ReasoningLevel.STANDARD
    # Strict invariant: Did NOT pick high level merely because text was longer
    assert verdict.recommended_level != ReasoningLevel.HIGH


def test_demonstrable_improvement_detected_on_complex_bottleneck():
    """When standard reasoning fails on an invariant edge case and high passes, improvement is proven."""
    engine = ReasoningEvaluationEngine()

    # Complex constraint: handle negative zero and null preservation
    oracle = lambda out: "MATCH_CANONICAL_INVARIANT" in out

    rec_std = TaskResultRecord.create(
        task_id="bottleneck-01",
        reasoning_level=ReasoningLevel.STANDARD,
        output_payload="Result: FAST_APPROXIMATION_FAILED",
        token_count=45,
        oracle=oracle,
    )

    rec_high = TaskResultRecord.create(
        task_id="bottleneck-01",
        reasoning_level=ReasoningLevel.HIGH,
        output_payload="Deep analysis resolved corner case: MATCH_CANONICAL_INVARIANT",
        token_count=350,
        oracle=oracle,
    )

    engine.ingest_result(rec_std)
    engine.ingest_result(rec_high)

    verdict = engine.compare_reasoning_efficiency("bottleneck-01")
    assert verdict.standard_passed is False
    assert verdict.high_passed is True
    assert verdict.reasoning_improved_decision is True
    assert verdict.verbosity_only_inflation is False
    assert verdict.recommended_level == ReasoningLevel.HIGH


def test_ineffective_escalation_when_both_levels_fail():
    """When both standard and high fail the deterministic oracle, escalation is deemed ineffective."""
    engine = ReasoningEvaluationEngine()

    oracle = lambda out: "SUCCESS_CRITERIA_MET" in out

    rec_std = TaskResultRecord.create(
        task_id="unsolvable-01",
        reasoning_level=ReasoningLevel.STANDARD,
        output_payload="Error: Missing input data",
        token_count=30,
        oracle=oracle,
    )

    rec_high = TaskResultRecord.create(
        task_id="unsolvable-01",
        reasoning_level=ReasoningLevel.HIGH,
        output_payload="Extensive reasoning: Still missing input data after 40 steps.",
        token_count=400,
        oracle=oracle,
    )

    engine.ingest_result(rec_std)
    engine.ingest_result(rec_high)

    verdict = engine.compare_reasoning_efficiency("unsolvable-01")
    assert verdict.standard_passed is False
    assert verdict.high_passed is False
    assert verdict.reasoning_improved_decision is False
    assert verdict.recommended_level == ReasoningLevel.STANDARD


def test_existing_results_reused_without_new_model_calls():
    """Existing historical results are ingested and queried without dispatching new API jobs."""
    engine = ReasoningEvaluationEngine()

    task = FrozenTask(
        task_id="hist-01",
        input_payload="verify lease invariant",
        expected_result_digest="digest-123",
        difficulty=TaskDifficulty.ROUTINE,
    )
    engine.register_task(task)

    # Ingest existing result with historical tag
    rec = TaskResultRecord(
        task_id="hist-01",
        reasoning_level=ReasoningLevel.STANDARD,
        output_payload="Invariant verified",
        token_count=20,
        char_count=18,
        passed_oracle=True,
        source="HISTORICAL_LEDGER_RUN_2026_09",
    )
    engine.ingest_result(rec)

    assert engine.existing_results["hist-01"][ReasoningLevel.STANDARD].source == "HISTORICAL_LEDGER_RUN_2026_09"


def test_evidence_generation():
    """Emits required evidence with fixed-task-set, existing-results, and test-oracle."""
    engine = ReasoningEvaluationEngine()

    task = FrozenTask(
        task_id="eval-task-1",
        input_payload="input-data-spec",
        expected_result_digest="digest-abc",
        difficulty=TaskDifficulty.COMPLEX_BOTTLENECK,
    )
    engine.register_task(task)

    rec = TaskResultRecord.create(
        task_id="eval-task-1",
        reasoning_level=ReasoningLevel.STANDARD,
        output_payload="digest-abc confirmed",
        token_count=50,
        oracle=lambda x: "digest-abc" in x,
    )
    engine.ingest_result(rec)

    evidence = engine.generate_reasoning_evidence()
    required_keys = ["fixed-task-set", "existing-results", "test-oracle"]
    for k in required_keys:
        assert k in evidence

    assert "eval-task-1" in evidence["fixed-task-set"]
    assert "eval-task-1" in evidence["existing-results"]
    assert evidence["test-oracle"]["selection_rule"] == "correctness_only_no_text_length_bias"
