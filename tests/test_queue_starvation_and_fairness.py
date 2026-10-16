"""Deterministic tests for Queue Starvation and Fairness.

Mission: Eine dauerhaft blockierte Aufgabe darf nicht die gesamte Courier-Queue anhalten.

Testumgebung mit 5 Aufgaben:
1. Task 1: Blockiert durch fehlenden Provider (PROVIDER_UNAVAILABLE).
2. Task 2: Lokale Routineaufgabe 1 (bereit, ausführbar durch lokalen Worker).
3. Task 3: Lokale Routineaufgabe 2 (bereit, ausführbar durch lokalen Worker).
4. Task 4: Vom Menschen abhängige Aufgabe (HUMAN_REQUIRED / BLOCKED).
5. Task 5: Spätere abhängige Aufgabe (hängt von Task 4 ab).

Beweise:
- Berechtigte lokale Arbeiten (Task 2 und Task 3) werden ohne Starvation nacheinander ausgewählt.
- PROVIDER_UNAVAILABLE und HUMAN_REQUIRED bleiben korrekt sichtbar und werden nicht stillschweigend übergangen.
- Es gibt keine permanente Blockade und keinen Busy-Loop.
- Stopgrund ist eindeutig dokumentiert.
"""

import json
from pathlib import Path
import pytest

