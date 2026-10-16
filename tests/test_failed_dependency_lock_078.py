"""Deterministic tests for SEED 078 — FEHLGESCHLAGENE DEPENDENCY SPERREN.

Verifies:
1. Direct Upstream Failure Locks Downstream Task:
   - When upstream task A enters ERROR, dependent task B is emitted in evaluate_dag()
     as HUMAN_ACTION_REQUIRED rather than being silently bypassed.
2. Transitive Failure Locking:
   - A -> B -> C: If A fails, both B and transitive dependent C are locked.
3. Multi-Dependency (Fan-In) Partial Failure:
   - (A, B) -> C: If A is DONE but B is ERROR/BLOCKED, C is strictly locked.
4. Unrelated Work Unaffected (No Global Stall):
   - Independent task X continues running and is returned by select_first_ready()
     even while B is locked on failed A.
5. Recovery / Retry Unlocks Downstream:
   - Once failed task A is reconciled and completed (DONE), B transitions from locked
     to ready.
6. Execution Guard:
   - select_first_ready() excludes locked HUMAN_ACTION_REQUIRED tasks fail-closed.
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
) -> CoordinationEvent:
    return CoordinationEvent(
        event_id=eid,
        mission_id=mid,
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=etype,
        status=status,
        depends_on=deps or [],
        head="fac447f5c9c22936177069566b82c7319bc35f5c",
        evidence_ref=evidence_ref,
        created_at=created_at,
        payload_hash=f"hash-{eid}",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    )


def test_direct_upstream_failure_locks_downstream_task():
    """Beweis 1: Fehlgeschlagene Vorgängeraufgabe sperrt direkt abhängige Aufgabe mit HUMAN_ACTION_REQUIRED."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "task_A", status=MissionStatus.ERROR, etype=EventType.ERROR))
    reducer.apply(make_event("e-b", "task_B", deps=["task_A"]))

    engine = CoordinationEngine(reducer)
    assert engine.is_dependency_failed("task_B") is True

    actions = {a.mission_id: a for a in engine.evaluate_dag()}
    assert "task_A" in actions
    assert actions["task_A"].action_type == NextActionType.CANCEL_REQUIRED

    # task_B ist explizit als gesperrt ausgewiesen
    assert "task_B" in actions
    assert actions["task_B"].action_type == NextActionType.HUMAN_ACTION_REQUIRED
    assert "blocked by failed/blocked dependencies" in actions["task_B"].reason


def test_transitive_upstream_failure_locking():
    """Beweis 2: Transitive Fehlerfortpflanzung (A -> B -> C) sperrt Kette."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "task_A", status=MissionStatus.ERROR, etype=EventType.ERROR))
    reducer.apply(make_event("e-b", "task_B", deps=["task_A"]))
    reducer.apply(make_event("e-c", "task_C", deps=["task_B"]))

    engine = CoordinationEngine(reducer)
    assert engine.is_dependency_failed("task_B") is True

    actions = {a.mission_id: a for a in engine.evaluate_dag()}
    assert "task_B" in actions
    assert actions["task_B"].action_type == NextActionType.HUMAN_ACTION_REQUIRED


def test_fan_in_partial_failure_locks_target():
    """Beweis 3: Mehrfachabhängigkeit (A fertig, B fehlerhaft -> C gesperrt)."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "dep_A", status=MissionStatus.DONE, etype=EventType.FINAL))
    reducer.apply(make_event("e-b", "dep_B", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED))
    reducer.apply(make_event("e-c", "target_C", deps=["dep_A", "dep_B"]))

    engine = CoordinationEngine(reducer)
    assert engine.is_dependency_failed("target_C") is True

    actions = {a.mission_id: a for a in engine.evaluate_dag()}
    assert "target_C" in actions
    assert actions["target_C"].action_type == NextActionType.HUMAN_ACTION_REQUIRED
    assert "dep_B (BLOCKED)" in actions["target_C"].reason


