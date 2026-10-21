"""Tests for CP-47 / CQ-47 / GB-CANARY-PROOF-01: Canary Proof & Autonomous Task Progression.

Verifies:
1. Autonomous 5-task progression without user manual Next-Task prompts ("nicht mehr Next-Task-Prompts verteilen").
2. Mutex single-flight constraint strictly rejects parallel second canary ("keinen parallelen zweiten Canary starten").
3. Zero lost tasks and zero duplicate observed side effects ("Verluste und doppelte beobachtete Effekte null").
4. Strict separation between Fixture and PHYSICAL_LIVE authorization ("Fixture/LIVE klar getrennt").
5. Bounded failure recovery in task 3 without invalidating prior tasks.
6. Evidence structure generation containing ['canary-manifest', 'execution-owner', 'live-permission'].
"""

import pytest

from courier_core.canary_proof_verifier import (
    CanaryCollisionError,
    CanaryProofEngine,
    ExecutionEnvironment,
    UnauthorizedLiveExecutionError,
)


def test_canary_pipeline_executes_autonomously_zero_manual_prompts():
    """Canary runs 5 dependency tasks end-to-end automatically with zero lost tasks and zero duplicate effects."""
    engine = CanaryProofEngine()
    manifest = engine.initialize_canary(manifest_id="canary-fixture-run-001", env=ExecutionEnvironment.FIXTURE)

    summary = engine.run_pipeline()

    assert summary["all_completed"] is True
    assert summary["tasks_count"] == 5
    assert summary["total_completed"] == 5
    # Strict invariants: 0 lost tasks, 0 duplicate effects
    assert summary["lost_tasks_count"] == 0
    assert summary["duplicate_effects_count"] == 0


def test_parallel_second_canary_forbidden_raises_collision_error():
    """Attempting to initialize a second canary while one is active raises CanaryCollisionError."""
    engine = CanaryProofEngine()
    engine.initialize_canary(manifest_id="canary-active-01")

    with pytest.raises(CanaryCollisionError):
        engine.initialize_canary(manifest_id="canary-parallel-collision")


def test_physical_live_requires_authorized_permission_token():
    """PHYSICAL_LIVE execution strictly requires an authentic live_permission token."""
    engine = CanaryProofEngine()

    # Attempt without token
    with pytest.raises(UnauthorizedLiveExecutionError):
        engine.initialize_canary(
            manifest_id="canary-live-unauth",
            env=ExecutionEnvironment.PHYSICAL_LIVE,
            live_permission=None,
        )

    # Valid token succeeds
    manifest = engine.initialize_canary(
        manifest_id="canary-live-auth",
        env=ExecutionEnvironment.PHYSICAL_LIVE,
        live_permission="TOKEN_DENNIS_LIVE_GATE_2026",
    )
    assert manifest.env == ExecutionEnvironment.PHYSICAL_LIVE
    assert manifest.live_permission == "TOKEN_DENNIS_LIVE_GATE_2026"


def test_bounded_fault_recovery_without_corrupting_prior_tasks():
    """Task 3 transient fault retries safely; Tasks 1 and 2 execute exactly once."""
    engine = CanaryProofEngine()
    manifest = engine.initialize_canary(manifest_id="canary-fault-test")

    engine.run_pipeline()

    t1 = [t for t in manifest.tasks if t.task_id == "canary-t1-root"][0]
    t2 = [t for t in manifest.tasks if t.task_id == "canary-t2-dep"][0]
    t3 = [t for t in manifest.tasks if t.task_id == "canary-t3-fault"][0]

    # Task 1 and 2 executed exactly once
    assert t1.execution_count == 1
    assert t2.execution_count == 1
    # Task 3 had 1 failure + 1 retry = 2 attempts, but only 1 final completed status
    assert t3.execution_count == 2
    assert t3.status == "COMPLETED"


def test_evidence_generation():
    """Validates required catalog evidence keys: ['canary-manifest', 'execution-owner', 'live-permission']."""
    engine = CanaryProofEngine()
    engine.initialize_canary(
        manifest_id="canary-ev-test",
        execution_owner="courier_supervisor",
    )
    engine.run_pipeline()

    evidence = engine.generate_canary_evidence()

    assert "canary-manifest" in evidence
    assert "execution-owner" in evidence
    assert "live-permission" in evidence

    assert evidence["canary-manifest"]["manifest_id"] == "canary-ev-test"
    assert evidence["canary-manifest"]["is_completed"] is True
    assert evidence["canary-manifest"]["effects_verified_single_occurrence"] is True
    assert evidence["execution-owner"] == "courier_supervisor"
