"""Reasoning Evaluation Engine & Deterministic Test Oracle (CP-29 / CQ-29).

Verifies and enforces:
1. Evaluation over a fixed, frozen task set with immutable input specifications and deterministic test oracles.
2. Ingestion and prioritization of existing historical results before considering additional model runs.
3. Strict deterministic pass/fail criteria ("Keine Wahl nach Textlänge"): Verbose prose does not qualify as correctness.
4. Demonstrable improvement detection: Proves when extra reasoning actually changes an incorrect verdict to correct versus mere token inflation.
5. Emits structured evidence matching ["fixed-task-set", "existing-results", "test-oracle"].
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class TaskDifficulty(str, Enum):
    ROUTINE = "ROUTINE"
    COMPLEX_BOTTLENECK = "COMPLEX_BOTTLENECK"


class ReasoningLevel(str, Enum):
    STANDARD = "STANDARD"
    HIGH = "HIGH"


class EvaluationOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class FrozenTask:
    """An immutable evaluation task with fixed inputs and deterministic oracle."""
    task_id: str
    input_payload: str
    expected_result_digest: str
    difficulty: TaskDifficulty = TaskDifficulty.ROUTINE

    @property
    def frozen_sha256(self) -> str:
        data = f"{self.task_id}:{self.input_payload}:{self.expected_result_digest}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass
class TaskResultRecord:
    """The result of an execution attempt under a given reasoning level."""
    task_id: str
    reasoning_level: ReasoningLevel
    output_payload: str
    token_count: int
    char_count: int
    passed_oracle: bool
    source: str = "EXISTING_RESULT"

    @classmethod
    def create(
        cls,
        task_id: str,
        reasoning_level: ReasoningLevel,
        output_payload: str,
        token_count: int,
        oracle: Callable[[str], bool],
        source: str = "EXISTING_RESULT",
    ) -> "TaskResultRecord":
        passed = oracle(output_payload)
        return cls(
            task_id=task_id,
            reasoning_level=reasoning_level,
            output_payload=output_payload,
            token_count=token_count,
            char_count=len(output_payload),
            passed_oracle=passed,
            source=source,
        )


@dataclass(frozen=True)
class ComparisonVerdict:
    """Comparison verdict determining whether higher reasoning demonstrably improved the outcome."""
    task_id: str
    standard_passed: bool
    high_passed: bool
    standard_tokens: int
    high_tokens: int
    reasoning_improved_decision: bool
    verbosity_only_inflation: bool
    recommended_level: ReasoningLevel
    explanation: str


class ReasoningEvaluationEngine:
    """Evaluates whether additional reasoning demonstrably improves decision quality."""

    def __init__(self, frozen_tasks: Optional[List[FrozenTask]] = None) -> None:
        self.tasks: Dict[str, FrozenTask] = {}
        if frozen_tasks:
            for t in frozen_tasks:
                self.tasks[t.task_id] = t
        self.existing_results: Dict[str, Dict[ReasoningLevel, TaskResultRecord]] = {}

    def register_task(self, task: FrozenTask) -> None:
        self.tasks[task.task_id] = task

    def ingest_result(self, record: TaskResultRecord) -> None:
        """Stores a historical or observed result for a task."""
        if record.task_id not in self.existing_results:
            self.existing_results[record.task_id] = {}
        self.existing_results[record.task_id][record.reasoning_level] = record

    def compare_reasoning_efficiency(self, task_id: str) -> ComparisonVerdict:
        """Compares STANDARD vs HIGH reasoning for a task against deterministic oracles.

        Strict invariants:
        - Never selects a result merely because it has longer text or more tokens ('Keine Wahl nach Textlänge').
        - Flags verbosity inflation when token count increases without a correctness gain.
        - Recommends HIGH only when STANDARD failed and HIGH passed the oracle.
        """
        if task_id not in self.existing_results:
            raise KeyError(f"No existing results registered for task {task_id}")

        results = self.existing_results[task_id]
        if ReasoningLevel.STANDARD not in results or ReasoningLevel.HIGH not in results:
            raise ValueError(f"Task {task_id} must have both STANDARD and HIGH results for comparison")

        res_std = results[ReasoningLevel.STANDARD]
        res_high = results[ReasoningLevel.HIGH]

        # Case 1: Standard already passes oracle
        if res_std.passed_oracle:
            verbosity_inflation = res_high.token_count > res_std.token_count
            return ComparisonVerdict(
                task_id=task_id,
                standard_passed=True,
                high_passed=res_high.passed_oracle,
                standard_tokens=res_std.token_count,
                high_tokens=res_high.token_count,
                reasoning_improved_decision=False,
                verbosity_only_inflation=verbosity_inflation,
                recommended_level=ReasoningLevel.STANDARD,
                explanation="Standard reasoning is already correct. Extra reasoning tokens do not improve correctness.",
            )

        # Case 2: Standard failed, High passed oracle -> Demonstrable Improvement!
        if not res_std.passed_oracle and res_high.passed_oracle:
            return ComparisonVerdict(
                task_id=task_id,
                standard_passed=False,
                high_passed=True,
                standard_tokens=res_std.token_count,
                high_tokens=res_high.token_count,
                reasoning_improved_decision=True,
                verbosity_only_inflation=False,
                recommended_level=ReasoningLevel.HIGH,
                explanation="High reasoning demonstrably resolved the failure and passed the deterministic oracle.",
            )

        # Case 3: Both failed oracle -> Extra reasoning failed to help
        return ComparisonVerdict(
            task_id=task_id,
            standard_passed=False,
            high_passed=False,
            standard_tokens=res_std.token_count,
            high_tokens=res_high.token_count,
            reasoning_improved_decision=False,
            verbosity_only_inflation=res_high.token_count > res_std.token_count,
            recommended_level=ReasoningLevel.STANDARD,
            explanation="Both levels failed the deterministic oracle. Extra tokens provided no accuracy gain.",
        )

    def generate_reasoning_evidence(self) -> Dict[str, Any]:
        """Emits required evidence dictionary for CP-29.

        Required fields:
        - 'fixed-task-set'
        - 'existing-results'
        - 'test-oracle'
        """
        task_set_summary = {
            tid: {
                "difficulty": task.difficulty.value,
                "input_hash": hashlib.sha256(task.input_payload.encode()).hexdigest()[:16],
                "expected_digest": task.expected_result_digest,
                "frozen_sha256": task.frozen_sha256[:16],
            }
            for tid, task in self.tasks.items()
        }

        results_summary = {}
        for tid, level_dict in self.existing_results.items():
            results_summary[tid] = {
                lvl.value: {
                    "passed_oracle": rec.passed_oracle,
                    "token_count": rec.token_count,
                    "char_count": rec.char_count,
                    "source": rec.source,
                }
                for lvl, rec in level_dict.items()
            }

        return {
            "fixed-task-set": task_set_summary,
            "existing-results": results_summary,
            "test-oracle": {
                "evaluation_method": "deterministic_exact_or_invariant",
                "selection_rule": "correctness_only_no_text_length_bias",
                "registered_task_count": len(self.tasks),
                "evaluated_task_count": len(self.existing_results),
            },
        }