from server import app as server_app
from scripts.coordination_delivery import AgentID, NextActionType
from scripts.coordination_engine import CoordinationEngine
from scripts.coordination_ledger import (
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import discover_resumable, reduce_store
from scripts.github_coordination import FileCoordinationStore


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


def test_server_selector_starvation_and_fairness(tmp_path, monkeypatch):
    """Prüft, dass der Server-Claim-Selector lokale Arbeiten auswählt und nicht blockiert."""
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    http = server_app.app.test_client()

    # Lokalen Windows-Worker registrieren
    reg = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WINDOWS-LOCAL", "capabilities": ["windows"]},
    )
    assert reg.status_code == 200

    # 1. Task 1: Blockiert durch fehlenden Provider (z.B. cloud_llm, kein Worker vorhanden)
    http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "cloud llm task with no provider",
            "workflow_plan": [
                {
                    "task_id": "task-cloud-1",
                    "target_agent": "cloud_llm",
                    "instruction": "call unavailable provider",
                    "artifacts": ["cloud.out"],
                    "status_note": "PROVIDER_UNAVAILABLE",
                }
            ],
        },
    )

    # 2. Task 2: Lokale Routineaufgabe 1
    http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "local routine task 1",
            "workflow_plan": [
                {
                    "task_id": "task-routine-1",
                    "target_agent": "windows",
                    "instruction": "compile local cache",
                    "artifacts": ["cache.bin"],
                }
            ],
        },
    )

    # 3. Task 3: Lokale Routineaufgabe 2
    http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "local routine task 2",
            "workflow_plan": [
                {
                    "task_id": "task-routine-2",
                    "target_agent": "windows",
                    "instruction": "lint project",
                    "artifacts": ["lint.txt"],
                }
            ],
        },
    )

    # 4. Task 4: Vom Menschen abhängige Aufgabe (HUMAN_REQUIRED)
    http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "human gate task",
            "workflow_plan": [
                {
                    "task_id": "task-human-1",
                    "target_agent": "windows",
                    "instruction": "financial approval",
                    "artifacts": ["approval.sig"],
                }
            ],
        },
    )
    # Manuell auf HUMAN_REQUIRED / BLOCKED setzen (wie nach Quarantäne oder Gate)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    for g in state["goals"].values():
        if "human gate" in g["goal_text"]:
            g["status"] = "BLOCKED"
            g["workflow_plan"][0]["status"] = "HUMAN_REQUIRED"
    server_app.save_state(state)

    # 5. Task 5: Spätere abhängige Aufgabe (hängt von Task 4 ab)
    http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "dependent downstream task",
            "workflow_plan": [
                {
                    "task_id": "task-downstream-1",
                    "target_agent": "windows",
                    "instruction": "execute post-approval payout",
                    "artifacts": ["payout.receipt"],
                    "depends_on": ["task-human-1"],
                }
            ],
        },
    )
    # Als noch nicht freigeschaltet markieren
    state = json.loads(state_file.read_text(encoding="utf-8"))
    for g in state["goals"].values():
        if "downstream" in g["goal_text"]:
            g["status"] = "BLOCKED"  # Wegen ungelöster Abhängigkeit
    server_app.save_state(state)

    # --- SELEKTIONSTEST DURCH LOKALEN WORKER ---
    selection_order = []
    max_iterations = 10
    iterations = 0
    stop_reason = None

    while iterations < max_iterations:
        iterations += 1
        claim_res = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WINDOWS-LOCAL"})
        task = claim_res.get_json().get("task")
        if task is None:
            stop_reason = "NO_ELIGIBLE_TASK_FOR_WORKER"
            break

        task_id = task["task_id"]
        selection_order.append(task_id)

        # Worker simuliert saubere Ausführung und reicht Ergebnis ein
        result_payload = {
            "goal_id": task["goal_id"],
            "task_id": task_id,
            "attempt_id": task["attempt_id"],
            "dispatch_id": task["dispatch_id"],
            "worker_id": "WINDOWS-LOCAL",
            "run_id": f"pid-routine-{iterations}",
            "result_id": f"result-{task_id}",
            "status": "SUCCESS",
            "artifacts": [{"path": task["artifacts"][0], "sha256": "e" * 64}],
        }
        res_post = http.post("/tasks/result", headers=auth(), json=result_payload)
        assert res_post.status_code == 200

        # Verifier reconciliert
        ver_post = http.post(
            "/tasks/verify",
            headers=verifier_auth(),
            json={
                "task_id": task_id,
                "result_id": f"result-{task_id}",
                "verifier_id": "VERIFIER-01",
                "verdict": "PASS",
                "artifacts": result_payload["artifacts"],
            },
        )
        assert ver_post.status_code == 200

    # BEWEISE:
    # 1. Auswahlreihenfolge: Berechtigte lokale Arbeiten wurden ohne Starvation abgearbeitet!
    assert selection_order == ["task-routine-1", "task-routine-2"], (
        f"Erwartete Auswahlreihenfolge ['task-routine-1', 'task-routine-2'], erhalten: {selection_order}"
    )

    # 2. Stopgrund & Keine Busy-Loop:
    assert stop_reason == "NO_ELIGIBLE_TASK_FOR_WORKER"
    assert iterations == 3  # Genau 2 erfolgreiche Claims + 1 Abschluss-Prüfung

    # 3. Blockierte Aufgaben bleiben korrekt sichtbar und unverändert im Zustand:
    final_state = json.loads(state_file.read_text(encoding="utf-8"))
    cloud_task = next(
        t for g in final_state["goals"].values() for t in g.get("workflow_plan", []) if t["task_id"] == "task-cloud-1"
    )
    human_task = next(
        t for g in final_state["goals"].values() for t in g.get("workflow_plan", []) if t["task_id"] == "task-human-1"
    )
    downstream_task = next(
        t for g in final_state["goals"].values() for t in g.get("workflow_plan", []) if t["task_id"] == "task-downstream-1"
    )

    assert cloud_task["status"] == "QUEUED"  # Wartet weiterhin auf passenden Provider
    assert human_task["status"] == "HUMAN_REQUIRED"  # Wartet weiterhin auf Freigabe
    assert downstream_task["status"] == "QUEUED"  # Wartet auf Downstream-Freigabe


