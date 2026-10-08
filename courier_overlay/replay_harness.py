"""Overlay Event Replay & Visual Acceptance Harness (Lane L5).

Provides a deterministic local replay fixture for lifecycle events:
- Recorded canonical lifecycle event sequences:
  (e.g., CREATED -> ASSIGNED -> STARTED -> PROGRESS -> RESULT -> COMPLETE/BLOCKED).
- Step-by-step and batch playback for test and visual verification without LLM calls.
- Invariant verification for worker state transitions.
- Low-load acceptance canary for robot/package/canary behavior.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from courier_overlay.event_bus import EVENT_TYPES, emit
from courier_overlay.state_machine import OverlayStateMachine, WorkerState


@dataclasses.dataclass(frozen=True)
class ReplayEvent:
    agent_id: str
    task_id: str
    event_type: str
    short_summary: str
    delay_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "short_summary": self.short_summary,
            "delay_ms": self.delay_ms,
        }


# Canonical lifecycle sequences
LIFECYCLE_SUCCESS: list[ReplayEvent] = [
    ReplayEvent("worker-alpha", "task-101", "ORCHESTRATOR_CREATED_TASK", "Task created by orchestrator"),
    ReplayEvent("worker-alpha", "task-101", "TASK_ASSIGNED", "Task assigned to worker-alpha"),
    ReplayEvent("worker-alpha", "task-101", "WORKER_CLAIMED", "Worker claimed task"),
    ReplayEvent("worker-alpha", "task-101", "WORKER_STARTED", "Execution started"),
    ReplayEvent("worker-alpha", "task-101", "WORKER_PROGRESS", "Step 1/2 complete"),
    ReplayEvent("worker-alpha", "task-101", "RESULT_READY", "Outcome produced"),
    ReplayEvent("worker-alpha", "task-101", "CUSTOMS_ENTER", "Entering verification customs"),
    ReplayEvent("worker-alpha", "task-101", "CUSTOMS_APPROVED", "Verification passed"),
    ReplayEvent("worker-alpha", "task-101", "TASK_COMPLETE", "Task finalized successfully"),
]

LIFECYCLE_BLOCKED: list[ReplayEvent] = [
    ReplayEvent("worker-beta", "task-102", "TASK_ASSIGNED", "Task assigned to worker-beta"),
    ReplayEvent("worker-beta", "task-102", "WORKER_CLAIMED", "Worker claimed task"),
    ReplayEvent("worker-beta", "task-102", "WORKER_STARTED", "Execution started"),
    ReplayEvent("worker-beta", "task-102", "TASK_BLOCKED", "Execution failed on unrecoverable error"),
]

LIFECYCLE_CUSTOMS_REJECTED: list[ReplayEvent] = [
    ReplayEvent("worker-gamma", "task-103", "TASK_ASSIGNED", "Task assigned to worker-gamma"),
    ReplayEvent("worker-gamma", "task-103", "WORKER_STARTED", "Execution started"),
    ReplayEvent("worker-gamma", "task-103", "RESULT_READY", "Outcome produced"),
    ReplayEvent("worker-gamma", "task-103", "CUSTOMS_ENTER", "Entering customs verification"),
    ReplayEvent("worker-gamma", "task-103", "CUSTOMS_REJECTED", "Customs gate rejected result"),
    ReplayEvent("worker-gamma", "task-103", "RESULT_REJECTED", "Result rejected by verifier"),
]

LIFECYCLE_MULTI_AGENT: list[ReplayEvent] = [
    ReplayEvent("agent-1", "task-201", "TASK_ASSIGNED", "Agent 1 assigned task-201"),
    ReplayEvent("agent-2", "task-202", "TASK_ASSIGNED", "Agent 2 assigned task-202"),
    ReplayEvent("agent-1", "task-201", "WORKER_STARTED", "Agent 1 started"),
    ReplayEvent("agent-2", "task-202", "WORKER_STARTED", "Agent 2 started"),
    ReplayEvent("agent-1", "task-201", "WORKER_PROGRESS", "Agent 1 working"),
    ReplayEvent("agent-2", "task-202", "TASK_BLOCKED", "Agent 2 hit quota"),
    ReplayEvent("agent-1", "task-201", "TASK_COMPLETE", "Agent 1 finished"),
]

CANONICAL_SEQUENCES = {
    "success": LIFECYCLE_SUCCESS,
    "blocked": LIFECYCLE_BLOCKED,
    "customs_rejected": LIFECYCLE_CUSTOMS_REJECTED,
    "multi_agent": LIFECYCLE_MULTI_AGENT,
}


class ReplayHarness:
    """Deterministic replay fixture for desktop overlay visualization."""

    def __init__(self, bus_path: str, state_machine: Optional[OverlayStateMachine] = None):
        self.bus_path = bus_path
        self.state_machine = state_machine or OverlayStateMachine(bus_path)
        self.events: list[ReplayEvent] = []
        self.cursor: int = 0
        self.history: list[dict[str, str]] = []  # [{agent_id: status, ...}]

    def load_sequence(self, sequence: list[ReplayEvent] | list[dict[str, Any]]) -> None:
        """Load an event sequence to replay."""
        self.events = []
        for item in sequence:
            if isinstance(item, ReplayEvent):
                self.events.append(item)
            elif isinstance(item, dict):
                self.events.append(ReplayEvent(
                    agent_id=item["agent_id"],
                    task_id=item["task_id"],
                    event_type=item["event_type"],
                    short_summary=item["short_summary"],
                    delay_ms=item.get("delay_ms", 0),
                ))
            else:
                raise TypeError(f"Unsupported event type: {type(item)}")
        self.cursor = 0
        self.history = []

    def remaining(self) -> int:
        return max(0, len(self.events) - self.cursor)

    def step(self) -> Optional[dict[str, Any]]:
        """Emit next event, fold into state machine, and snapshot state."""
        if self.cursor >= len(self.events):
            return None

        event = self.events[self.cursor]
        self.cursor += 1

        # Validate event type
        if event.event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event.event_type}")

        # Emit to bus
        emit(
            self.bus_path,
            agent_id=event.agent_id,
            task_id=event.task_id,
            event_type=event.event_type,
            short_summary=event.short_summary,
        )

        # Sync state machine
        self.state_machine.sync()

        # Capture status snapshot
        snapshot = {w.agent_id: w.status for w in self.state_machine.get_snapshot()}
        self.history.append(snapshot)

        return {
            "event": event.to_dict(),
            "cursor": self.cursor,
            "snapshot": snapshot,
        }

    def play_all(self) -> list[dict[str, Any]]:
        """Play all remaining events in the sequence."""
        results = []
        while self.remaining() > 0:
            res = self.step()
            if res:
                results.append(res)
        return results

    def reset(self) -> None:
        """Reset sequence playback cursor without modifying bus file."""
        self.cursor = 0
        self.history = []

    def verify_state_invariants(self) -> dict[str, Any]:
        """Verify that state transitions satisfy deterministic rules."""
        valid_statuses = {"IDLE", "ASSIGNED", "WORKING", "BLOCKED"}
        violations = []

        for idx, snap in enumerate(self.history):
            for agent, status in snap.items():
                if status not in valid_statuses:
                    violations.append({
                        "step": idx,
                        "agent_id": agent,
                        "invalid_status": status,
                    })

        return {
            "valid": len(violations) == 0,
            "steps_checked": len(self.history),
            "violations": violations,
        }


def run_canary_acceptance(bus_path: str) -> dict[str, Any]:
    """Runs a complete visual replay acceptance suite against the provided bus.

    Deterministic, offline, 0 LLM tokens, 0 network requests.
    """
    results = {}
    total_events = 0

    for name, seq in CANONICAL_SEQUENCES.items():
        sm = OverlayStateMachine(bus_path)
        harness = ReplayHarness(bus_path, state_machine=sm)
        harness.load_sequence(seq)
        played = harness.play_all()
        invariants = harness.verify_state_invariants()

        total_events += len(played)
        results[name] = {
            "events_replayed": len(played),
            "invariants_valid": invariants["valid"],
            "final_snapshot": {w.agent_id: w.status for w in sm.get_snapshot()},
        }

    all_valid = all(r["invariants_valid"] for r in results.values())
    return {
        "status": "PASS" if all_valid else "FAIL",
        "sequences_tested": len(CANONICAL_SEQUENCES),
        "total_events_replayed": total_events,
        "details": results,
    }
