"""Deterministic tests for SEED 076 — ERSTES READY DETERMINISTISCH WÄHLEN.

Verifies:
1. Deterministic Selection Across Inverted Event Arrival Orders:
   - When multiple missions are concurrently READY, evaluate_dag() and select_first_ready()
     yield the exact same canonical order regardless of arrival/insertion order.
2. Chronological FIFO Prioritization:
   - An earlier-created mission is prioritized over a later-created mission.
3. Lexical Tie-Breaking on Identical Timestamps:
   - When created_at timestamps are identical, deterministic tie-breaking follows lexical mission_id.
4. Dependency-Safe Progression:
   - A dependent mission never becomes first-ready before all its dependencies are DONE.
5. Agent-Targeted First-Ready Filtering:
   - select_first_ready(agent_id) filters safely for the calling agent without skipping shared constraints.
6. Terminal / Cycle Safety:
   - Empty DAG, fully-completed DAG (TRUE_IDLE), or circular DAG (DAG_CYCLE_DETECTED) safely return None.
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
    created_at: str,
    deps: list[str] = None,
    status: MissionStatus = MissionStatus.WORKING,
    etype: EventType = EventType.ASSIGNED,
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
        evidence_ref="evidence-seed076",
        created_at=created_at,
        payload_hash=f"hash-{eid}",
        ownership=agent_id.value,
    )


def test_first_ready_deterministic_across_arrival_permutations():
    """Beweis 1: Unabhängig von der Eintreffreihenfolge wird stets dieselbe Aufgabe als Erstes gewählt."""
    # Reducer 1: Zuerst mission_beta, dann mission_alpha
    r1 = CoordinationReducer()
    r1.apply(make_event("e1", "mission_beta", "2026-10-12T10:00:00Z"))
    r1.apply(make_event("e2", "mission_alpha", "2026-10-12T10:00:00Z"))
    eng1 = CoordinationEngine(r1)

    # Reducer 2: Zuerst mission_alpha, dann mission_beta
    r2 = CoordinationReducer()
    r2.apply(make_event("e2", "mission_alpha", "2026-10-12T10:00:00Z"))
    r2.apply(make_event("e1", "mission_beta", "2026-10-12T10:00:00Z"))
    eng2 = CoordinationEngine(r2)

    # Beide Engines müssen exakt dieselbe Reihenfolge und dieselbe First-Ready-Aufgabe liefern
    order1 = [a.mission_id for a in eng1.evaluate_dag()]
    order2 = [a.mission_id for a in eng2.evaluate_dag()]
    assert order1 == ["mission_alpha", "mission_beta"]
    assert order2 == ["mission_alpha", "mission_beta"]
    assert order1 == order2

    first1 = eng1.select_first_ready()
    first2 = eng2.select_first_ready()
    assert first1 is not None and first2 is not None
    assert first1.mission_id == "mission_alpha"
    assert first2.mission_id == "mission_alpha"


def test_first_ready_fifo_timestamp_prioritization():
    """Beweis 2: Eine früher erstellte Aufgabe (FIFO) hat Vorrang vor später erstellten Aufgaben."""
    reducer = CoordinationReducer()
    # Late Task wird zuerst eingereicht
    reducer.apply(make_event("e-late", "task_late", "2026-10-12T10:05:00Z"))
    # Early Task wird danach eingereicht, hat aber älteren Zeitstempel
    reducer.apply(make_event("e-early", "task_early", "2026-10-12T10:01:00Z"))

    engine = CoordinationEngine(reducer)
    first = engine.select_first_ready()
    assert first is not None
    assert first.mission_id == "task_early"

    all_actions = [a.mission_id for a in engine.evaluate_dag()]
    assert all_actions == ["task_early", "task_late"]


def test_first_ready_respects_dependencies():
    """Beweis 3: Abhängige Aufgaben werden erst nach Abschluss der Vorgänger first-ready."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-dep", "task_downstream", "2026-10-12T10:00:00Z", deps=["task_upstream"]))
    reducer.apply(make_event("e-indep", "task_independent", "2026-10-12T10:02:00Z"))
    reducer.apply(make_event("e-up", "task_upstream", "2026-10-12T10:01:00Z"))

    engine = CoordinationEngine(reducer)
    # Zu Beginn: task_upstream (10:01) und task_independent (10:02) sind bereit; task_downstream blockiert
    first = engine.select_first_ready()
    assert first is not None
    assert first.mission_id == "task_upstream"

    # task_upstream abschließen
    reducer.apply(make_event("e-up-done", "task_upstream", "2026-10-12T10:10:00Z", status=MissionStatus.DONE, etype=EventType.FINAL))

    # Jetzt ist task_downstream (10:00) entblockt und älter als task_independent (10:02)
    first_after = engine.select_first_ready()
    assert first_after is not None
    assert first_after.mission_id == "task_downstream"