def test_coordination_dag_selector_fairness(tmp_path):
    """Prüft DAG-Selector-Fairness im Coordination Ledger."""
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)
    source_sha = "fac447f5c9c22936177069566b82c7319bc35f5c"

    # 1. Task 1: Provider unavailable (BLOCKED)
    store.write_event(
        CoordinationEvent(
            event_id="e-p1",
            mission_id="TASK_PROVIDER_UNAVAILABLE",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.BLOCKED,
            status=MissionStatus.BLOCKED,
            depends_on=[],
            head=source_sha,
            evidence_ref="circuit_open",
            created_at="2026-10-11T12:00:00Z",
            payload_hash="h1",
            blocker="PROVIDER_UNAVAILABLE",
        )
    )

    # 2. Task 2: Lokale Routineaufgabe 1 (WORKING)
    store.write_event(
        CoordinationEvent(
            event_id="e-r1",
            mission_id="TASK_ROUTINE_1",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head=source_sha,
            evidence_ref="spec-r1",
            created_at="2026-10-11T12:00:01Z",
            payload_hash="h2",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        )
    )

    # 3. Task 3: Lokale Routineaufgabe 2 (WORKING)
    store.write_event(
        CoordinationEvent(
            event_id="e-r2",
            mission_id="TASK_ROUTINE_2",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head=source_sha,
            evidence_ref="spec-r2",
            created_at="2026-10-11T12:00:02Z",
            payload_hash="h3",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        )
    )

    # 4. Task 4: Vom Menschen abhängige Aufgabe (BLOCKED)
    store.write_event(
        CoordinationEvent(
            event_id="e-h1",
            mission_id="TASK_HUMAN_REQUIRED",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.BLOCKED,
            status=MissionStatus.BLOCKED,
            depends_on=[],
            head=source_sha,
            evidence_ref="manual_signoff",
            created_at="2026-10-11T12:00:03Z",
            payload_hash="h4",
            blocker="HUMAN_REQUIRED",
        )
    )

    # 5. Task 5: Spätere abhängige Aufgabe (hängt von TASK_HUMAN_REQUIRED ab)
    store.write_event(
        CoordinationEvent(
            event_id="e-d1",
            mission_id="TASK_DOWNSTREAM",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=["TASK_HUMAN_REQUIRED"],
            head=source_sha,
            evidence_ref="spec-d1",
            created_at="2026-10-11T12:00:04Z",
            payload_hash="h5",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        )
    )

    reducer = reduce_store(store)
    engine = CoordinationEngine(reducer)

    # 1. Resumable Discovery für lokalen Worker GOOGLE_WINDOWS:
    resumable = discover_resumable(reducer, AgentID.GOOGLE_WINDOWS)
    resumable_ids = [c.mission_id for c in resumable]

    # BEWEIS: Genau die beiden Routineaufgaben werden angeboten!
    assert resumable_ids == ["TASK_ROUTINE_1", "TASK_ROUTINE_2"]
    assert "TASK_PROVIDER_UNAVAILABLE" not in resumable_ids
    assert "TASK_HUMAN_REQUIRED" not in resumable_ids
    assert "TASK_DOWNSTREAM" not in resumable_ids

    # 2. Globale DAG-Evaluation:
    actions = engine.evaluate_dag()
    action_types = {a.mission_id: a.action_type for a in actions if a.mission_id}
    reasons = {a.mission_id: a.reason for a in actions if a.mission_id}

    # Routineaufgaben sind in Ausführung / bereit:
    assert action_types["TASK_ROUTINE_1"] == NextActionType.WAIT
    assert action_types["TASK_ROUTINE_2"] == NextActionType.WAIT

    # Blockierte Aufgaben melden präzise HUMAN_ACTION_REQUIRED:
    assert action_types["TASK_PROVIDER_UNAVAILABLE"] == NextActionType.HUMAN_ACTION_REQUIRED
    assert "PROVIDER_UNAVAILABLE" in reasons["TASK_PROVIDER_UNAVAILABLE"]

    assert action_types["TASK_HUMAN_REQUIRED"] == NextActionType.HUMAN_ACTION_REQUIRED
    assert "HUMAN_REQUIRED" in reasons["TASK_HUMAN_REQUIRED"]

    # TASK_DOWNSTREAM darf keinesfalls in den Aktionen auftauchen:
    assert "TASK_DOWNSTREAM" not in action_types
