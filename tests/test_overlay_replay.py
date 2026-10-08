import os
import tempfile
import pytest

from courier_overlay.replay import (
    CANONICAL_SEQUENCES,
    LIFECYCLE_BLOCKED,
    LIFECYCLE_CUSTOMS_REJECTED,
    LIFECYCLE_MULTI_AGENT,
    LIFECYCLE_SUCCESS,
    ReplayEvent,
    ReplayHarness,
    run_canary_acceptance,
)
from courier_overlay.state_machine import OverlayStateMachine


def test_replay_harness_step_by_step():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        sm = OverlayStateMachine(bus)
        harness = ReplayHarness(bus, state_machine=sm)
        harness.load_sequence(LIFECYCLE_SUCCESS)

        assert harness.remaining() == len(LIFECYCLE_SUCCESS)

        # Step 1: ORCHESTRATOR_CREATED_TASK (not a worker state change)
        step1 = harness.step()
        assert step1 is not None
        assert step1["cursor"] == 1
        assert step1["event"]["event_type"] == "ORCHESTRATOR_CREATED_TASK"

        # Step 2: TASK_ASSIGNED -> ASSIGNED
        step2 = harness.step()
        assert step2 is not None
        assert step2["snapshot"]["worker-alpha"] == "ASSIGNED"

        # Step 3: WORKER_CLAIMED -> ASSIGNED
        step3 = harness.step()
        assert step3 is not None
        assert step3["snapshot"]["worker-alpha"] == "ASSIGNED"

        # Step 4: WORKER_STARTED -> WORKING
        step4 = harness.step()
        assert step4 is not None
        assert step4["snapshot"]["worker-alpha"] == "WORKING"

        # Step 5: WORKER_PROGRESS -> WORKING
        step5 = harness.step()
        assert step5 is not None
        assert step5["snapshot"]["worker-alpha"] == "WORKING"

        # Play remaining
        remaining = harness.play_all()
        assert len(remaining) == len(LIFECYCLE_SUCCESS) - 5
        assert harness.remaining() == 0

        # Final state should be IDLE
        final_worker = next(w for w in sm.get_snapshot() if w.agent_id == "worker-alpha")
        assert final_worker.status == "IDLE"
        assert final_worker.current_task is None

        # Check invariants
        inv = harness.verify_state_invariants()
        assert inv["valid"] is True
        assert inv["steps_checked"] == len(LIFECYCLE_SUCCESS)


def test_replay_harness_blocked_lifecycle():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        harness = ReplayHarness(bus)
        harness.load_sequence(LIFECYCLE_BLOCKED)
        harness.play_all()

        worker = next(w for w in harness.state_machine.get_snapshot() if w.agent_id == "worker-beta")
        assert worker.status == "BLOCKED"
        assert worker.current_task == "task-102"


def test_replay_harness_customs_rejected():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        harness = ReplayHarness(bus)
        harness.load_sequence(LIFECYCLE_CUSTOMS_REJECTED)
        harness.play_all()

        worker = next(w for w in harness.state_machine.get_snapshot() if w.agent_id == "worker-gamma")
        assert worker.status == "BLOCKED"


def test_replay_harness_multi_agent():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        harness = ReplayHarness(bus)
        harness.load_sequence(LIFECYCLE_MULTI_AGENT)
        harness.play_all()

        snap = {w.agent_id: w.status for w in harness.state_machine.get_snapshot()}
        assert snap["agent-1"] == "IDLE"
        assert snap["agent-2"] == "BLOCKED"


def test_replay_harness_invalid_event_type():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "bus.jsonl")
        harness = ReplayHarness(bus)
        harness.load_sequence([
            ReplayEvent("bad-agent", "task-bad", "NONEXISTENT_EVENT_TYPE", "Bad event"),
        ])
        with pytest.raises(ValueError, match="Unknown event type"):
            harness.step()


def test_replay_canary_acceptance():
    with tempfile.TemporaryDirectory() as td:
        bus = os.path.join(td, "canary_bus.jsonl")
        report = run_canary_acceptance(bus)

        assert report["status"] == "PASS"
        assert report["sequences_tested"] == 4
        assert report["total_events_replayed"] > 20
        assert report["details"]["success"]["final_snapshot"]["worker-alpha"] == "IDLE"
        assert report["details"]["blocked"]["final_snapshot"]["worker-beta"] == "BLOCKED"
