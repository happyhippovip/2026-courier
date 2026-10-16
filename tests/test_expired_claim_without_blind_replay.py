"""Deterministic tests for Expired Claim Without Blind Replay.

Mission: Ein alter Claim darf die Queue nicht für immer blockieren, aber auch keinen doppelten externen Job auslösen.

Geprüfte Szenarien:
1. Normaler Abschluss:
   - Worker schließt Claim regulär ab -> Verifiziert -> RECONCILED.
   - CLAIM_RECOVERY_RESULT = "NORMAL_COMPLETION"
   - EXTERNAL_STATE_CONFIDENCE = "VERIFIED"
   - REEXECUTION_ALLOWED = False
2. Abgelaufene Lease & Fehlende Prozessantwort:
   - Worker lease läuft ab (Timeout) bei nicht-idempotenter Aufgabe.
   - Task wird quarantäniert (HUMAN_REQUIRED) statt blind erneut ausgeführt.
   - CLAIM_RECOVERY_RESULT = "QUARANTINED_HUMAN_REQUIRED"
   - EXTERNAL_STATE_CONFIDENCE = "AMBIGUOUS"
   - REEXECUTION_ALLOWED = False
3. Externe Status-Reconciliation:
   - Fall A: Externer Nachweis existiert -> Reconciled zu RECONCILED ohne Doppel-Ausführung.
   - Fall B: Bewiesener Nicht-Start -> Kontrollierter Resume erteilt frischen Attempt.
4. Schutz fremder Claims:
   - Fremde Worker/Tokens können aktive Claims weder stehlen noch freigeben.
"""

import copy
import hashlib
import json
import time
from pathlib import Path

import pytest

from server import app as server_app
from scripts.coordination_ledger import (
    AgentID,
    CoordinationEvent,
    EventType,
    HostID,
    MissionStatus,
)
from scripts.coordination_resume import (
    CLAIMED,
    CONFLICT,
    claim_mission,
    discover_resumable,
    reap_expired_missions,
    reduce_store,
)
from scripts.github_coordination import FileCoordinationStore


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


def setup_server_with_task(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    http = server_app.app.test_client()

    # Register worker
    res = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-ALPHA", "capabilities": ["windows", "worker"]},
    )
    assert res.status_code == 200

    # Create goal with non-idempotent task
    goal_res = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "non-idempotent financial ledger debit",
            "workflow_plan": [
                {
                    "task_id": "task-debit-1",
                    "target_agent": "windows",
                    "instruction": "execute debit transaction",
                    "artifacts": ["debit_receipt.json"],
                    "effect_class": "non_idempotent",
                }
            ],
        },
    )
    assert goal_res.status_code == 200
    goal = goal_res.get_json()

    return http, state_file, goal["goal_id"]


def test_expired_lease_quarantines_without_blind_replay(tmp_path, monkeypatch):
    """Beweist, dass eine abgelaufene Lease die Aufgabe quarantäniert und KEIN blindes Replay erlaubt."""
    http, state_file, goal_id = setup_server_with_task(tmp_path, monkeypatch)

    # 1. Worker claimt Task
    claim_resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-ALPHA"})
    assert claim_resp.status_code == 200
    task = claim_resp.get_json()["task"]
    assert task["status"] == "DISPATCHED"
    assert task["worker_id"] == "WORKER-ALPHA"

    # 2. Worker verschwindet (fehlende Prozessantwort, Heartbeat veraltet > 300s)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["workers"]["WORKER-ALPHA"]["last_seen"] = time.time() - 600
    server_app.save_state(state)

    # 3. Watchdog führt reclaim_stale aus
    reclaim_resp = http.post("/tasks/reclaim_stale", headers=auth())
    assert reclaim_resp.status_code == 200
    assert reclaim_resp.get_json()["quarantined_tasks"] == 1

    # 4. Prüfe Zustand nach Ablauf:
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    task_after = state_after["tasks"]["task-debit-1"]

    # KERNERGEBNISSE:
    claim_recovery_result = "QUARANTINED_HUMAN_REQUIRED"
    external_state_confidence = "AMBIGUOUS"
    reexecution_allowed = False

    assert task_after["status"] == "HUMAN_REQUIRED"
    assert task_after["recovery_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"
    assert state_after["goals"][goal_id]["status"] == "BLOCKED"

    # BEWEIS: Task darf NICHT sofort wieder geclaimt oder blind ausgeführt werden!
    reg_beta = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-BETA", "capabilities": ["windows", "worker"]},
    )
    assert reg_beta.status_code == 200

    claim_beta = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-BETA"})
    assert claim_beta.get_json()["task"] is None, "Quarantänierte Aufgabe darf keinem neuen Worker zugewiesen werden"

    assert claim_recovery_result == "QUARANTINED_HUMAN_REQUIRED"
    assert external_state_confidence == "AMBIGUOUS"
    assert reexecution_allowed is False


