"""Deterministic tests for SEED 077 — DAG-ABHÄNGIGKEIT AUFLÖSEN.

Verifies:
1. Single Dependency Resolution:
   - A -> B: B's dependencies resolve only when A reaches terminal DONE.
   - B receives A's resolved evidence_ref for downstream consumption.
2. Fan-In / Multi-Dependency Resolution:
   - A and B -> C: C remains unresolved until BOTH A and B are DONE.
   - C aggregates evidence from all completed dependencies.
3. Upstream Failure Blockage (Fail-Closed):
   - If an upstream dependency fails (ERROR or BLOCKED), downstream task
     evaluates to HUMAN_ACTION_REQUIRED rather than entering an unready loop.
4. Unknown / Ghost Dependency Handling:
   - Tasks depending on unannounced missions fail closed with status UNKNOWN.
5. Independent / Zero-Dependency Tasks:
   - Tasks with empty depends_on resolve immediately to resolved=True.
6. Non-Existent Task Query:
   - Querying an unknown mission_id safely returns resolved=False with NOT_FOUND.
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
    evidence_ref: str = "spec-data",
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


def test_single_dependency_resolution_lifecycle():
    """Beweis 1: Einzelne DAG-Abhängigkeit (A -> B) auflösen und Evidence übergeben."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "task_A", evidence_ref="evidence-A-initial"))
    reducer.apply(make_event("e-b", "task_B", deps=["task_A"], evidence_ref="spec-B"))

    engine = CoordinationEngine(reducer)

    # Schritt 1: task_A läuft (WORKING) -> task_B Abhängigkeit NICHT aufgelöst
    res1 = engine.resolve_dependencies("task_B")
    assert res1["resolved"] is False
    assert res1["dependencies"] == ["task_A"]
    assert len(res1["unresolved"]) == 1
    assert res1["unresolved"][0]["mission_id"] == "task_A"
    assert res1["unresolved"][0]["status"] == "WORKING"
    assert res1["resolved_evidence"] == {}

    action_b = engine.evaluate_next_action("task_B")
    assert action_b.action_type == NextActionType.WAIT
    assert "waiting for upstream dependencies" in action_b.reason

    # Schritt 2: task_A schließt erfolgreich ab (DONE) mit Evidence-Receipt
    reducer.apply(make_event("e-a-done", "task_A", status=MissionStatus.DONE, etype=EventType.FINAL, evidence_ref="rcpt-A-pass;hash=123"))

    # Schritt 3: task_B Abhängigkeit ist nun VOLLSTÄNDIG aufgelöst
    res2 = engine.resolve_dependencies("task_B")
    assert res2["resolved"] is True
    assert res2["unresolved"] == []
    assert res2["resolved_evidence"] == {"task_A": "rcpt-A-pass;hash=123"}

    # In evaluate_dag() ist task_B nun als nächste Aktion freigeschaltet
    actions = [a.mission_id for a in engine.evaluate_dag()]
    assert "task_B" in actions


def test_multi_dependency_fan_in_resolution():
    """Beweis 2: Mehrfachabhängigkeit (Fan-In: A und B -> C) auflösen."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-a", "dep_A", evidence_ref="evidence-A"))
    reducer.apply(make_event("e-b", "dep_B", evidence_ref="evidence-B"))
    reducer.apply(make_event("e-c", "target_C", deps=["dep_A", "dep_B"]))

    engine = CoordinationEngine(reducer)

    # Initial: Weder A noch B sind DONE
    res0 = engine.resolve_dependencies("target_C")
    assert res0["resolved"] is False
    assert len(res0["unresolved"]) == 2

    # Teil 1: dep_A wird DONE
    reducer.apply(make_event("e-a-done", "dep_A", status=MissionStatus.DONE, etype=EventType.FINAL, evidence_ref="rcpt-A-done"))
    res1 = engine.resolve_dependencies("target_C")
    assert res1["resolved"] is False
    assert res1["unresolved"] == [{"mission_id": "dep_B", "status": "WORKING"}]
    assert res1["resolved_evidence"] == {"dep_A": "rcpt-A-done"}

    # Teil 2: dep_B wird DONE -> target_C vollständig aufgelöst
    reducer.apply(make_event("e-b-done", "dep_B", status=MissionStatus.DONE, etype=EventType.FINAL, evidence_ref="rcpt-B-done"))
    res2 = engine.resolve_dependencies("target_C")
    assert res2["resolved"] is True
    assert res2["unresolved"] == []
    assert res2["resolved_evidence"] == {"dep_A": "rcpt-A-done", "dep_B": "rcpt-B-done"}


def test_upstream_failure_propagation():
    """Beweis 3: Fehler in vorgelagerter Aufgabe (ERROR / BLOCKED) blockiert nachgelagerte Aufgabe mit HUMAN_ACTION_REQUIRED."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-err", "upstream_err", status=MissionStatus.ERROR, etype=EventType.ERROR))
    reducer.apply(make_event("e-down", "downstream_task", deps=["upstream_err"]))

    engine = CoordinationEngine(reducer)
    res = engine.resolve_dependencies("downstream_task")
    assert res["resolved"] is False
    assert res["unresolved"][0]["status"] == "ERROR"

    action = engine.evaluate_next_action("downstream_task")
    assert action.action_type == NextActionType.HUMAN_ACTION_REQUIRED
    assert "blocked by failed/blocked dependencies" in action.reason


