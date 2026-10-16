"""Deterministic tests for Dependency-Safe Next Ready.

Mission: Folgeaufgaben dürfen nur starten, wenn ihre echten Voraussetzungen erfüllt sind.

Topologie des Test-DAG:
- A und B unabhängig (depends_on: [])
- C hängt von A ab (depends_on: [A])
- D hängt von B und C ab (depends_on: [B, C])

Geprüfte Schritte & READY-Set Transitionen:
1. Initial: READY = {A, B}; C und D blockiert.
2. A wird akzeptiert abgeschlossen: READY = {B, C}; C freigeschaltet, D blockiert (B und C nicht fertig).
3. Fehler bei B (B -> ERROR): READY = {B (REASSIGN), C}; D bleibt strikt blockiert.
4. B wird zulässig behandelt & abgeschlossen (B -> DONE): READY = {C}; D bleibt blockiert (da C noch nicht DONE).
5. C wird abgeschlossen (C -> DONE): READY = {D}; D ist nun vollständig entblockt.
6. D wird abgeschlossen (D -> DONE): READY = {}; Engine meldet TRUE_IDLE.
7. Identischer Replay von A: Idempotent abgewiesen, A wird keinesfalls wieder READY.
8. Verspäteter Resultateingang auf A (Stale Event): Monotonie-Schutz verwirft Event, A bleibt DONE.
"""

from pathlib import Path
import pytest

from scripts.coordination_delivery import AgentID, NextActionType
from scripts.coordination_engine import CoordinationEngine
from scripts.coordination_ledger import (
    CoordinationEvent,
    CoordinationReducer,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore


def compute_ready_set(reducer: CoordinationReducer, agent_id: AgentID = AgentID.GOOGLE_WINDOWS) -> set[str]:
    """Ermittelt alle aktuell ausführbaren Aufgaben (wo alle Dependencies DONE sind und Mission != DONE)."""
    resumable = discover_resumable(reducer, agent_id)
    return {c.mission_id for c in resumable}


def test_dependency_safe_next_ready_dag_lifecycle(tmp_path):
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)

    source_sha = "fac447f5c9c22936177069566b82c7319bc35f5c"

    # --- SCHRITT 0: Initialer DAG-Zustand ---
    # A und B unabhängig; C hängt von A ab; D hängt von B und C ab.
    events = [
        CoordinationEvent(
            event_id="e-assign-a",
            mission_id="A",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head=source_sha,
            evidence_ref="spec-a",
            created_at="2026-10-11T12:00:00Z",
            payload_hash="h-a",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        ),
        CoordinationEvent(
            event_id="e-assign-b",
            mission_id="B",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head=source_sha,
            evidence_ref="spec-b",
            created_at="2026-10-11T12:00:01Z",
            payload_hash="h-b",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        ),
        CoordinationEvent(
            event_id="e-assign-c",
            mission_id="C",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=["A"],
            head=source_sha,
            evidence_ref="spec-c",
            created_at="2026-10-11T12:00:02Z",
            payload_hash="h-c",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        ),
        CoordinationEvent(
            event_id="e-assign-d",
            mission_id="D",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=["B", "C"],
            head=source_sha,
            evidence_ref="spec-d",
            created_at="2026-10-11T12:00:03Z",
            payload_hash="h-d",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        ),
    ]

    for ev in events:
        store.write_event(ev)

    # Prüfe Initialen Zustand
    r0 = reduce_store(store)
    eng0 = CoordinationEngine(r0)
    ready0 = compute_ready_set(r0)
    assert ready0 == {"A", "B"}, f"Schritt 0: READY muss {{A, B}} sein, erhalten: {ready0}"
    actions0 = [a.mission_id for a in eng0.evaluate_dag()]
    assert set(actions0) == {"A", "B"}

    # --- SCHRITT 1: Akzeptierter Abschluss von A ---
    final_a = CoordinationEvent(
        event_id="e-final-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head=source_sha,
        evidence_ref="rcpt-a;verdict=PASS",
        created_at="2026-10-11T12:05:00Z",
        payload_hash="h-final-a",
        ownership=None,
    )
    store.write_event(final_a)

    r1 = reduce_store(store)
    eng1 = CoordinationEngine(r1)
    ready1 = compute_ready_set(r1)

    # BEWEIS 1: C ist freigeschaltet! D bleibt blockiert!
    assert "C" in ready1, "C muss nach Abschluss von A freigeschaltet sein"
    assert "D" not in ready1, "D muss blockiert bleiben, da B und C noch nicht DONE sind"
    assert "A" not in ready1, "A ist abgeschlossen und darf nicht wieder READY sein"
    assert ready1 == {"B", "C"}, f"Schritt 1: READY muss {{B, C}} sein, erhalten: {ready1}"

    actions1 = [a.mission_id for a in eng1.evaluate_dag()]
    assert set(actions1) == {"B", "C"}

    # --- SCHRITT 2: Fehler bei B (B -> ERROR) ---
    error_b = CoordinationEvent(
        event_id="e-error-b",
        mission_id="B",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ERROR,
        status=MissionStatus.ERROR,
        depends_on=[],
        head=source_sha,
        evidence_ref="error: worker timed out",
        created_at="2026-10-11T12:06:00Z",
        payload_hash="h-error-b",
        ownership=AgentID.GOOGLE_WINDOWS.value,
    )
    store.write_event(error_b)

    r2 = reduce_store(store)
    eng2 = CoordinationEngine(r2)
    ready2 = compute_ready_set(r2)

    # BEWEIS 2: B wird als REASSIGN angeboten; C läuft unabhängig weiter; D bleibt blockiert!
    assert "B" in ready2, "B im Zustand ERROR muss für Reassignment angeboten werden"
    checkpoint_b = next(c for c in discover_resumable(r2, AgentID.GOOGLE_WINDOWS) if c.mission_id == "B")
    assert checkpoint_b.mode == "REASSIGN"
    assert "C" in ready2, "C hängt nur von A ab und bleibt unbeeinflusst READY"
    assert "D" not in ready2, "D darf bei fehlerhaftem B keinesfalls starten"
    assert ready2 == {"B", "C"}, f"Schritt 2: READY muss {{B, C}} sein, erhalten: {ready2}"

    # Engine evaluiert B als CANCEL_REQUIRED / Reassign-Bedarf
    b_action = next(a for a in eng2.evaluate_dag() if a.mission_id == "B")
    assert b_action.action_type == NextActionType.CANCEL_REQUIRED

    # --- SCHRITT 3: Zulässige Behandlung von B & Erfolgreicher Abschluss ---
    # Reassign und Abschluss von B
    final_b = CoordinationEvent(
        event_id="e-final-b",
        mission_id="B",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head=source_sha,
        evidence_ref="rcpt-b;verdict=PASS;retry=1",
        created_at="2026-10-11T12:10:00Z",
        payload_hash="h-final-b",
        ownership=None,
    )
    store.write_event(final_b)

    r3 = reduce_store(store)
    ready3 = compute_ready_set(r3)

    # BEWEIS 3: B ist nun DONE. D bleibt weiterhin blockiert, da C noch nicht DONE ist!
    assert "B" not in ready3
    assert "C" in ready3
    assert "D" not in ready3, "D muss blockiert bleiben, bis AUCH C abgeschlossen ist"
    assert ready3 == {"C"}, f"Schritt 3: READY muss {{C}} sein, erhalten: {ready3}"

    # --- SCHRITT 4: Abschluss von C ---
    final_c = CoordinationEvent(
        event_id="e-final-c",
        mission_id="C",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=["A"],
        head=source_sha,
        evidence_ref="rcpt-c;verdict=PASS",
        created_at="2026-10-11T12:15:00Z",
        payload_hash="h-final-c",
        ownership=None,
    )
    store.write_event(final_c)

    r4 = reduce_store(store)
    eng4 = CoordinationEngine(r4)
    ready4 = compute_ready_set(r4)

    # BEWEIS 4: Jetzt sind B und C DONE -> D ist vollständig freigeschaltet!
    assert "A" not in ready4
    assert "B" not in ready4
    assert "C" not in ready4
    assert ready4 == {"D"}, f"Schritt 4: READY muss {{D}} sein, erhalten: {ready4}"
    actions4 = [a.mission_id for a in eng4.evaluate_dag()]
    assert actions4 == ["D"]

    # --- SCHRITT 5: Abschluss von D & TRUE_IDLE ---
    final_d = CoordinationEvent(
        event_id="e-final-d",
        mission_id="D",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=["B", "C"],
        head=source_sha,
        evidence_ref="rcpt-d;verdict=PASS",
        created_at="2026-10-11T12:20:00Z",
        payload_hash="h-final-d",
        ownership=None,
    )
    store.write_event(final_d)

    r5 = reduce_store(store)
    eng5 = CoordinationEngine(r5)
    ready5 = compute_ready_set(r5)
    assert ready5 == set(), f"Schritt 5: Alle Aufgaben sind DONE, READY muss leer sein, erhalten: {ready5}"

    idle_action = eng5.evaluate_dag()
    assert len(idle_action) == 1
    assert idle_action[0].action_type == NextActionType.TRUE_IDLE