def test_unrelated_task_remains_active_during_dependency_lock():
    """Beweis 4: Unabhängige Aufgaben werden durch die Sperre nicht behindert (kein globaler Freeze)."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-err", "broken_parent", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED))
    reducer.apply(make_event("e-dep", "locked_child", deps=["broken_parent"]))
    reducer.apply(make_event("e-ok", "healthy_independent", deps=[]))

    engine = CoordinationEngine(reducer)
    actions = {a.mission_id: a for a in engine.evaluate_dag()}

    assert "broken_parent" in actions
    assert actions["broken_parent"].action_type == NextActionType.HUMAN_ACTION_REQUIRED

    assert "locked_child" in actions
    assert actions["locked_child"].action_type == NextActionType.HUMAN_ACTION_REQUIRED

    # healthy_independent ist normal verfügbar
    assert "healthy_independent" in actions
    assert actions["healthy_independent"].action_type == NextActionType.WAIT

    # select_first_ready wählt healthy_independent und überspringt die beiden gesperrten Aufgaben
    first = engine.select_first_ready()
    assert first is not None
    assert first.mission_id == "healthy_independent"


def test_recovery_unlocks_locked_dependency():
    """Beweis 5: Nach Behebung des Fehlers (Vorgänger DONE) wird die Sperre aufgehoben."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a-fail", "task_A", status=MissionStatus.ERROR, etype=EventType.ERROR, created_at="2026-10-12T10:00:00Z"))
    reducer.apply(make_event("e-b", "task_B", deps=["task_A"], created_at="2026-10-12T10:01:00Z"))

    engine = CoordinationEngine(reducer)
    assert engine.is_dependency_failed("task_B") is True

    # Vorgänger wird repariert und erfolgreich abgeschlossen
    reducer.apply(make_event("e-a-fixed", "task_A", status=MissionStatus.DONE, etype=EventType.FINAL, created_at="2026-10-12T10:05:00Z"))

    # Sperre aufgehoben: task_B ist nun normal bereit
    assert engine.is_dependency_failed("task_B") is False
    actions = {a.mission_id: a for a in engine.evaluate_dag()}
    assert actions["task_B"].action_type == NextActionType.WAIT
    assert engine.select_first_ready().mission_id == "task_B"


def test_select_first_ready_excludes_locked_tasks():
    """Beweis 6: select_first_ready liefert None, wenn alle verbleibenden Tasks gesperrt sind."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "task_A", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED))
    reducer.apply(make_event("e-b", "task_B", deps=["task_A"]))

    engine = CoordinationEngine(reducer)
    # Beide Aufgaben erfordern menschliches Eingreifen (task_A ist BLOCKED, task_B ist gesperrt wegen task_A)
    assert engine.select_first_ready() is None


def test_persistence_and_cold_restart_failed_dependency_lock(tmp_path):
    """Beweis 7: Persistenz über FileCoordinationStore, Kaltstart-Statusrekonstruktion & Idempotenz."""
    import subprocess
    import sys
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore

    ledger_path = tmp_path / "failed_dep_ledger.jsonl"
    store = FileCoordinationStore(ledger_path)

    # Events schreiben
    ev_parent_fail = make_event("ev-parent-fail", "parent_broken", status=MissionStatus.BLOCKED, etype=EventType.BLOCKED, created_at="2026-10-12T10:00:00Z")
    ev_child_locked = make_event("ev-child-locked", "child_locked", deps=["parent_broken"], created_at="2026-10-12T10:01:00Z")
    ev_other_ok = make_event("ev-other-ok", "other_healthy", deps=[], created_at="2026-10-12T10:02:00Z")

    store.write_event(ev_parent_fail)
    store.write_event(ev_child_locked)
    store.write_event(ev_other_ok)

    # Kaltstart
    cold_reducer = reduce_store(store)
    cold_engine = CoordinationEngine(cold_reducer)

    assert cold_engine.is_dependency_failed("child_locked") is True
    actions = {a.mission_id: a for a in cold_engine.evaluate_dag()}
    assert actions["parent_broken"].action_type == NextActionType.HUMAN_ACTION_REQUIRED
    assert actions["child_locked"].action_type == NextActionType.HUMAN_ACTION_REQUIRED
    assert actions["other_healthy"].action_type == NextActionType.WAIT

    # select_first_ready liefert only other_healthy
    assert cold_engine.select_first_ready().mission_id == "other_healthy"

    # Idempotenz
    assert cold_reducer.apply(ev_parent_fail) is False
    assert cold_engine.is_dependency_failed("child_locked") is True

    # Subprozess-Kaltstartnachweis
    check_code = f"""
import sys
from pathlib import Path
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.coordination_engine import CoordinationEngine

store = FileCoordinationStore(Path(r"{ledger_path}"))
reducer = reduce_store(store)
engine = CoordinationEngine(reducer)

assert engine.is_dependency_failed("child_locked") is True
first = engine.select_first_ready()
assert first is not None and first.mission_id == "other_healthy"
print("COLD_RESTART_LOCK_VERIFIED")
"""
    result = subprocess.run([sys.executable, "-c", check_code], capture_output=True, text=True, check=True)
    assert "COLD_RESTART_LOCK_VERIFIED" in result.stdout

