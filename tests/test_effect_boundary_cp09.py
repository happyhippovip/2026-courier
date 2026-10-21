"""Comprehensive Contract Tests for CP-09 / CQ-09:
Dauerhafte Queue: Fencing, Epoch Guard, Decoupled Process Abort, and Unknown-Effect Reconciliation.

Acceptance Criteria:
1. Alter Lease-Inhaber kann keinen neuen Effekt autorisieren.
2. Fencing/Epoch und Ergebnisannahme getrennt von Prozessabbruch.
3. Unbekannter externer Effekt bleibt blockiert, bis er aufgeklärt ist (Reconciliation statt blindem Retry).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import pytest

from courier_core.effect_boundary import (
    EffectClass,
    EffectFencingBoundary,
    EffectResolution,
    ExecutionPhase,
    FencingBoundaryError,
    LeaseExpiredError,
    StaleFencingTokenError,
    EffectAuthorizationDenied,
    UnknownEffectQuarantinedError,
)
from server import app as server_app


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


# =========================================================================
# Part 1: Core EffectFencingBoundary Unit Tests
# =========================================================================

def test_stale_lease_holder_cannot_authorize_effect_after_takeover(tmp_path):
    """Beweist: Ein alter Lease-Inhaber (Zombie-Worker) kann keinen neuen Effekt autorisieren,

    nachdem die Lease abgelaufen ist und ein neuer Worker übernommen hat (Epoch Guard).
    """
    state_file = tmp_path / "fences.json"
    boundary = EffectFencingBoundary(state_file)

    t0 = 1000.0
    # Worker Alpha erhält Lease (Generation 1)
    rec1 = boundary.acquire_lease("task-payout-1", "worker-alpha", ttl_seconds=10.0, now=t0)
    assert rec1.generation == 1
    assert rec1.holder == "worker-alpha"

    # Worker Alpha schläft ein (z.B. GC-Pause oder Netzwerkpartition)
    # Bei t0 + 15s ist die Lease abgelaufen. Worker Beta übernimmt (Generation 2)
    rec2 = boundary.acquire_lease("task-payout-1", "worker-beta", ttl_seconds=10.0, now=t0 + 15.0)
    assert rec2.generation == 2
    assert rec2.holder == "worker-beta"

    # Worker Beta autorisiert legitimen Effekt
    auth_beta = boundary.authorize_effect(
        "task-payout-1",
        "worker-beta",
        generation=2,
        effect_payload={"amount_cents": 5000, "recipient": "vendor-1"},
        now=t0 + 16.0,
    )
    assert auth_beta["authorized"] is True
    assert auth_beta["physical_effect_sequence"] == 1

    # ZOMBIE WORKER ALPHA WACHT AUF!
    # Prozess wurde nicht abgebrochen oder ignoriert SIGTERM.
    # Worker Alpha versucht immer noch mit alter Generation 1 einen Effekt zu autorisieren:
    with pytest.raises(StaleFencingTokenError, match="Stale fencing token 1 rejected"):
        boundary.authorize_effect(
            "task-payout-1",
            "worker-alpha",
            generation=1,
            effect_payload={"amount_cents": 5000, "recipient": "vendor-1"},
            now=t0 + 17.0,
        )

    # Invariante: Exakt 1 physikalischer Effekt autorisiert, 0 Doppel-Effekte!
    assert boundary.verify_no_duplicate_effect("task-payout-1") is True


def test_expired_lease_denies_authorization_even_without_takeover(tmp_path):
    """Beweist: Auch wenn noch kein neuer Worker übernommen hat, verweigert die Boundary

    die Autorisierung, sobald die Lease abgelaufen ist (zeitliche Fencing-Grenze).
    """
    state_file = tmp_path / "fences.json"
    boundary = EffectFencingBoundary(state_file)

    t0 = 2000.0
    rec = boundary.acquire_lease("task-mutation-1", "worker-slow", ttl_seconds=5.0, now=t0)
    assert rec.generation == 1

    # Versuch der Autorisierung nach Ablauf der Lease (t0 + 6.0s)
    with pytest.raises(LeaseExpiredError, match="Lease expired"):
        boundary.authorize_effect(
            "task-mutation-1",
            "worker-slow",
            generation=1,
            effect_payload={"action": "drop_partition"},
            now=t0 + 6.0,
        )

    assert boundary.verify_no_duplicate_effect("task-mutation-1") is True


def test_unknown_effect_quarantine_instead_of_blind_retry(tmp_path):
    """Beweist: Wenn eine Lease abläuft während die Aufgabe in der STARTED-Phase war

    (nicht-idempotenter Effekt möglicherweise begonnen), wird NICHT blind wiederholt,
    sondern die Aufgabe in NEEDS_RECONCILIATION blockiert.
    """
    state_file = tmp_path / "fences.json"
    boundary = EffectFencingBoundary(state_file)

    t0 = 3000.0
    boundary.acquire_lease(
        "task-charge-card",
        "worker-finance",
        ttl_seconds=10.0,
        effect_class=EffectClass.NON_IDEMPOTENT.value,
        now=t0,
    )

    # Worker autorisiert Effekt und wechselt in Phase STARTED
    boundary.authorize_effect(
        "task-charge-card",
        "worker-finance",
        generation=1,
        effect_payload={"amount": 99.00},
        now=t0 + 1.0,
    )

    # Worker stürzt mitten in der Ausführung ab oder verliert Verbindung
    # Watchdog stellt Lease-Ablauf fest:
    outcome = boundary.handle_lease_expiry_or_failover("task-charge-card", now=t0 + 15.0)

    # KERNERGEBNIS:
    assert outcome["status"] == "NEEDS_RECONCILIATION"
    assert outcome["reexecution_allowed"] is False
    assert outcome["recovery_reason"] == "STALE_WORKER_EFFECT_AMBIGUOUS"

    # BEWEIS: Neuer Worker darf die Aufgabe NICHT claimen oder ausführen!
    with pytest.raises(UnknownEffectQuarantinedError, match="quarantined for unknown external effect"):
        boundary.acquire_lease("task-charge-card", "worker-new", ttl_seconds=10.0, now=t0 + 16.0)


def test_reconciliation_confirmed_executed_prevents_duplicate_run(tmp_path):
    """Beweist: Nach externer Prüfung stellt sich heraus, dass der Effekt stattfand

    (CONFIRMED_EXECUTED) -> Aufgabe wird direkt als RECONCILED markiert,
    ohne ein zweites Mal ausgeführt zu werden.
    """
    state_file = tmp_path / "fences.json"
    boundary = EffectFencingBoundary(state_file)

    t0 = 4000.0
    boundary.acquire_lease("task-wire-transfer", "worker-tx", ttl_seconds=10.0, now=t0)
    boundary.authorize_effect("task-wire-transfer", "worker-tx", generation=1, effect_payload={}, now=t0 + 1.0)
    boundary.handle_lease_expiry_or_failover("task-wire-transfer", now=t0 + 15.0)

    # Betreiber prüft Bankkonto / externe API und sieht: Überweisung ist erfolgreich durchgegangen!
    rec_res = boundary.reconcile_unknown_effect(
        "task-wire-transfer",
        resolution=EffectResolution.CONFIRMED_EXECUTED,
        operator_id="operator-dennis",
        note="Verified transaction TX-99281 in external bank ledger",
    )

    assert rec_res["status"] == "RECONCILED"
    assert rec_res["reexecution_allowed"] is False

    # Invariante: Null doppelte Effekte
    assert boundary.verify_no_duplicate_effect("task-wire-transfer") is True


def test_reconciliation_proven_not_executed_allows_clean_retry(tmp_path):
    """Beweist: Wenn extern bewiesen ist, dass KEIN Effekt stattfand (PROVEN_NOT_EXECUTED),

    wird die Quarantäne aufgehoben und ein kontrollierter Retry mit neuer Generation erlaubt.
    """
    state_file = tmp_path / "fences.json"
    boundary = EffectFencingBoundary(state_file)

    t0 = 5000.0
    boundary.acquire_lease("task-api-post", "worker-crash", ttl_seconds=10.0, now=t0)
    boundary.authorize_effect("task-api-post", "worker-crash", generation=1, effect_payload={}, now=t0 + 1.0)
    boundary.handle_lease_expiry_or_failover("task-api-post", now=t0 + 15.0)

    # Externe Logs beweisen: Request hat den Server nie erreicht
    rec_res = boundary.reconcile_unknown_effect(
        "task-api-post",
        resolution=EffectResolution.PROVEN_NOT_EXECUTED,
        operator_id="operator-audit",
        note="Zero incoming requests logged in API gateway",
    )

    assert rec_res["status"] == "QUEUED"
    assert rec_res["reexecution_allowed"] is True

    # Jetzt darf Worker 2 die Aufgabe mit frischer Generation 2 übernehmen
    rec2 = boundary.acquire_lease("task-api-post", "worker-fresh", ttl_seconds=10.0, now=t0 + 30.0)
    assert rec2.generation == 2
    assert rec2.holder == "worker-fresh"


# =========================================================================
# Part 2: HTTP Integration Tests with server/app.py
# =========================================================================

def setup_server_with_goal(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    client = server_app.app.test_client()

    client.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-1", "capabilities": ["windows", "worker"]},
    )
    client.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-2", "capabilities": ["windows", "worker"]},
    )

    goal_res = client.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "idempotency and fencing verification",
            "workflow_plan": [
                {
                    "task_id": "task-fence-test",
                    "target_agent": "windows",
                    "instruction": "perform audited external update",
                    "artifacts": ["receipt.json"],
                    "effect_class": "non_idempotent",
                }
            ],
        },
    )
    assert goal_res.status_code == 200
    goal = goal_res.get_json()
    return client, state_file, goal["goal_id"]


def test_server_fencing_token_minting_and_stale_rejection(tmp_path, monkeypatch):
    """Beweist: server/app.py vergibt lease_generation / fencing_token und

    weist Stale Token eines Zombie-Workers mit HTTP 409 ab.
    """
    client, state_file, goal_id = setup_server_with_goal(tmp_path, monkeypatch)

    # 1. Worker 1 claimt Task -> erhält fencing_token = 1
    claim1 = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-1"})
    assert claim1.status_code == 200
    t1 = claim1.get_json()["task"]
    assert t1["task_id"] == "task-fence-test"
    assert t1["lease_generation"] == 1
    assert t1["fencing_token"] == 1

    # 2. Worker 1 geht stale (> 300s)
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["workers"]["WORKER-1"]["last_seen"] = time.time() - 600
    server_app.save_state(state)

    # Watchdog führt reclaim_stale aus
    reclaim = client.post("/tasks/reclaim_stale", headers=auth())
    assert reclaim.status_code == 200
    assert reclaim.get_json()["quarantined_tasks"] == 1

    # 3. Betreiber beweist Nicht-Start und resumed die Aufgabe für Worker 2
    res_rec = client.post(
        "/tasks/task-fence-test/resume",
        headers=auth(),
        json={"action": "reconcile", "resolution": "PROVEN_NOT_EXECUTED", "note": "Zero external mutations"},
    )
    assert res_rec.status_code == 200
    assert res_rec.get_json()["status"] == "RESUMED"

    # Worker 2 claimt die Aufgabe -> erhält frische Generation 2!
    claim2 = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-2"})
    assert claim2.status_code == 200
    t2 = claim2.get_json()["task"]
    assert t2["task_id"] == "task-fence-test"
    assert t2["lease_generation"] == 2
    assert t2["fencing_token"] == 2

    # 4. Zombie Worker 1 wacht auf und versucht Resultat mit alter Generation 1 einzureichen
    stale_payload = {
        "task_id": "task-fence-test",
        "worker_id": "WORKER-1",
        "attempt_id": t1["attempt_id"],
        "dispatch_id": t1["dispatch_id"],
        "lease_generation": 1,
        "fencing_token": 1,
        "status": "SUCCESS",
        "artifacts": [],
    }
    stale_res = client.post("/tasks/result", headers=auth(), json=stale_payload)
    # Muss mit 409 Conflict abgewiesen werden
    assert stale_res.status_code == 409


def test_server_reconciliation_confirmed_executed(tmp_path, monkeypatch):
    """Beweist: Server-Route /resume unterstützt action: reconcile mit CONFIRMED_EXECUTED

    und schließt Goal/Task sicher ab ohne zweite Ausführung.
    """
    client, state_file, goal_id = setup_server_with_goal(tmp_path, monkeypatch)

    # Claim & Stale Quarantäne
    client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-1"})
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["workers"]["WORKER-1"]["last_seen"] = time.time() - 600
    server_app.save_state(state)
    client.post("/tasks/reclaim_stale", headers=auth())

    # Reconcile mit CONFIRMED_EXECUTED
    rec = client.post(
        "/tasks/task-fence-test/resume",
        headers=auth(),
        json={
            "action": "reconcile",
            "resolution": "CONFIRMED_EXECUTED",
            "operator_id": "operator-dennis",
            "note": "External API debit confirmed via statement",
        },
    )
    assert rec.status_code == 200
    assert rec.get_json()["status"] == "RECONCILED"

    # Prüfe Zustand im Server State
    state_after = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after["tasks"]["task-fence-test"]["status"] == "RECONCILED"
    assert state_after["tasks"]["task-fence-test"]["reconciliation_resolution"] == "CONFIRMED_EXECUTED"
    assert state_after["goals"][goal_id]["status"] == "DONE"
