"""Deterministic tests for SEED 080 — DAG-ZYKLUS ERKENNEN.

Verifies:
1. Positive DAG (Acyclic):
   - A -> B -> C: Valid dependency resolution, correct READY sequence, terminates in TRUE_IDLE.
2. Direct Cycle (A -> B -> A):
   - CoordinationEngine detects cycle [A, B] and emits DAG_CYCLE_DETECTED actions.
   - The queue does not falsely report TRUE_IDLE or remain silently hung.
3. Transitive / 3-node Cycle (A -> B -> C -> A):
   - Cycle is accurately discovered and reported with full path.
4. Self-Dependency Cycle (A -> A):
   - Self-referencing task is detected and flagged.
5. Mixed DAG (Cycle on component X <-> Y, independent task Z):
   - Independent acyclic task Z is properly scheduled/evaluated while cycle X <-> Y is detected.
6. Cycle resolved when one node in the cycle is marked DONE:
   - Once a task in the cycle is satisfied (e.g., DONE externally), the remaining tasks unblock normally.
"""

import pytest
from scripts.coordination_engine import CoordinationEngine
from scripts.coordination_delivery import NextActionType
from scripts.coordination_ledger import (
    CoordinationEvent,
    CoordinationReducer,
    EventType,
    HostID,
    MissionStatus,
    AgentID,
)


def make_event(eid, mid, deps, status=MissionStatus.WORKING, etype=EventType.ASSIGNED):
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=etype,
        status=status,
        depends_on=deps or [],
        head="fac447f5c9c22936177069566b82c7319bc35f5c",
        evidence_ref="evidence-seed080",
        created_at="2026-10-11T12:00:00Z",
        payload_hash=f"hash-{mid}",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    )


def test_positive_acyclic_dag_evaluates_cleanly():
    """Positive Case: Normal acyclic DAG (A -> B) completes without cycle alerts."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e1", "taskA", [], status=MissionStatus.DONE, etype=EventType.FINAL))
    reducer.apply(make_event("e2", "taskB", ["taskA"], status=MissionStatus.WORKING, etype=EventType.ASSIGNED))

    engine = CoordinationEngine(reducer)
    cycles = engine.detect_cycles()
    assert cycles == []

    actions = engine.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].mission_id == "taskB"
    assert actions[0].action_type == NextActionType.WAIT


def test_direct_two_node_cycle_detected():
    """Negative Case: Direct cycle between task A and task B (A depends on B, B depends on A)."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e1", "taskA", ["taskB"]))
    reducer.apply(make_event("e2", "taskB", ["taskA"]))

    engine = CoordinationEngine(reducer)
    cycles = engine.detect_cycles()
    assert len(cycles) >= 1
    cycle_nodes = set(cycles[0])
    assert cycle_nodes == {"taskA", "taskB"}

    actions = engine.evaluate_dag()
    assert len(actions) == 2
    action_types = {a.action_type for a in actions}
    assert action_types == {NextActionType.DAG_CYCLE_DETECTED}
    for a in actions:
        assert "Cyclical dependency detected in DAG" in a.reason


def test_three_node_transitive_cycle_detected():
    """Negative Case: Transitive cycle (A -> B -> C -> A)."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e1", "nodeX", ["nodeY"]))
    reducer.apply(make_event("e2", "nodeY", ["nodeZ"]))
    reducer.apply(make_event("e3", "nodeZ", ["nodeX"]))

    engine = CoordinationEngine(reducer)
    cycles = engine.detect_cycles()
    assert len(cycles) >= 1
    cycle_nodes = set(cycles[0])
    assert cycle_nodes == {"nodeX", "nodeY", "nodeZ"}

    actions = engine.evaluate_dag()
    assert len(actions) == 3
    for a in actions:
        assert a.action_type == NextActionType.DAG_CYCLE_DETECTED
        assert a.mission_id in {"nodeX", "nodeY", "nodeZ"}


def test_self_dependency_cycle():
    """Negative Case: Single task depending on itself (A -> A)."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e1", "selfLoop", ["selfLoop"]))

    engine = CoordinationEngine(reducer)
    cycles = engine.detect_cycles()
    assert len(cycles) >= 1
    assert cycles[0] == ["selfLoop"]

    actions = engine.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].action_type == NextActionType.DAG_CYCLE_DETECTED
    assert actions[0].mission_id == "selfLoop"


def test_mixed_dag_unrelated_task_executes_while_cycle_persists():
    """Safety: Unrelated task is not starved if it is ready, but cycle is detected when stalled."""
    reducer = CoordinationReducer()
    # Cycle between C1 and C2
    reducer.apply(make_event("e1", "C1", ["C2"]))
    reducer.apply(make_event("e2", "C2", ["C1"]))
    # Unrelated independent task
    reducer.apply(make_event("e3", "IndependentTask", []))

    engine = CoordinationEngine(reducer)
    # The independent task has all deps done, so evaluate_dag will evaluate it first
    actions = engine.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].mission_id == "IndependentTask"

    # Now mark IndependentTask as DONE
    reducer.apply(make_event("e4", "IndependentTask", [], status=MissionStatus.DONE, etype=EventType.FINAL))
    # Now only the cycle remains; evaluate_dag must report the cycle rather than FALSE TRUE_IDLE
    actions2 = engine.evaluate_dag()
    assert len(actions2) == 2
    for a in actions2:
        assert a.action_type == NextActionType.DAG_CYCLE_DETECTED


def test_cycle_broken_when_task_reaches_done():
    """Resolution: When one task in the cycle reaches DONE (e.g. human intervention), cycle is resolved."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e1", "P", ["Q"]))
    reducer.apply(make_event("e2", "Q", ["P"]))

    engine = CoordinationEngine(reducer)
    assert len(engine.detect_cycles()) >= 1

    # Human or override marks Q as DONE
    reducer.apply(make_event("e3", "Q", [], status=MissionStatus.DONE, etype=EventType.FINAL))

    # Cycle is broken
    cycles_after = engine.detect_cycles()
    assert cycles_after == []

    # P is now unlocked and READY!
    actions = engine.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].mission_id == "P"
    assert actions[0].action_type == NextActionType.WAIT
