"""Comprehensive Contract Tests for CP-10 / CQ-10:
Dauerhafte Queue: Outbox, Result Ingest, and ACK-Binding Consistency.

Acceptance Criteria:
1. Keine Ergebnislöschung vor gültigem ACK (persist-before-send & ACK-before-clear).
2. Erneute Zustellung erzeugt keinen neuen logischen Effekt (idempotentes ACK_DUPLICATE).
3. Widersprüchliche Results bleiben unterscheidbar (Conflict 409 vs. Benign Duplicate 200).
4. Späte Zustellungen (Late / Stale Attempts) werden abgewiesen ohne Zustand zu verfälschen.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
import pytest

from courier_core.outbox_ack_boundary import (
    DurableOutboxBoundary,
    ResultIngestBoundary,
    ResultIngestStatus,
    DeliveryReceipt,
    OutboxBoundaryError,
)
from server import app as server_app


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


def make_durable_result(task, result_id="result-1", status="SUCCESS"):
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "pid-101",
        "result_id": result_id,
        "source_sha": "a" * 40,
        "status": status,
        "artifacts": [
            {"path": "output.txt", "sha256": hashlib.sha256(b"ok\n").hexdigest()}
        ],
    }


# =========================================================================
# Part 1: Outbox ACK-Before-Clear and FIFO Ordering Tests
# =========================================================================

def test_persist_before_send_creates_durable_fsynced_file(tmp_path):
    """Beweist: Ergebnisse werden vor jedem Netzwerkaufruf dauerhaft auf Disk geschrieben."""
    home = tmp_path / "worker_home"
    payload = {
        "dispatch_id": "dsp-1001",
        "task_id": "task-alpha",
        "worker_id": "worker-1",
        "attempt_id": "task-alpha:attempt:1",
        "status": "SUCCESS",
        "artifacts": [],
    }

    outbox_file = DurableOutboxBoundary.persist_result(home, payload)
    assert outbox_file.exists()
    assert outbox_file.name == "dsp-1001.json"

    with open(outbox_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["dispatch_id"] == "dsp-1001"
    assert loaded["status"] == "SUCCESS"


def test_no_deletion_before_valid_ack_on_transient_failure(tmp_path):
    """Beweist: Keine Ergebnislöschung vor gültigem ACK.

    Bei Verbindungsabbrüchen oder 5xx-Fehlern bleibt das Outbox-File erhalten.
    """
    home = tmp_path / "worker_home"
    payload = {
        "dispatch_id": "dsp-1002",
        "task_id": "task-network-test",
        "worker_id": "worker-1",
        "status": "SUCCESS",
        "artifacts": [],
    }
    file_path = DurableOutboxBoundary.persist_result(home, payload)
    assert file_path.exists()

    # Simulierter Netzwerkabsturz / Socket-Drop
    def dropping_deliver(p):
        raise ConnectionResetError("Socket dropped before ACK was delivered")

    receipt = DurableOutboxBoundary.deliver_with_ack(home, "dsp-1002", dropping_deliver)

    # KERNERGEBNISSE:
    assert receipt.cleared_from_outbox is False
    assert receipt.status == "DELIVERY_FAILED"
    # BEWEIS: Datei liegt weiterhin unverändert im Outbox-Verzeichnis!
    assert file_path.exists()


def test_deletion_occurs_only_after_verified_ack(tmp_path):
    """Beweist: Erst bei gültigem ACK (ACK_RESULT_RECEIVED) wird die Datei aus der Outbox gelöscht."""
    home = tmp_path / "worker_home"
    payload = {
        "dispatch_id": "dsp-1003",
        "task_id": "task-success-ack",
        "worker_id": "worker-1",
        "status": "SUCCESS",
        "artifacts": [],
    }
    file_path = DurableOutboxBoundary.persist_result(home, payload)
    assert file_path.exists()

    def successful_deliver(p):
        return {"status": "ACK_RESULT_RECEIVED", "dispatch_id": "dsp-1003"}

    receipt = DurableOutboxBoundary.deliver_with_ack(home, "dsp-1003", successful_deliver)

    assert receipt.status == "ACK_RESULT_RECEIVED"
    assert receipt.cleared_from_outbox is True
    # BEWEIS: Datei wurde sicher aus der Outbox entfernt
    assert not file_path.exists()


def test_deletion_also_clears_on_ack_duplicate(tmp_path):
    """Beweist: Auch bei einem ACK_DUPLICATE (bereits empfangenes Result)

    wird die Outbox bereinigt, da der Server den Erhalt bereits bestätigt hat.
    """
    home = tmp_path / "worker_home"
    payload = {
        "dispatch_id": "dsp-1004",
        "task_id": "task-dup-ack",
        "worker_id": "worker-1",
        "status": "SUCCESS",
        "artifacts": [],
    }
    file_path = DurableOutboxBoundary.persist_result(home, payload)
    assert file_path.exists()

    def duplicate_ack_deliver(p):
        return {"status": "ACK_DUPLICATE"}

    receipt = DurableOutboxBoundary.deliver_with_ack(home, "dsp-1004", duplicate_ack_deliver)

    assert receipt.status == "ACK_DUPLICATE"
    assert receipt.duplicate is True
    assert receipt.cleared_from_outbox is True
    assert not file_path.exists()


# =========================================================================
# Part 2: Server-Side Result Ingest & Deduplication Tests
# =========================================================================

def setup_server_with_task(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    client = server_app.app.test_client()

    client.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-INGEST", "capabilities": ["windows", "worker"]},
    )

    goal_res = client.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "result ingest idempotency test",
            "workflow_plan": [
                {
                    "task_id": "task-ingest-1",
                    "target_agent": "windows",
                    "instruction": "compute verifiable checksum",
                    "artifacts": ["checksum.txt"],
                    "effect_class": "non_idempotent",
                }
            ],
        },
    )
    assert goal_res.status_code == 200
    goal = goal_res.get_json()
    return client, state_file, goal["goal_id"]


def test_duplicate_delivery_produces_zero_new_logical_effects(tmp_path, monkeypatch):
    """Beweist: Erneute Zustellung desselben Ergebnisses erzeugt KEINEN neuen logischen Effekt.

    Server antwortet mit ACK_DUPLICATE; keine erneute Status-Mutation, keine doppelten Verifications.
    """
    client, state_file, goal_id = setup_server_with_task(tmp_path, monkeypatch)

    # Claim Task
    claim_res = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-INGEST"})
    assert claim_res.status_code == 200
    task = claim_res.get_json()["task"]

    result_payload = make_durable_result(task, result_id="res-unique-991", status="SUCCESS")

    # 1. Erste Zustellung
    r1 = client.post("/tasks/result", headers=auth(), json=result_payload)
    assert r1.status_code == 200
    assert r1.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Zustand nach 1. Zustellung einfrieren
    state_after_first = json.loads(state_file.read_text(encoding="utf-8"))
    task_after_first = state_after_first["tasks"]["task-ingest-1"]
    assert task_after_first["status"] == "RESULT_RECEIVED"
    first_attempts = task_after_first.get("attempts", 1)

    # 2. Zweite Zustellung (Duplicate Replay, z.B. nach Timeout oder Packet Re-send)
    r2 = client.post("/tasks/result", headers=auth(), json=result_payload)
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "ACK_DUPLICATE"

    # 3. Dritte Zustellung
    r3 = client.post("/tasks/result", headers=auth(), json=result_payload)
    assert r3.status_code == 200
    assert r3.get_json()["status"] == "ACK_DUPLICATE"

    # BEWEIS: Absolut identischer Zustand, 0 neue logische Effekte
    state_after_dups = json.loads(state_file.read_text(encoding="utf-8"))
    task_after_dups = state_after_dups["tasks"]["task-ingest-1"]

    assert task_after_dups["status"] == "RESULT_RECEIVED"
    assert task_after_dups.get("attempts", 1) == first_attempts
    assert task_after_dups["result"] == task_after_first["result"]


def test_contradictory_result_rejected_as_conflict_409(tmp_path, monkeypatch):
    """Beweist: Widersprüchliche Results für eine bereits bearbeitete Aufgabe

    bleiben unterscheidbar und werden mit HTTP 409 Conflict abgewiesen.
    """
    client, state_file, goal_id = setup_server_with_task(tmp_path, monkeypatch)

    claim_res = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-INGEST"})
    task = claim_res.get_json()["task"]

    # Erstes legitimes Resultat
    valid_payload = make_durable_result(task, result_id="res-original", status="SUCCESS")
    r1 = client.post("/tasks/result", headers=auth(), json=valid_payload)
    assert r1.status_code == 200
    assert r1.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Widersprüchliches Resultat (gleiche Task, aber abweichender Status oder anderer Inhalt)
    contradictory_payload = make_durable_result(task, result_id="res-divergent-fake", status="FAILURE")
    r_conflict = client.post("/tasks/result", headers=auth(), json=contradictory_payload)

    # KERNERGEBNIS:
    assert r_conflict.status_code == 409
    assert "Conflicting result for already processed task" in r_conflict.get_json()["error"]

    # Ursprünglicher Zustand bleibt geschützt
    state_curr = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_curr["tasks"]["task-ingest-1"]["result"]["result_id"] == "res-original"


def test_late_result_from_superseded_attempt_rejected_409(tmp_path, monkeypatch):
    """Beweist: Ein verspätetes Resultat aus einem alten/überholten Attempt

    wird strikt abgewiesen (HTTP 409) und überschreibt nicht den aktuellen Task-Zustand.
    """
    client, state_file, goal_id = setup_server_with_task(tmp_path, monkeypatch)

    # Worker 1 claimt Attempt 1
    claim1 = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-INGEST"})
    t1 = claim1.get_json()["task"]
    assert t1["attempts"] == 1

    # Worker 1 geht stale -> Quarantäne & Resume erteilt Attempt 2
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["workers"]["WORKER-INGEST"]["last_seen"] = time.time() - 600
    server_app.save_state(state)
    client.post("/tasks/reclaim_stale", headers=auth())

    # Resume Task
    client.post("/tasks/task-ingest-1/resume", headers=auth(), json={"action": "retry"})

    # Worker re-registriert sich frisch
    client.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "WORKER-INGEST", "capabilities": ["windows", "worker"]},
    )

    # Worker claimt Attempt 2
    claim2 = client.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-INGEST"})
    t2 = claim2.get_json()["task"]
    assert t2 is not None
    assert t2["attempts"] == 2
    assert t2["attempt_id"] != t1["attempt_id"]
    assert t2["dispatch_id"] != t1["dispatch_id"]

    # Nun trifft verspätet ein Resultat aus dem alten Attempt 1 ein:
    late_payload = make_durable_result(t1, result_id="res-late-1", status="SUCCESS")
    late_res = client.post("/tasks/result", headers=auth(), json=late_payload)

    # Muss mit 409 Conflict abgewiesen werden
    assert late_res.status_code == 409
    assert "attempt or dispatch mismatch, possible replay" in late_res.get_json()["error"]

    # Task befindet sich weiterhin im aktiven Attempt 2!
    state_after_late = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_after_late["tasks"]["task-ingest-1"]["attempts"] == 2
    assert state_after_late["tasks"]["task-ingest-1"]["dispatch_id"] == t2["dispatch_id"]