def test_first_ready_targeted_agent_filtering():
    """Beweis 4: select_first_ready(agent_id) filtert deterministisch für den zuständigen Agenten."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-win", "win_task", "2026-10-12T10:00:00Z", agent_id=AgentID.GOOGLE_WINDOWS))
    reducer.apply(make_event("e-mac", "mac_task", "2026-10-12T09:59:00Z", agent_id=AgentID.GOOGLE_MAC))

    engine = CoordinationEngine(reducer)

    # Ohne Filter: mac_task ist älter (09:59)
    assert engine.select_first_ready().mission_id == "mac_task"

    # Mit Filter auf GOOGLE_WINDOWS: win_task wird selektiert
    win_ready = engine.select_first_ready(agent_id=AgentID.GOOGLE_WINDOWS)
    assert win_ready is not None
    assert win_ready.mission_id == "win_task"

    # Filter auf unbeteiligten Agenten: None
    assert engine.select_first_ready(agent_id=AgentID.CODEX_MAC) is None


def test_first_ready_returns_none_on_idle_or_cycle():
    """Beweis 5: Bei leerem DAG, vollständigem Abschluss (TRUE_IDLE) oder Zyklus gibt select_first_ready None zurück."""
    # Leerer Reducer
    r_empty = CoordinationReducer()
    assert CoordinationEngine(r_empty).select_first_ready() is None

    # Alle Aufgaben DONE -> TRUE_IDLE
    r_done = CoordinationReducer()
    r_done.apply(make_event("e1", "t1", "2026-10-12T10:00:00Z", status=MissionStatus.DONE, etype=EventType.FINAL))
    r_done.apply(make_event("e2", "t2", "2026-10-12T10:01:00Z", status=MissionStatus.DONE, etype=EventType.FINAL))
    eng_done = CoordinationEngine(r_done)
    actions = eng_done.evaluate_dag()
    assert len(actions) == 1
    assert actions[0].action_type == NextActionType.TRUE_IDLE
    assert eng_done.select_first_ready() is None

    # Zyklischer DAG (t1 -> t2 -> t1)
    r_cycle = CoordinationReducer()
    r_cycle.apply(make_event("c1", "c_one", "2026-10-12T10:00:00Z", deps=["c_two"]))
    r_cycle.apply(make_event("c2", "c_two", "2026-10-12T10:00:00Z", deps=["c_one"]))
    eng_cycle = CoordinationEngine(r_cycle)
    cycle_actions = eng_cycle.evaluate_dag()
    assert any(a.action_type == NextActionType.DAG_CYCLE_DETECTED for a in cycle_actions)
    assert eng_cycle.select_first_ready() is None


def test_missing_or_failed_dependency_fails_closed():
    """Beweis 6: Fehlende oder nicht-abgeschlossene Abhängigkeiten blockieren deterministisch (Fail-closed)."""
    reducer = CoordinationReducer()
    # Task hängt von einer gänzlich unbekannten mission_ghost ab
    reducer.apply(make_event("e-ghost-dep", "task_stranded", "2026-10-12T10:00:00Z", deps=["mission_ghost"]))
    engine = CoordinationEngine(reducer)
    assert engine.select_first_ready() is None
    assert engine.evaluate_dag() == []

    # Task hängt von einer Aufgabe ab, die im ERROR-Zustand endete (nicht DONE)
    reducer.apply(make_event("e-err", "task_errored", "2026-10-12T09:50:00Z", status=MissionStatus.ERROR, etype=EventType.ERROR))
    reducer.apply(make_event("e-blocked", "task_waiting_on_error", "2026-10-12T10:05:00Z", deps=["task_errored"]))
    # task_waiting_on_error darf NICHT ausgewählt werden; task_errored erfordert CANCEL_REQUIRED
    first = engine.select_first_ready()
    assert first is not None
    assert first.mission_id == "task_errored"
    assert first.action_type == NextActionType.CANCEL_REQUIRED


def test_missing_or_none_timestamps_safe_fallback():
    """Beweis 7: Robuster Fallback bei fehlenden/None Timestamps ohne Absturz."""
    reducer = CoordinationReducer()
    # Mission ohne Timestamp (z.B. Legacy-Event oder korrumpierte Daten)
    ev_no_ts = make_event("e-null", "task_null_ts", "2026-10-12T10:00:00Z")
    reducer.apply(ev_no_ts)
    reducer.missions["task_null_ts"]["created_at"] = None

    ev_normal = make_event("e-normal", "task_normal", "2026-10-12T10:01:00Z")
    reducer.apply(ev_normal)

    engine = CoordinationEngine(reducer)
    # Sortierung bricht nicht ab: "" < "2026-10-12..." -> task_null_ts wird stabil behandelt
    actions = [a.mission_id for a in engine.evaluate_dag()]
    assert len(actions) == 2
    assert engine.select_first_ready() is not None


def test_alien_agent_cannot_intercept_targeted_mission():
    """Beweis 8: Fremde Agenten-Autoritäten können keine zielgerichteten Tasks unautorisiert beanspruchen."""
    reducer = CoordinationReducer()
    reducer.apply(make_event("e-win-only", "mission_for_windows", "2026-10-12T10:00:00Z", agent_id=AgentID.GOOGLE_WINDOWS))
    engine = CoordinationEngine(reducer)

    # Autorisierter Windows-Agent erhält die Aufgabe
    assert engine.select_first_ready(agent_id=AgentID.GOOGLE_WINDOWS).mission_id == "mission_for_windows"

    # Nicht-autorisierter Mac-Agent erhält Fail-Closed None
    assert engine.select_first_ready(agent_id=AgentID.GOOGLE_MAC) is None
    assert engine.select_first_ready(agent_id=AgentID.MUSE_MAC) is None
    assert engine.select_first_ready(agent_id=AgentID.UNKNOWN) is None

