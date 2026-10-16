"""Deterministic tests for SEED 079 — UNABHÄNGIGE ARBEIT WEITERFÜHREN.

Verifies:
1. Parallel Independent Branches Continue:
   - When Branch A is stalled (BLOCKED, ERROR, or CYCLICAL), independent Branch B
     remains fully executable and is returned by select_all_ready() and select_first_ready().
2. Multiple Independent Tasks Retrieved:
   - select_all_ready() deterministically returns all ready independent tasks in FIFO order.
3. Transitive Independence Check:
   - is_independent_of(candidate, target) correctly returns True when tasks belong
     to disjoint DAG subgraphs, and False when direct or transitive dependencies exist.
4. Agent Filtering for Independent Work:
   - select_all_ready(agent_id) filters tasks assigned to a specific worker while
     preserving ready state for unassigned / assigned work.
5. Mixed Topology (Convergent and Divergent Branches):
   - In a complex DAG with both dependent and independent trees, stalled nodes do not
     bleed into independent roots or disjoint leaves.
6. Fail-Closed Exclusion of Meta-Actions:
   - select_all_ready() strictly excludes TRUE_IDLE, DAG_CYCLE_DETECTED, and HUMAN_ACTION_REQUIRED.
"""

import pytest
from scripts.coordination_engine import CoordinationEngine
from scripts.coordination_delivery import NextActionType, AgentID
from scripts.coordination_ledger import (
    CoordinationEvent,
    CoordinationReducer,
    EventType,
    HostID,
    MissionStatus,
)


def make_event(
    eid: str,
    mid: str,
    deps: list[str] = None,
    status: MissionStatus = MissionStatus.WORKING,
    etype: EventType = EventType.ASSIGNED,
    evidence_ref: str = "spec",
    created_at: str = "2026-10-12T10:00:00Z",
    agent_id: AgentID = AgentID.GOOGLE_WINDOWS,
) -> CoordinationEvent:
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=agent_id,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=etype,
        status=status,
        depends_on=deps or [],
        head="fac447f5c9c22936177069566b82c7319bc35f5c",
        evidence_ref=evidence_ref,
        created_at=created_at,
        payload_hash=f"hash-{eid}",
        ownership=agent_id.value,
    )


def test_independent_work_continues_while_other_branch_blocked():
    """Beweis 1: Unabhängige Zweige laufen ungehindert weiter, wenn ein Zweig BLOCKED ist."""
    reducer = CoordinationReducer()
    # Zweig 1: Blockiert
    reducer.apply(make_event("e-1", "branch1_blocked", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED, created_at="2026-10-12T10:00:00Z"))
    reducer.apply(make_event("e-2", "branch1_child", deps=["branch1_blocked"], created_at="2026-10-12T10:01:00Z"))

    # Zweig 2: Völlig unabhängig und bereit
    reducer.apply(make_event("e-3", "branch2_independent", deps=[], created_at="2026-10-12T10:02:00Z"))

    engine = CoordinationEngine(reducer)
    ready = engine.select_all_ready()
    assert len(ready) == 1
    assert ready[0].mission_id == "branch2_independent"
    assert ready[0].action_type == NextActionType.WAIT

    # Structural independence check
    assert engine.is_independent_of("branch2_independent", "branch1_blocked") is True
    assert engine.is_independent_of("branch2_independent", "branch1_child") is True