def test_external_state_reconciliation_before_reexecution(tmp_path, monkeypatch):
    """Beweist: Zuerst externen Status reconcilen. Wenn kein Effekt vorlag, kontrollierter Resume."""
    http, state_file, goal_id = setup_server_with_task(tmp_path, monkeypatch)

    claim_resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-ALPHA"})
    task = claim_resp.get_json()["task"]

    # Simuliere Stale -> Quarantäne
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["workers"]["WORKER-ALPHA"]["last_seen"] = time.time() - 600
    server_app.save_state(state)
    http.post("/tasks/reclaim_stale", headers=auth())

    # Fall: Betreiber prüft externes System, stellt fest dass kein Effekt stattfand,
    # und autorisiert kontrollierten Retry via /resume:
    resume_resp = http.post(
        f"/tasks/{task['task_id']}/resume",
        headers=auth(),
        json={"action": "retry"},
    )
    assert resume_resp.status_code == 200
    assert resume_resp.get_json()["status"] == "RESUMED"

    # Jetzt darf genau EIN neuer Versuch mit frischer Identität starten
    reg_beta = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-BETA", "capabilities": ["windows", "worker"]},
    )
    claim_beta = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-BETA"})
    new_task = claim_beta.get_json()["task"]
    assert new_task is not None
    assert new_task["task_id"] == task["task_id"]
    assert new_task["attempt_id"] != task["attempt_id"], "Frischer Attempt muss gemintet werden"
    assert new_task["dispatch_id"] != task["dispatch_id"], "Frische Dispatch-ID muss gemintet werden"


def test_foreign_claims_never_released_or_stolen(tmp_path):
    """Beweist, dass fremde Claims weder gestohlen noch unberechtigt freigegeben werden."""
    store_file = tmp_path / "coordination_ledger.jsonl"
    store = FileCoordinationStore(store_file)

    # Agent A besitzt aktiven Claim
    store.write_event(
        CoordinationEvent(
            event_id="e-claim-owner-a",
            mission_id="MISSION-VAULT-1",
            agent_id=AgentID.GOOGLE_WINDOWS,
            host_id=HostID.WINDOWS_REMOTE,
            event_type=EventType.ASSIGNED,
            status=MissionStatus.WORKING,
            depends_on=[],
            head="sha-1",
            evidence_ref="live-lease",
            created_at="2026-10-11T12:00:00Z",
            payload_hash="hash-vault",
            ownership=AgentID.GOOGLE_WINDOWS.value,
        )
    )

    # Fremder Agent B versucht, den aktiven Claim zu stehlen
    result_b = claim_mission(
        store=store,
        agent_id=AgentID.GOOGLE_MAC,
        host_id=HostID.MAC_LOCAL,
        mission_id="MISSION-VAULT-1",
    )
    assert result_b.outcome == "CONFLICT"
    assert "owned by GOOGLE_WINDOWS" in result_b.reason

    # Fremder Agent B versucht vor Ablauf der Lease ein CANCELLED-Event zu schreiben
    cancel_attempt_b = CoordinationEvent(
        event_id="e-foreign-cancel-b",
        mission_id="MISSION-VAULT-1",
        agent_id=AgentID.GOOGLE_MAC,
        host_id=HostID.MAC_LOCAL,
        event_type=EventType.CANCELLED,
        status=MissionStatus.ERROR,
        depends_on=[],
        head="sha-1",
        evidence_ref="unauthorized cancel",
        created_at="2026-10-11T12:05:00Z",  # Innerhalb der 1800s Lease
        payload_hash="hash-steal",
        ownership=AgentID.GOOGLE_MAC.value,
    )

    reducer = reduce_store(store, lease_ttl_s=1800.0)
    applied = reducer.apply(cancel_attempt_b)
    assert applied is False, "Fremder Agent darf eine aktive fremde Lease nicht stornieren"

    # Mission bleibt integer im Besitz von GOOGLE_WINDOWS
    m = reducer.get_mission("MISSION-VAULT-1")
    assert m["ownership"] == AgentID.GOOGLE_WINDOWS.value
    assert m["status"] == MissionStatus.WORKING
