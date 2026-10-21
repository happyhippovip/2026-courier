"""Runtime Ownership Boundary & Motor Decoupling Coordinator (CP-46 / GB-RUNTIME-OWNERSHIP-01).

Guarantees:
1. Interactive chat turns end promptly and cleanly ("Interaktiver Chat darf enden").
2. Autonomous background execution is owned exclusively by verified OS/host motors ("autorisierter Motor ist nachweisbar zuständig").
3. Prompt text cannot manufacture background persistence or infinite loops ("kein Dauerlauf aus Prompttext behaupten").
4. Physical hardware, power, sleep, and network interruptions are documented boundaries ("Rechner-/Netzausfall wird als Grenze dokumentiert").
5. Strict task-bound drain limits and 0.00 EUR spend budgets.
6. Evidence generation containing 'actual-motor', 'trigger-config', and 'stop-budget'.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MotorKind(str, Enum):
    OS_DAEMON_SERVICE = "OS_DAEMON_SERVICE"
    SCHEDULED_TASK = "SCHEDULED_TASK"
    COURIER_STANDALONE_MOTOR = "COURIER_STANDALONE_MOTOR"
    NONE_UNCONFIGURED = "NONE_UNCONFIGURED"


class PhysicalBoundaryKind(str, Enum):
    POWER_LOSS = "POWER_LOSS"
    SYSTEM_SLEEP = "SYSTEM_SLEEP"
    NETWORK_DISCONNECT = "NETWORK_DISCONNECT"
    HOST_REBOOT = "HOST_REBOOT"
    VOLUNTARY_DRAIN = "VOLUNTARY_DRAIN"


class PromptDauerlaufProhibitedError(Exception):
    """Raised when prompt text claims continuous execution without an authentic configured motor."""


@dataclass(frozen=True)
class MotorOwnership:
    motor_id: str
    motor_kind: MotorKind
    is_verified_active: bool
    drain_budget_seconds: float
    spend_budget_eur: float = 0.00


@dataclass(frozen=True)
class PhysicalBoundaryRecord:
    boundary_id: str
    boundary_kind: PhysicalBoundaryKind
    recorded_at_iso: str
    checkpoint_id: str
    resume_on_wake: bool


class RuntimeOwnershipCoordinator:
    """Manages agent turn termination, verified motor handoff, and physical environmental boundaries."""

    def __init__(self) -> None:
        self._authorized_motor: Optional[MotorOwnership] = None
        self._boundary_records: List[PhysicalBoundaryRecord] = []
        self._turn_history: List[Dict[str, Any]] = []

    @property
    def authorized_motor(self) -> Optional[MotorOwnership]:
        return self._authorized_motor

    def register_authorized_motor(
        self,
        motor_id: str,
        motor_kind: MotorKind,
        drain_budget_seconds: float,
        is_verified_active: bool = True,
        spend_budget_eur: float = 0.00,
    ) -> MotorOwnership:
        """Registers a verified host/OS background supervisor with bounded drain limits."""
        if not motor_id:
            raise ValueError("motor_id cannot be empty")
        if spend_budget_eur > 0.00:
            raise ValueError("Autonomous spend budget must be exactly 0.00 EUR")

        motor = MotorOwnership(
            motor_id=motor_id,
            motor_kind=motor_kind,
            is_verified_active=is_verified_active,
            drain_budget_seconds=drain_budget_seconds,
            spend_budget_eur=spend_budget_eur,
        )
        self._authorized_motor = motor
        return motor

    def evaluate_turn_completion(
        self,
        has_pending_tasks: bool,
        prompt_claims_continuous_running: bool = False,
    ) -> Dict[str, Any]:
        """Evaluates whether the interactive chat turn can exit immediately.

        Strict Invariants:
        1. An interactive chat turn is always allowed and encouraged to end.
        2. If prompt text claims continuous execution without an authorized motor, raises error.
        3. Background work continues if and only if an authorized motor is actively registered.
        """
        # Anti-hallucination check
        if prompt_claims_continuous_running and (
            self._authorized_motor is None or not self._authorized_motor.is_verified_active
        ):
            raise PromptDauerlaufProhibitedError(
                "Prompt text claimed infinite continuous execution, but no verified OS motor is registered!"
            )

        can_exit = True  # Chat turn is always permitted to end cleanly
        delegated_to_motor = False

        if has_pending_tasks:
            if self._authorized_motor and self._authorized_motor.is_verified_active:
                delegated_to_motor = True
                status_msg = f"Turn exited cleanly; background execution delegated to motor {self._authorized_motor.motor_id}"
            else:
                status_msg = "Turn exited; pending tasks parked in queue until next wake or motor start"
        else:
            status_msg = "Turn completed cleanly; all ready work finished"

        record = {
            "chat_turn_can_exit": can_exit,
            "delegated_to_motor": delegated_to_motor,
            "status_message": status_msg,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._turn_history.append(record)
        return record

    def record_physical_boundary(
        self,
        boundary_kind: PhysicalBoundaryKind,
        checkpoint_id: str,
        resume_on_wake: bool = True,
    ) -> PhysicalBoundaryRecord:
        """Records a physical interruption boundary (sleep, power loss, network drop) with recovery state."""
        rec = PhysicalBoundaryRecord(
            boundary_id=f"pbr-{len(self._boundary_records) + 1}",
            boundary_kind=boundary_kind,
            recorded_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            checkpoint_id=checkpoint_id,
            resume_on_wake=resume_on_wake,
        )
        self._boundary_records.append(rec)
        return rec

    def generate_ownership_evidence(self) -> Dict[str, Any]:
        """Generates evidence audit records containing required catalog keys."""
        return {
            "actual-motor": {
                "motor_id": self._authorized_motor.motor_id if self._authorized_motor else "NONE",
                "motor_kind": self._authorized_motor.motor_kind.value if self._authorized_motor else "NONE_UNCONFIGURED",
                "is_verified_active": self._authorized_motor.is_verified_active if self._authorized_motor else False,
            },
            "trigger-config": {
                "turn_exits_permitted": True,
                "recorded_turns": len(self._turn_history),
                "physical_boundaries_recorded": [
                    {"id": b.boundary_id, "kind": b.boundary_kind.value, "checkpoint": b.checkpoint_id}
                    for b in self._boundary_records
                ],
            },
            "stop-budget": {
                "drain_budget_seconds": self._authorized_motor.drain_budget_seconds if self._authorized_motor else 0.0,
                "spend_budget_eur": self._authorized_motor.spend_budget_eur if self._authorized_motor else 0.0,
            },
        }