def test_multiple_independent_ready_tasks_fifo_ordering():
    """Beweis 2: select_all_ready() liefert mehrere unabhängige Aufgaben deterministisch nach FIFO."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "task_early", deps=[], created_at="2026-10-12T10:01:00Z"))
    reducer.apply(make_event("e-b", "task_late", deps=[], created_at="2026-10-12T10:05:00Z"))
    reducer.apply(make_event("e-c", "task_mid", deps=[], created_at="2026-10-12T10:03:00Z"))

    engine = CoordinationEngine(reducer)
    ready = engine.select_all_ready()
    assert [r.mission_id for r in ready] == ["task_early", "task_mid", "task_late"]


def test_is_independent_of_transitive_detection():
    """Beweis 3: is_independent_of erkennt direkte und transitive Abhängigkeiten korrekt."""
    reducer = CoordinationReducer()
    # Kette: A -> B -> C
    reducer.apply(make_event("e-a", "A", deps=[]))
    reducer.apply(make_event("e-b", "B", deps=["A"]))
    reducer.apply(make_event("e-c", "C", deps=["B"]))

    # Unabhängige Aufgabe X
    reducer.apply(make_event("e-x", "X", deps=[]))

    engine = CoordinationEngine(reducer)
    # C hängt transitiv von A ab -> NICHT unabhängig
    assert engine.is_independent_of("C", "A") is False
    assert engine.is_independent_of("A", "C") is False
    assert engine.is_independent_of("B", "A") is False
    assert engine.is_independent_of("C", "B") is False

    # X ist unabhängig von A, B, C
    assert engine.is_independent_of("X", "A") is True
    assert engine.is_independent_of("X", "B") is True
    assert engine.is_independent_of("X", "C") is True
    assert engine.is_independent_of("A", "X") is True


def test_independent_work_continues_during_cycle_stall():
    """Beweis 4: Unabhängige Aufgaben werden weitergeführt, selbst wenn andere Aufgaben in einem Zyklus stecken."""
    reducer = CoordinationReducer()
    # Zyklus: C1 <-> C2
    reducer.apply(make_event("e-c1", "c1", deps=["c2"], created_at="2026-10-12T10:00:00Z"))
    reducer.apply(make_event("e-c2", "c2", deps=["c1"], created_at="2026-10-12T10:01:00Z"))

    # Unabhängig: Ready
    reducer.apply(make_event("e-indep", "independent_task", deps=[], created_at="2026-10-12T10:02:00Z"))

    engine = CoordinationEngine(reducer)
    ready = engine.select_all_ready()
    assert len(ready) == 1
    assert ready[0].mission_id == "independent_task"

    first = engine.select_first_ready()
    assert first is not None
    assert first.mission_id == "independent_task"


def test_select_all_ready_agent_filter():
    """Beweis 5: select_all_ready filtert korrekt nach target_agent."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-win", "task_win", deps=[], agent_id=AgentID.GOOGLE_WINDOWS, created_at="2026-10-12T10:00:00Z"))
    reducer.apply(make_event("e-mac", "task_mac", deps=[], agent_id=AgentID.GOOGLE_MAC, created_at="2026-10-12T10:01:00Z"))

    engine = CoordinationEngine(reducer)
    win_ready = engine.select_all_ready(agent_id=AgentID.GOOGLE_WINDOWS)
    assert len(win_ready) == 1
    assert win_ready[0].mission_id == "task_win"

    mac_ready = engine.select_all_ready(agent_id=AgentID.GOOGLE_MAC)
    assert len(mac_ready) == 1
    assert mac_ready[0].mission_id == "task_mac"


def test_mixed_topology_disjoint_subgraphs():
    """Beweis 6: Gemischte Topologie mit partiell erledigten und partiell gesperrten Zweigen."""
    reducer = CoordinationReducer()
    # Subgraph 1 (Failing branch): Parent BLOCKED -> child locked
    reducer.apply(make_event("e-g1", "g1_root", deps=[], status=MissionStatus.BLOCKED, etype=EventType.BLOCKED, created_at="2026-10-12T09:00:00Z"))
    reducer.apply(make_event("e-g2", "g2_locked", deps=["g1_root"], created_at="2026-10-12T09:10:00Z"))

    # Subgraph 2 (Healthy branch): Parent DONE, child WORKING -> ready to advance
    reducer.apply(make_event("e-h1", "h1_root", deps=[], status=MissionStatus.DONE, etype=EventType.FINAL, created_at="2026-10-12T09:05:00Z"))
    reducer.apply(make_event("e-h2", "h2_ready", deps=["h1_root"], status=MissionStatus.WORKING, etype=EventType.ASSIGNED, created_at="2026-10-12T09:15:00Z"))

    # Subgraph 3 (Independent root): No deps, WORKING
    reducer.apply(make_event("e-i1", "i1_standalone", deps=[], status=MissionStatus.WORKING, etype=EventType.ASSIGNED, created_at="2026-10-12T09:25:00Z"))

    engine = CoordinationEngine(reducer)
    ready = engine.select_all_ready()
    ready_ids = [r.mission_id for r in ready]

    assert "h2_ready" in ready_ids
    assert "i1_standalone" in ready_ids
    assert "g1_root" not in ready_ids
    assert "g2_locked" not in ready_ids

    # Order must be FIFO: h2_ready (09:15) then i1_standalone (09:25)
    assert ready_ids == ["h2_ready", "i1_standalone"]
    assert engine.is_independent_of("h2_ready", "g1_root") is True
    assert engine.is_independent_of("i1_standalone", "g2_locked") is True


