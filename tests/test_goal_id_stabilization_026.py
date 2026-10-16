"""Isolated reproduction tests for Seed 026 / Catalog 0344: Goal-ID dauerhaft stabilisieren.

Phase 4: Isolierte Reproduktion.
Demonstrates the exact failure path where goal_id and goal_fingerprint are lost
from CoordinationEvent evidence_ref when spec is omitted/absent during feedback,
despite being durably stored in mapping (state['missions'][mission_id]).
"""
import hashlib
import json
import pytest
from pathlib import Path

from scripts.coordination_ledger import AgentID, EventType, HostID, MissionStatus
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.ledger_v1_bridge import _feedback_event, _identity, _recorded_goal
from tests.test_ledger_v1_bridge import FakeHTTP, _home, _ready, _run, _seed, _spec


def test_isolated_reproduction_feedback_event_drops_persisted_goal_without_spec():
    """Unit-level reproduction: _feedback_event ignores mapping['goal_id'] when spec is None."""
    mission = {
        "mission_id": "mission-026",
        "depends_on": [],
        "head": "0123456789abcdef0123456789abcdef01234567",
        "updated_at": "2026-10-12T00:00:00Z",
    }
    mapping = {
        "task_id": "task-026",
        "spec_fingerprint": "a" * 64,
        "source_sha": "0123456789abcdef0123456789abcdef01234567",
        "goal_id": "goal-durable-026",
        "goal_fingerprint": "b" * 64,
    }
    view = {
        "status": "COMPLETE",
        "task_id": "task-026",
        "attempt": 1,
        "accepted_result_id": "result-026",
    }

    # Positive reference: with spec provided, goal_id and goal_fingerprint are preserved
    spec_with_goal = {
        "goal_id": "goal-durable-026",
        "goal_fingerprint": "b" * 64,
    }
    event_with_spec = _feedback_event(
        mission, mapping, spec_with_goal, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, view
    )
    assert event_with_spec is not None
    assert "goal_id=goal-durable-026" in event_with_spec.evidence_ref
    assert f"goal_fingerprint={'b' * 64}" in event_with_spec.evidence_ref

    # Defect fix verification: without spec, _feedback_event now stabilizes the persisted goal_id
    event_without_spec = _feedback_event(
        mission, mapping, None, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, view
    )
    assert event_without_spec is not None
    # FIX VERIFICATION:
    # goal_id and goal_fingerprint are durably preserved from mapping even when spec is None
    assert "goal_id=goal-durable-026" in event_without_spec.evidence_ref
    assert f"goal_fingerprint={'b' * 64}" in event_without_spec.evidence_ref