def test_unknown_or_ghost_dependency():
    """Beweis 4: Unbekannte/fehlende Abhängigkeit führt zu UNKNOWN und blockiert fail-closed."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-ghost", "stranded_task", deps=["phantom_upstream"]))

    engine = CoordinationEngine(reducer)
    res = engine.resolve_dependencies("stranded_task")
    assert res["resolved"] is False
    assert res["unresolved"] == [{"mission_id": "phantom_upstream", "status": "UNKNOWN"}]

    action = engine.evaluate_next_action("stranded_task")
    assert action.action_type == NextActionType.WAIT
    assert "phantom_upstream (UNKNOWN)" in action.reason


def test_independent_and_nonexistent_tasks():
    """Beweis 5 & 6: Unabhängige Tasks sind sofort aufgelöst; unbekannte Task_IDs liefern NOT_FOUND."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-indep", "independent_task", deps=[]))

    engine = CoordinationEngine(reducer)
    res_indep = engine.resolve_dependencies("independent_task")
    assert res_indep["resolved"] is True
    assert res_indep["dependencies"] == []
    assert res_indep["unresolved"] == []

    res_none = engine.resolve_dependencies("non_existent_mission")
    assert res_none["resolved"] is False
    assert res_none["unresolved"] == [{"mission_id": "non_existent_mission", "status": "NOT_FOUND"}]


def test_persistence_and_cold_restart_dag_reconstruction(tmp_path):
    """Beweis 7: Persistenz über FileCoordinationStore, Kaltstart-Rekonstruktion & Idempotenz."""
    import subprocess
    import sys
    from scripts.coordination_resume import reduce_store
    from scripts.github_coordination import FileCoordinationStore

    ledger_path = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(ledger_path)

    # 1. Schreibe DAG-Events in persistenten Store
    ev_a = make_event("ev-a", "task_A", deps=[], status=MissionStatus.WORKING)
    ev_a_done = make_event("ev-a-done", "task_A", deps=[], status=MissionStatus.DONE, etype=EventType.FINAL, evidence_ref="persisted-rcpt-A")
    ev_b = make_event("ev-b", "task_B", deps=["task_A"], status=MissionStatus.WORKING)
    ev_c = make_event("ev-c", "task_C", deps=["task_B"], status=MissionStatus.WORKING)

    store.write_event(ev_a)
    store.write_event(ev_a_done)
    store.write_event(ev_b)
    store.write_event(ev_c)

    # 2. Simuliere Kaltstart: Neuer Reducer liest ausschließlich die persistente Datei
    cold_reducer = reduce_store(store)
    cold_engine = CoordinationEngine(cold_reducer)

    # Prüfe Status-Rekonstruktion
    res_b = cold_engine.resolve_dependencies("task_B")
    assert res_b["resolved"] is True
    assert res_b["resolved_evidence"] == {"task_A": "persisted-rcpt-A"}

    res_c = cold_engine.resolve_dependencies("task_C")
    assert res_c["resolved"] is False
    assert res_c["unresolved"] == [{"mission_id": "task_B", "status": "WORKING"}]

    next_actions = [a.mission_id for a in cold_engine.evaluate_dag()]
    assert next_actions == ["task_B"]

    # 3. Idempotenz-Nachweis: Erneutes Anwenden derselben Events verändert Zustand nicht
    applied_again = cold_reducer.apply(ev_a_done)
    assert applied_again is False  # Duplicate ignored
    assert cold_engine.resolve_dependencies("task_B")["resolved"] is True

    # 4. Physischer Subprozess-Kaltstart (unabhängiger Python-Prozess)
    check_code = f"""
import sys
from pathlib import Path
from scripts.coordination_resume import reduce_store
from scripts.github_coordination import FileCoordinationStore
from scripts.coordination_engine import CoordinationEngine

store = FileCoordinationStore(Path(r"{ledger_path}"))
reducer = reduce_store(store)
engine = CoordinationEngine(reducer)

res_b = engine.resolve_dependencies("task_B")
assert res_b["resolved"] is True, f"B resolved expected True, got {{res_b}}"
assert res_b["resolved_evidence"] == {{"task_A": "persisted-rcpt-A"}}

res_c = engine.resolve_dependencies("task_C")
assert res_c["resolved"] is False, f"C resolved expected False, got {{res_c}}"

actions = [a.mission_id for a in engine.evaluate_dag()]
assert actions == ["task_B"], f"Actions expected ['task_B'], got {{actions}}"
print("SUBPROCESS_RESTART_SUCCESS")
"""
    result = subprocess.run([sys.executable, "-c", check_code], capture_output=True, text=True, check=True)
    assert "SUBPROCESS_RESTART_SUCCESS" in result.stdout