def test_negative_self_independence_returns_false():
    """Negativtest 1: Eine Mission ist nicht unabhängig von sich selbst."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-1", "task_self", deps=[]))
    engine = CoordinationEngine(reducer)
    assert engine.is_independent_of("task_self", "task_self") is False


def test_negative_deep_transitive_diamond_dependency_not_independent():
    """Negativtest 2: Diamond-Abhängigkeit (A -> B, A -> C, (B, C) -> D) stellt Abhängigkeit sicher."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "A", deps=[]))
    reducer.apply(make_event("e-b", "B", deps=["A"]))
    reducer.apply(make_event("e-c", "C", deps=["A"]))
    reducer.apply(make_event("e-d", "D", deps=["B", "C"]))

    engine = CoordinationEngine(reducer)
    assert engine.is_independent_of("D", "A") is False
    assert engine.is_independent_of("A", "D") is False
    assert engine.is_independent_of("D", "B") is False
    assert engine.is_independent_of("D", "C") is False

    # B und C sind untereinander unabhängig
    assert engine.is_independent_of("B", "C") is True
    assert engine.is_independent_of("C", "B") is True


def test_negative_all_blocked_returns_empty_ready_list():
    """Negativtest 3: Wenn alle Aufgaben blockiert oder gesperrt sind, liefert select_all_ready() eine leere Liste."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-1", "b1", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED))
    reducer.apply(make_event("e-2", "b2", deps=["b1"]))

    engine = CoordinationEngine(reducer)
    ready = engine.select_all_ready()
    assert ready == []
    assert engine.select_first_ready() is None


def test_negative_ghost_or_nonexistent_mission_independence():
    """Sicherheitstest 4: Unbekannte oder nicht existente Missions-IDs werden sicher behandelt."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-1", "existing_task", deps=[]))

    engine = CoordinationEngine(reducer)
    # Existierende Mission zu Ghost: strukturell unabhängig
    assert engine.is_independent_of("existing_task", "ghost_nonexistent") is True
    assert engine.is_independent_of("ghost_nonexistent", "existing_task") is True
    assert engine.is_independent_of("ghost_a", "ghost_b") is True


def test_persistence_and_restart_independent_work(tmp_path):
    """Beweis 7: Persistenz über FileCoordinationStore, Kaltstart-Rekonstruktion & Idempotenz für unabhängige Arbeit."""
    import subprocess
    import sys
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore

    ledger_path = tmp_path / "coordination_ledger_079.jsonl"
    store = FileCoordinationStore(ledger_path)

    # 1. Branch A: Blocked
    ev_a1 = make_event("ev-a1", "branch_a_blocked", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED, created_at="2026-10-12T09:00:00Z")
    ev_a2 = make_event("ev-a2", "branch_a_locked", deps=["branch_a_blocked"], created_at="2026-10-12T09:05:00Z")

    # 2. Branch B: Independent, ready
    ev_b1 = make_event("ev-b1", "branch_b_ready1", deps=[], created_at="2026-10-12T09:10:00Z")
    ev_b2 = make_event("ev-b2", "branch_b_ready2", deps=[], created_at="2026-10-12T09:15:00Z")

    store.write_event(ev_a1)
    store.write_event(ev_a2)
    store.write_event(ev_b1)
    store.write_event(ev_b2)

    # 3. Kaltstart aus dem Ledger
    cold_reducer = reduce_store(store)
    cold_engine = CoordinationEngine(cold_reducer)

    ready = cold_engine.select_all_ready()
    ready_ids = [r.mission_id for r in ready]
    assert ready_ids == ["branch_b_ready1", "branch_b_ready2"]
    assert cold_engine.is_independent_of("branch_b_ready1", "branch_a_blocked") is True
    assert cold_engine.is_independent_of("branch_b_ready2", "branch_a_locked") is True

    # 4. Idempotenz-Prüfung: Erneutes Schreiben/Anwenden ignoriert Duplikate
    assert cold_reducer.apply(ev_b1) is False
    assert [r.mission_id for r in cold_engine.select_all_ready()] == ["branch_b_ready1", "branch_b_ready2"]

    # 5. Physischer Subprozess-Kaltstart
    check_code = f"""
import sys
from pathlib import Path
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.coordination_engine import CoordinationEngine

store = FileCoordinationStore(Path(r"{ledger_path}"))
reducer = reduce_store(store)
engine = CoordinationEngine(reducer)

ready = [r.mission_id for r in engine.select_all_ready()]
assert ready == ["branch_b_ready1", "branch_b_ready2"], f"Unexpected ready: {{ready}}"
assert engine.is_independent_of("branch_b_ready1", "branch_a_blocked") is True
print("SUBPROCESS_RESTART_INDEPENDENT_WORK_SUCCESS")
"""
    result = subprocess.run([sys.executable, "-c", check_code], capture_output=True, text=True, check=True)
    assert "SUBPROCESS_RESTART_INDEPENDENT_WORK_SUCCESS" in result.stdout