def test_replay_and_stale_result_safety(tmp_path):
    """Testet Replay von A und verspäteten Resultateingang."""
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)
    source_sha = "fac447f5c9c22936177069566b82c7319bc35f5c"

    # Task A anlegen und abschließen
    e_assign_a = CoordinationEvent(
        event_id="e-assign-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.ASSIGNED,
        status=MissionStatus.WORKING,
        depends_on=[],
        head=source_sha,
        evidence_ref="spec-a",
        created_at="2026-10-11T12:00:00Z",
        payload_hash="h-a",
    )
    store.write_event(e_assign_a)

    e_final_a = CoordinationEvent(
        event_id="e-final-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.FINAL,
        status=MissionStatus.DONE,
        depends_on=[],
        head=source_sha,
        evidence_ref="rcpt-a;verdict=PASS",
        created_at="2026-10-11T12:05:00Z",
        payload_hash="h-final-a",
    )
    store.write_event(e_final_a)

    reducer = reduce_store(store)
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE

    # 1. Identischer Replay von A (gleiche event_id)
    applied_replay = reducer.apply(e_final_a)
    assert applied_replay is False, "Exakter Replay muss idempotent ignoriert werden"
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE

    # 2. Verspäteter Resultateingang (Stale Event mit Zeitstempel vor FINAL)
    stale_event = CoordinationEvent(
        event_id="e-stale-partial-a",
        mission_id="A",
        agent_id=AgentID.GOOGLE_WINDOWS,
        host_id=HostID.WINDOWS_REMOTE,
        event_type=EventType.PARTIAL,
        status=MissionStatus.WORKING,
        depends_on=[],
        head=source_sha,
        evidence_ref="stale partial data",
        created_at="2026-10-11T12:02:00Z",  # Älter als FINAL (12:05:00Z)
        payload_hash="h-stale-a",
    )
    applied_stale = reducer.apply(stale_event)
    assert applied_stale is False, "Veralteter Resultateingang darf neueren Fortschritt nicht überschreiben"
    assert reducer.get_mission("A")["status"] == MissionStatus.DONE
