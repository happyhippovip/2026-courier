"""Tests for CP-25 / CQ-25 / GB-FANIN-01: Fan-In Barrier, Mandatory Gate & Work Cancellation

Verifies:
1. Mandatory barriers cannot be bypassed or downgraded to force early pass (fails closed).
2. Missing optional evidence is explicitly cataloged in the terminal receipt.
3. Superfluous unstarted tasks are cancelled cleanly to yield permits for cluster fairness.
4. In-flight tasks with committed/pending external effects are gracefully awaited rather than blind-killed.
5. Evidence generated with ['dependency-contract', 'branch-policy', 'accepted-result'].
"""

import pytest

from courier_core.fanin_barrier_engine import (
    BranchCriticality,
    BranchExecutionState,
    FanInBarrierEngine,
    FanInGoalContract,
)


def test_mandatory_barrier_cannot_be_bypassed_fails_closed():
    engine = FanInBarrierEngine()

    goal = FanInGoalContract(goal_id="goal-release-101", project_id="courier-core")
    goal.add_branch("build_binaries", BranchCriticality.MANDATORY)
    goal.add_branch("integration_tests", BranchCriticality.MANDATORY)
    goal.add_branch("optional_telemetry", BranchCriticality.OPTIONAL)

    # Mandatory integration_tests is FAILED
    states = {
        "build_binaries": BranchExecutionState.COMPLETED,
        "integration_tests": BranchExecutionState.FAILED,
        "optional_telemetry": BranchExecutionState.COMPLETED,
    }

    receipt = engine.evaluate_terminal_fanin(goal, states)

    assert receipt.passed is False
    assert receipt.verdict == "FAIL_MANDATORY_UNFULFILLED"
    assert "integration_tests" in receipt.unfulfilled_mandatory_branches
    assert "build_binaries" in receipt.completed_mandatory_branches


def test_missing_optional_evidence_is_explicitly_cataloged_on_pass():
    engine = FanInBarrierEngine()

    goal = FanInGoalContract(goal_id="goal-release-102", project_id="courier-core")
    goal.add_branch("build_binaries", BranchCriticality.MANDATORY)
    goal.add_branch("unit_tests", BranchCriticality.MANDATORY)
    goal.add_branch("extended_benchmarks", BranchCriticality.OPTIONAL)

    states = {
        "build_binaries": BranchExecutionState.COMPLETED,
        "unit_tests": BranchExecutionState.COMPLETED,
        "extended_benchmarks": BranchExecutionState.FAILED,  # Optional failure
    }

    receipt = engine.evaluate_terminal_fanin(goal, states)

    # Core goal passes because all mandatory dependencies are satisfied
    assert receipt.passed is True
    assert receipt.verdict == "PASS"

    # Missing optional branch is explicitly reported in the audit receipt
    assert "extended_benchmarks" in receipt.missing_optional_evidence
    assert receipt.completed_mandatory_branches == ["build_binaries", "unit_tests"]


def test_superfluous_unstarted_work_is_cancelled_for_fairness():
    engine = FanInBarrierEngine()

    goal = FanInGoalContract(goal_id="goal-quick-exit", project_id="courier-core")
    goal.add_branch("core_feature", BranchCriticality.MANDATORY)
    goal.add_branch("deep_docs", BranchCriticality.OPTIONAL)
    goal.add_branch("extra_profiling", BranchCriticality.OPTIONAL)

    states = {
        "core_feature": BranchExecutionState.COMPLETED,
        "deep_docs": BranchExecutionState.PENDING_UNSTARTED,
        "extra_profiling": BranchExecutionState.PENDING_UNSTARTED,
    }

    receipt = engine.evaluate_terminal_fanin(goal, states)

    assert receipt.passed is True
    # Unstarted surplus work cancelled cleanly
    assert "deep_docs" in receipt.cancelled_superfluous_branches
    assert "extra_profiling" in receipt.cancelled_superfluous_branches


def test_inflight_effects_are_not_blindly_killed():
    engine = FanInBarrierEngine()

    goal = FanInGoalContract(goal_id="goal-external-effects", project_id="courier-core")
    goal.add_branch("primary_task", BranchCriticality.MANDATORY)
    goal.add_branch("database_sync", BranchCriticality.OPTIONAL, effect_class="non_idempotent")
    goal.add_branch("read_stats", BranchCriticality.OPTIONAL, effect_class="read_only")

    states = {
        "primary_task": BranchExecutionState.COMPLETED,
        "database_sync": BranchExecutionState.IN_FLIGHT,
        "read_stats": BranchExecutionState.IN_FLIGHT,
    }

    # database_sync has active in-flight external mutations; read_stats does not
    inflight_effects = {
        "database_sync": True,
        "read_stats": False,
    }

    receipt = engine.evaluate_terminal_fanin(goal, states, inflight_effects)

    assert receipt.passed is True
    # Non-idempotent task with active external effect is gracefully awaited
    assert "database_sync" in receipt.gracefully_awaited_inflight_branches
    # Read-only task with no side-effects is safely cancelled to free capacity
    assert "read_stats" in receipt.cancelled_superfluous_branches


def test_evidence_generation():
    engine = FanInBarrierEngine()

    goal = FanInGoalContract(goal_id="goal-demo", project_id="demo-proj")
    goal.add_branch("b_core", BranchCriticality.MANDATORY)
    goal.add_branch("b_opt", BranchCriticality.OPTIONAL)

    states = {
        "b_core": BranchExecutionState.COMPLETED,
        "b_opt": BranchExecutionState.PENDING_UNSTARTED,
    }

    evidence = engine.generate_fanin_evidence(goal, states)

    assert evidence["required_evidence"] == ["dependency-contract", "branch-policy", "accepted-result"]
    assert evidence["dependency-contract"]["goal_id"] == "goal-demo"
    assert evidence["branch-policy"]["mandatory_downgrade_allowed"] is False
    assert evidence["accepted-result"]["passed"] is True
    assert "b_opt" in evidence["accepted-result"]["cancelled_superfluous_branches"]
