"""Tests for CP-46 / CQ-46 / GB-RUNTIME-OWNERSHIP-01: Runtime Ownership & Motor Decoupling.

Verifies:
1. Interactive chat turns are permitted to end cleanly ("Interaktiver Chat darf enden").
2. Prompt text claiming infinite continuous execution without a motor is strictly rejected ("kein Dauerlauf aus Prompttext behaupten").
3. Autonomous execution is owned exclusively by verified host motors ("autorisierter Motor ist nachweisbar zuständig").
4. System sleep, power loss, and network drops are documented as physical boundaries ("Rechner-/Netzausfall wird als Grenze dokumentiert").
5. Evidence structure generation containing ['actual-motor', 'trigger-config', 'stop-budget'].
"""

import pytest

from courier_core.runtime_ownership_boundary import (
    MotorKind,
    PhysicalBoundaryKind,
    PromptDauerlaufProhibitedError,
    RuntimeOwnershipCoordinator,
)


def test_interactive_chat_turn_permitted_to_end():
    """Interactive chat turn is always permitted and designed to exit without keeping shell open."""
    coordinator = RuntimeOwnershipCoordinator()

    res = coordinator.evaluate_turn_completion(has_pending_tasks=False)
    assert res["chat_turn_can_exit"] is True
    assert "all ready work finished" in res["status_message"]


def test_prompt_text_dauerlauf_without_motor_raises_error():
    """Prompt claiming infinite overnight running without an authorized active motor is strictly rejected."""
    coordinator = RuntimeOwnershipCoordinator()

    with pytest.raises(PromptDauerlaufProhibitedError):
        coordinator.evaluate_turn_completion(
            has_pending_tasks=True,
            prompt_claims_continuous_running=True,
        )


def test_delegation_to_authorized_motor_with_drain_budget():
    """When a verified OS motor is registered, background work is delegated within bounded drain limits."""
    coordinator = RuntimeOwnershipCoordinator()

    motor = coordinator.register_authorized_motor(
        motor_id="courier-win-supervisor",
        motor_kind=MotorKind.OS_DAEMON_SERVICE,
        drain_budget_seconds=3600.0,
        is_verified_active=True,
        spend_budget_eur=0.00,
    )

    assert motor.motor_id == "courier-win-supervisor"
    assert motor.spend_budget_eur == 0.00

    res = coordinator.evaluate_turn_completion(
        has_pending_tasks=True,
        prompt_claims_continuous_running=True,
    )
    assert res["chat_turn_can_exit"] is True
    assert res["delegated_to_motor"] is True
    assert "courier-win-supervisor" in res["status_message"]


def test_physical_boundary_recorded_on_sleep_or_power_loss():
    """Hardware sleep, power cuts, or network severance are recorded as explicit physical boundaries."""
    coordinator = RuntimeOwnershipCoordinator()

    rec_sleep = coordinator.record_physical_boundary(
        boundary_kind=PhysicalBoundaryKind.SYSTEM_SLEEP,
        checkpoint_id="chk-sleep-001",
        resume_on_wake=True,
    )
    assert rec_sleep.boundary_kind == PhysicalBoundaryKind.SYSTEM_SLEEP
    assert rec_sleep.checkpoint_id == "chk-sleep-001"
    assert rec_sleep.resume_on_wake is True

    rec_net = coordinator.record_physical_boundary(
        boundary_kind=PhysicalBoundaryKind.NETWORK_DISCONNECT,
        checkpoint_id="chk-net-002",
        resume_on_wake=True,
    )
    assert rec_net.boundary_kind == PhysicalBoundaryKind.NETWORK_DISCONNECT


def test_evidence_generation():
    """Validates required catalog evidence keys: ['actual-motor', 'trigger-config', 'stop-budget']."""
    coordinator = RuntimeOwnershipCoordinator()
    coordinator.register_authorized_motor(
        motor_id="win-task-sched-01",
        motor_kind=MotorKind.SCHEDULED_TASK,
        drain_budget_seconds=1800.0,
    )
    coordinator.record_physical_boundary(
        boundary_kind=PhysicalBoundaryKind.HOST_REBOOT,
        checkpoint_id="chk-reboot-1",
    )

    evidence = coordinator.generate_ownership_evidence()

    assert "actual-motor" in evidence
    assert "trigger-config" in evidence
    assert "stop-budget" in evidence

    assert evidence["actual-motor"]["motor_id"] == "win-task-sched-01"
    assert evidence["stop-budget"]["drain_budget_seconds"] == 1800.0
    assert evidence["stop-budget"]["spend_budget_eur"] == 0.0
    assert len(evidence["trigger-config"]["physical_boundaries_recorded"]) == 1
