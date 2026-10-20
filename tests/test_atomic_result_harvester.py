"""Deterministic tests for Atomic Result Harvester.

Mission: Zurückgegebene Worker-Ergebnisse dürfen weder verlorengehen noch doppelt verbucht werden.

Testabdeckung:
1. Valid Result: Erstes echtes Resultat wird atomar verbucht (Status: RESULT_RECEIVED, ACK_RESULT_RECEIVED).
2. Identical Replay: Exakter Replay ist idempotent (ACK_DUPLICATE, HTTP 200, DUPLICATE_SIDE_EFFECT_COUNT == 0).
3. Contradictory Result: Widerspruch mit gleicher logischer Identität (veränderter Status/Artifacts/Result-ID)
   wird mit 409 Conflict abgewiesen und überschreibt nicht die ursprüngliche Wahrheit.
4. Claim-Owner & Attempt-Schutz: Fremde Worker oder veraltete Attempts werden abgewiesen.
5. Persistenzgrenze: Überprüfung der persistenten Vorher- und Nachher-Zustände auf Plattenebene.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from server import app as server_app
from scripts.integration_contract import (
    ContractError,
    load_durable_receipt,
    persist_durable_receipt,
    validate_durable_result,
)


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


def setup_client_and_claimed_task(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    http = server_app.app.test_client()

    # Register legitimate worker
    reg = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WINDOWS-01", "platform": "windows", "capabilities": ["windows"]},
    )
    assert reg.status_code == 200

    # Create goal with deterministic task
    goal_res = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "harvest test goal",
            "workflow_plan": [
                {
                    "task_id": "harvest-task-1",
                    "target_agent": "windows",
                    "instruction": "produce harvest.txt",
                    "artifacts": ["harvest.txt"],
                }
            ],
        },
    )
    assert goal_res.status_code == 200
    goal = goal_res.get_json()

    # Worker claims task
    claim_res = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WINDOWS-01"})
    assert claim_res.status_code == 200
    task = claim_res.get_json()["task"]
    assert task["status"] == "DISPATCHED"
    assert task["worker_id"] == "WINDOWS-01"

    return http, state_file, goal["goal_id"], task


def make_durable_result(task, status="SUCCESS", content=b"harvest-artifact\n"):
    art_sha = hashlib.sha256(content).hexdigest()
    # Compute deterministic result_id
    identity = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-pid-456",
        "status": status,
        "source_sha": "0" * 40,
        "artifacts": [{"path": "harvest.txt", "sha256": art_sha}],
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    identity["result_id"] = f"result-{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"
    return identity


def test_atomic_result_harvester_valid_replay_and_conflict(tmp_path, monkeypatch):
    """Prüfe atomare Übernahme, idempotenten Replay und Abweisung von Widersprüchen."""
    http, state_file, goal_id, task = setup_client_and_claimed_task(tmp_path, monkeypatch)

    # 1. Vorher-Zustand erfassen (persisted on disk)
    state_before = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_before["tasks"][task["task_id"]]["status"] == "DISPATCHED"
    assert state_before["tasks"][task["task_id"]]["worker_id"] == "WINDOWS-01"
    assert "result" not in state_before["tasks"][task["task_id"]]

    valid_res = make_durable_result(task, status="SUCCESS", content=b"initial-valid-content")

    # --- PHASE 1: Erstes gültiges Resultat ---
    resp1 = http.post("/tasks/result", headers=auth(), json=valid_res)
    assert resp1.status_code == 200
    assert resp1.get_json() == {"status": "ACK_RESULT_RECEIVED"}

    state_after_first = json.loads(state_file.read_text(encoding="utf-8"))
    task_after_first = state_after_first["tasks"][task["task_id"]]
    assert task_after_first["status"] == "RESULT_RECEIVED"
    assert task_after_first["result"]["result_id"] == valid_res["result_id"]
    assert task_after_first["result"]["status"] == "SUCCESS"

    # --- PHASE 2: Exakt gleiches Resultat erneut (Replay) ---
    # Messung von Nebeneffekten
    duplicate_side_effect_count = 0
    resp2 = http.post("/tasks/result", headers=auth(), json=valid_res)
    assert resp2.status_code == 200
    assert resp2.get_json() == {"status": "ACK_DUPLICATE"}

    state_after_replay = json.loads(state_file.read_text(encoding="utf-8"))
    if state_after_replay != state_after_first:
        duplicate_side_effect_count += 1

    assert duplicate_side_effect_count == 0, "Idempotenter Replay darf keinerlei Nebeneffekte erzeugen"
    assert state_after_replay == state_after_first

    # --- PHASE 3: Widersprüchliches Resultat mit gleicher logischer Identität ---
    # Erzeuge widersprüchliches Resultat (z. B. anderer Status FAILED oder manipulierte Artefakte)
    conflicting_res = copy.deepcopy(valid_res)
    conflicting_res["result_id"] = "result-altered-id-789"
    conflicting_res["status"] = "FAILED"
    conflicting_res["artifacts"] = [{"path": "harvest.txt", "sha256": "0" * 64}]

    resp3 = http.post("/tasks/result", headers=auth(), json=conflicting_res)
    assert resp3.status_code == 409, "Widersprüchliches Resultat muss mit 409 Conflict abgewiesen werden"
    assert "Conflicting result for already processed task" in resp3.get_json()["error"]

    # Prüfe: Die ursprüngliche Wahrheit wurde NICHT überschrieben
    state_after_conflict = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after_conflict == state_after_first
    assert state_after_conflict["tasks"][task["task_id"]]["result"]["result_id"] == valid_res["result_id"]
    assert state_after_conflict["tasks"][task["task_id"]]["result"]["status"] == "SUCCESS"


def test_atomic_result_harvester_claim_owner_and_attempt_fencing(tmp_path, monkeypatch):
    """Prüfe Schutz gegen fremde Worker und veraltete Attempts."""
    http, state_file, goal_id, task = setup_client_and_claimed_task(tmp_path, monkeypatch)

    # 1. Fremder Worker versucht Resultat einzuliefern
    forged_worker_res = make_durable_result(task)
    forged_worker_res["worker_id"] = "ALIEN-WORKER-99"

    resp_alien = http.post("/tasks/result", headers=auth(), json=forged_worker_res)
    assert resp_alien.status_code in (400, 409)
    assert any(msg in resp_alien.get_json()["error"] for msg in ("Invalid task or worker", "worker_id mismatch"))

    # 2. Veralteter Attempt
    stale_attempt_res = make_durable_result(task)
    stale_attempt_res["attempt_id"] = "stale-attempt-999"

    resp_stale = http.post("/tasks/result", headers=auth(), json=stale_attempt_res)
    assert resp_stale.status_code == 409
    assert "attempt or dispatch mismatch" in resp_stale.get_json()["error"]

    # Task muss weiterhin unverändert auf DISPATCHED stehen
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_durable_receipt_persistence_boundary(tmp_path):
    """Prüfe Persistenzgrenze, idempotenten Receipt-Schreibvorgang und Konflikt-Schutz."""
    receipt_dir = tmp_path / "receipts"
    task = {
        "goal_id": "g-receipt-1",
        "task_id": "t-receipt-1",
        "workkey": "WORKKEY-RECEIPT-01",
        "attempt_id": "att-1",
        "dispatch_id": "disp-1",
        "worker_id": "WORKER-01",
        "source_sha": "abc1234567890abcdef1234567890abcdef12345",
    }
    result = {
        "goal_id": "g-receipt-1",
        "task_id": "t-receipt-1",
        "workkey": "WORKKEY-RECEIPT-01",
        "attempt_id": "att-1",
        "dispatch_id": "disp-1",
        "worker_id": "WORKER-01",
        "source_sha": "abc1234567890abcdef1234567890abcdef12345",
        "run_id": "pid-777",
        "result_id": "result-receipt123456",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "a" * 64}],
    }

    # 1. Erste Persistierung
    receipt_path = persist_durable_receipt(task, result, receipt_dir)
    assert receipt_path.is_file()
    initial_mtime = receipt_path.stat().st_mtime_ns
    initial_content = receipt_path.read_text(encoding="utf-8")

    # 2. Exakter Replay (Idempotenz)
    duplicate_side_effect_count = 0
    replay_path = persist_durable_receipt(task, result, receipt_dir)
    assert replay_path == receipt_path
    if (
        receipt_path.stat().st_mtime_ns != initial_mtime
        or receipt_path.read_text(encoding="utf-8") != initial_content
    ):
        duplicate_side_effect_count += 1

    assert duplicate_side_effect_count == 0, "Idempotenter Receipt-Replay darf Datei nicht neu schreiben"

    # 3. Widersprüchliches Resultat für dieselbe Quittungs-Identität
    conflicting_result = dict(result)
    conflicting_result["artifacts"] = [{"path": "out.txt", "sha256": "f" * 64}]

    with pytest.raises(ContractError, match="Conflicting result for already processed task"):
        persist_durable_receipt(task, conflicting_result, receipt_dir)

    # Quittung bleibt integer und unverändert
    loaded = load_durable_receipt(receipt_path)
    assert loaded["result_id"] == result["result_id"]
    assert loaded["artifacts"][0]["sha256"] == "a" * 64