def test_end_to_end_ledger_final_stabilizes_goal_id_when_specs_omitted_on_feedback(tmp_path):
    """End-to-end bridge test: dispatch records goal, and feedback without spec preserves it."""
    goal_id = "goal-e2e-026"
    goal_fp = "c" * 64
    http = FakeHTTP()

    # Step 1: Initial dispatch with spec containing goal
    home = _home(tmp_path, {"M1": _spec(goal_id=goal_id, goal_fingerprint=goal_fp)})
    _seed(home, [_ready("M1", "m1-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1

    # Verify that bridge state file recorded goal_id and goal_fingerprint in mapping
    state_file = home / "ledger_bridge_state.json"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    m1_mapping = state_data["missions"]["M1"]
    assert m1_mapping.get("goal_id") == goal_id
    assert m1_mapping.get("goal_fingerprint") == goal_fp

    # Step 2: Task completes on controller
    task_id = m1_mapping["task_id"]
    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "res-026"
    http.views[task_id]["attempt"] = 1

    # Step 3: Feedback run where specs file no longer includes M1 (e.g. task completed in new batch)
    tasks_path = home / "ledger_tasks.json"
    tasks_path.write_text(json.dumps({}), encoding="utf-8")  # M1 omitted from specs

    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    # Inspect the resulting FINAL event on the coordination ledger
    ledger_store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    reducer = reduce_store(ledger_store)
    finals = [ev for ev in reducer.events if ev.event_type == EventType.FINAL]
    assert len(finals) == 1
    final_event = finals[0]

    # FIX VERIFICATION:
    # final_event.evidence_ref durably contains goal_id because
    # _feedback_event stabilized goal from m1_mapping["goal_id"]!
    assert f"goal_id={goal_id}" in final_event.evidence_ref
    assert f"goal_fingerprint={goal_fp}" in final_event.evidence_ref


def test_positive_contract_preserves_goal_id_when_spec_is_present(tmp_path):
    """Positive contract path: When spec remains present across feedback, goal_id is preserved."""
    goal_id = "goal-pos-026"
    goal_fp = "d" * 64
    http = FakeHTTP()

    home = _home(tmp_path, {"M1": _spec(goal_id=goal_id, goal_fingerprint=goal_fp)})
    _seed(home, [_ready("M1", "m1-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    state_file = home / "ledger_bridge_state.json"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    task_id = state_data["missions"]["M1"]["task_id"]

    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "res-pos-026"
    http.views[task_id]["attempt"] = 1

    # Spec retained in ledger_tasks.json
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    ledger_store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    reducer = reduce_store(ledger_store)
    finals = [ev for ev in reducer.events if ev.event_type == EventType.FINAL]
    assert len(finals) == 1
    assert f"goal_id={goal_id}" in finals[0].evidence_ref
    assert f"goal_fingerprint={goal_fp}" in finals[0].evidence_ref


def test_negative_contract_half_goal_pair_fails_closed(tmp_path):
    """Negative contract path: Spec with only goal_id but missing goal_fingerprint fails closed (parks)."""
    http = FakeHTTP()
    home = _home(tmp_path, {"M1": _spec(goal_id="only-id")})
    _seed(home, [_ready("M1", "m1-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 0  # Not posted

    ledger_store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    reducer = reduce_store(ledger_store)
    blocked_events = [ev for ev in reducer.events if ev.event_type == EventType.BLOCKED]
    assert len(blocked_events) == 1
    assert "goal_blocked" in blocked_events[0].evidence_ref
    assert blocked_events[0].status == MissionStatus.BLOCKED


def test_negative_mapping_tampered_half_goal_pair_fails_closed():
    """Security regression: If mapping is tampered with only one goal token, it fails closed (no goal in evidence)."""
    mission = {
        "mission_id": "mission-026-neg",
        "depends_on": [],
        "head": "0123456789abcdef0123456789abcdef01234567",
        "updated_at": "2026-10-12T00:00:00Z",
    }
    view = {"status": "COMPLETE", "task_id": "task-neg", "attempt": 1, "accepted_result_id": "res-neg"}

    # Case A: only goal_id in mapping
    mapping_only_id = {
        "task_id": "task-neg",
        "spec_fingerprint": "a" * 64,
        "source_sha": "0123456789abcdef0123456789abcdef01234567",
        "goal_id": "isolated-id",
    }
    assert _recorded_goal(mapping_only_id, None) is None
    ev_a = _feedback_event(mission, mapping_only_id, None, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, view)
    assert ev_a is not None
    assert "goal_id" not in ev_a.evidence_ref

    # Case B: only goal_fingerprint in mapping
    mapping_only_fp = {
        "task_id": "task-neg",
        "spec_fingerprint": "a" * 64,
        "source_sha": "0123456789abcdef0123456789abcdef01234567",
        "goal_fingerprint": "b" * 64,
    }
    assert _recorded_goal(mapping_only_fp, None) is None
    ev_b = _feedback_event(mission, mapping_only_fp, None, AgentID.GOOGLE_WINDOWS, HostID.WINDOWS_REMOTE, view)
    assert ev_b is not None
    assert "goal_fingerprint" not in ev_b.evidence_ref


def test_negative_mapping_corrupted_tokens_fail_closed():
    """Security regression: Injections, control characters, or oversize tokens in mapping fail closed."""
    corrupted_cases = [
        {"goal_id": "bad\nid", "goal_fingerprint": "b" * 64},
        {"goal_id": "bad id with space", "goal_fingerprint": "b" * 64},
        {"goal_id": "bad;semicolon=injection", "goal_fingerprint": "b" * 64},
        {"goal_id": "a" * 129, "goal_fingerprint": "b" * 64},
        {"goal_id": "", "goal_fingerprint": "b" * 64},
        {"goal_id": "valid-id", "goal_fingerprint": "invalid\nfp"},
        {"goal_id": "valid-id", "goal_fingerprint": "fp with space"},
        {"goal_id": "valid-id", "goal_fingerprint": "x" * 129},
        {"goal_id": "valid-id", "goal_fingerprint": ""},
    ]
    for case in corrupted_cases:
        mapping = {
            "task_id": "task-neg",
            "spec_fingerprint": "a" * 64,
            "source_sha": "0123456789abcdef0123456789abcdef01234567",
            **case,
        }
        assert _recorded_goal(mapping, None) is None, f"Expected fail-closed for {case}"


def test_negative_non_string_goal_types_in_mapping_fail_closed():
    """Security regression: Non-string data types planted in mapping must fail closed."""
    invalid_type_cases = [
        {"goal_id": 12345, "goal_fingerprint": "b" * 64},
        {"goal_id": True, "goal_fingerprint": "b" * 64},
        {"goal_id": ["nested", "list"], "goal_fingerprint": "b" * 64},
        {"goal_id": {"nested": "dict"}, "goal_fingerprint": "b" * 64},
        {"goal_id": "valid-id", "goal_fingerprint": 999},
        {"goal_id": "valid-id", "goal_fingerprint": False},
        {"goal_id": "valid-id", "goal_fingerprint": None},
    ]
    for case in invalid_type_cases:
        mapping = {
            "task_id": "task-neg",
            "spec_fingerprint": "a" * 64,
            "source_sha": "0123456789abcdef0123456789abcdef01234567",
            **case,
        }
        assert _recorded_goal(mapping, None) is None, f"Expected fail-closed for {case}"


def test_negative_spec_blocked_takes_precedence_over_mapping_fail_closed(tmp_path):
    """Security regression: If spec has an explicitly malformed goal, it fails closed (parks) and ignores mapping."""
    http = FakeHTTP()
    # Initial valid dispatch
    home = _home(tmp_path, {"M1": _spec(goal_id="good-id", goal_fingerprint="e" * 64)})
    _seed(home, [_ready("M1", "m1-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    state_file = home / "ledger_bridge_state.json"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    task_id = state_data["missions"]["M1"]["task_id"]

    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "res-026"
    http.views[task_id]["attempt"] = 1

    # In feedback run, spec is updated with an invalid goal (only goal_id, no fingerprint)
    tasks_path = home / "ledger_tasks.json"
    tasks_path.write_text(json.dumps({"M1": _spec(goal_id="corrupted-only-id")}), encoding="utf-8")

    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    ledger_store = FileCoordinationStore(home / "coordination_ledger.jsonl")
    reducer = reduce_store(ledger_store)
    # The mission must be parked as BLOCKED, not allowed to finalize with previous goal
    blocked_events = [ev for ev in reducer.events if ev.event_type == EventType.BLOCKED]
    assert len(blocked_events) == 1
    assert "goal_blocked" in blocked_events[0].evidence_ref
    # No FINAL event may be emitted
    finals = [ev for ev in reducer.events if ev.event_type == EventType.FINAL]
    assert len(finals) == 0


def test_persistence_and_restart_idempotency_with_stabilized_goal_id(tmp_path):
    """Phase 7: Persistence & Restart test: verifies cold reload, zero duplicate events, and state idempotency."""
    goal_id = "goal-restart-026"
    goal_fp = "f" * 64
    http = FakeHTTP()

    # Step 1: Initial dispatch with goal
    home = _home(tmp_path, {"M1": _spec(goal_id=goal_id, goal_fingerprint=goal_fp)})
    _seed(home, [_ready("M1", "m1-assign")])
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1

    # Step 2: Task completes on controller
    state_file = home / "ledger_bridge_state.json"
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    task_id = state_data["missions"]["M1"]["task_id"]
    http.views[task_id]["status"] = "COMPLETE"
    http.views[task_id]["accepted_result_id"] = "res-restart-026"
    http.views[task_id]["attempt"] = 1

    # Step 3: Feedback run where spec is omitted from tasks file
    tasks_path = home / "ledger_tasks.json"
    tasks_path.write_text(json.dumps({}), encoding="utf-8")
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err

    # Capture persisted disk state after successful feedback
    ledger_path = home / "coordination_ledger.jsonl"
    before_ledger = ledger_path.read_text(encoding="utf-8")
    before_state = state_file.read_text(encoding="utf-8")

    # Step 4: First cold restart / replay
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1, "Replay must not post additional tasks"
    assert ledger_path.read_text(encoding="utf-8") == before_ledger, "Replay must not append duplicate events"
    assert state_file.read_text(encoding="utf-8") == before_state, "State file must be idempotent after replay"

    # Step 5: Second cold restart with fresh store reduction and validation
    code, out, err, log, lines = _run(home, http)
    assert code == 0, err
    assert len(http.posts) == 1
    assert ledger_path.read_text(encoding="utf-8") == before_ledger

    fresh_store = FileCoordinationStore(ledger_path)
    fresh_reducer = reduce_store(fresh_store)
    mission_view = fresh_reducer.get_mission("M1")
    assert mission_view is not None
    assert mission_view["status"] == MissionStatus.DONE

    finals = [ev for ev in fresh_reducer.events if ev.event_type == EventType.FINAL]
    assert len(finals) == 1
    assert f"goal_id={goal_id}" in finals[0].evidence_ref
    assert f"goal_fingerprint={goal_fp}" in finals[0].evidence_ref

    reloaded_state = json.loads(state_file.read_text(encoding="utf-8"))
    m1_state = reloaded_state["missions"]["M1"]
    assert m1_state["status"] == "FINAL_DONE"
    assert m1_state["goal_id"] == goal_id
    assert m1_state["goal_fingerprint"] == goal_fp
    assert f"goal_id={goal_id}" in m1_state["evidence_ref"]



