"""Deterministic offline test suite for Seed 031: PROVENIENZ ÜBER RELOAD HALTEN.

Category: Ledger & dauerhafte Wahrheit.

Tests comprehensive positive & negative contract paths:
1. Positive Path:
   - Full provenance tuple (workkey, source_sha, input_fingerprint, owner, action, test_result, next_action)
     dispatched and persisted.
   - State cold reload: load_state restores all provenance fields intact.
   - Matching result submitted and verified with verify_result and validate_durable_result.
   - Independent verifier reconciles with durable verification receipt.
2. Negative & Security Regression Paths:
   - Tampered input_fingerprint fails closed with ContractError / 400.
   - Tampered owner fails closed with ContractError / 400.
   - Tampered action / test_result / next_action fails closed with ContractError / 400.
   - Invented provenance fields on result rejected (ContractError: ... invented on result).
   - Tampered state file signature on reload detected via HMAC and rejected fail-closed.
   - Worker restart and loss of task state marks task as HUMAN_REQUIRED without losing provenance.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from scripts.integration_contract import (
    ContractError,
    prepare_task,
    validate_durable_result,
    verify_result,
)
from server import app as server_app

TEST_SECRET = "test-secret-031"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": "Bearer verifier-secret-031", "Content-Type": "application/json"}


@pytest.fixture
def courier_env(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {},
        "seq": 0,
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret-031")
    with server_app.app.test_client() as client:
        yield client, state_file, tmp_path


# ---------------------------------------------------------------------------
# 1. POSITIVER VERTRAGSPFAD: Provenienz über State-Reload & Verifikation
# ---------------------------------------------------------------------------

def test_provenance_preserved_across_cold_reload_and_verification(courier_env):
    """Positive: Dispatched provenance survives cold reload and binds to durable result."""
    client, state_file, ws_root = courier_env

    # 1. Register qualified worker
    reg = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": "WIN-CUSTODIAN-01", "capabilities": ["windows"], "platform": "windows"},
    )
    assert reg.status_code == 200

    # 2. Dispatch task with rich provenance
    goal_res = client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "Verify provenance continuity over reload",
            "workflow_plan": [
                {
                    "task_id": "task-prov-031",
                    "target_agent": "windows",
                    "workkey": "courier/evidence/provenance-reload-031",
                    "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
                    "input_fingerprint": "fp-input-deterministic-999",
                    "owner": "Windows Evidence Custodian",
                    "action": "AUDIT_PROVENANCE",
                    "test_result": "PASS",
                    "next_action": "PERSIST_RECEIPT",
                    "artifacts": ["receipt_031.txt"],
                }
            ],
        },
    )
    assert goal_res.status_code == 200

    # 3. Worker claims task
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-CUSTODIAN-01"})
    task = claim_res.get_json()["task"]
    assert task is not None
    assert task["task_id"] == "task-prov-031"
    assert task["workkey"] == "courier/evidence/provenance-reload-031"
    assert task["source_sha"] == "fac447f5c9c22936177069566b82c7319bc35f5c"
    assert task["owner"] == "Windows Evidence Custodian"

    # 4. Simulate server restart / cold reload
    reloaded_state = server_app.load_state()
    reloaded_task = reloaded_state["tasks"]["task-prov-031"]
    for field in (
        "workkey",
        "source_sha",
        "input_fingerprint",
        "owner",
        "action",
        "test_result",
        "next_action",
    ):
        assert reloaded_task[field] == task[field], f"Field {field} lost on reload"

    # 5. Worker completes task and creates artifact
    art_file = ws_root / "receipt_031.txt"
    art_file.write_text("authentic receipt content", encoding="utf-8")
    import hashlib
    art_sha = hashlib.sha256(art_file.read_bytes()).hexdigest()

    # Worker builds matching DurableResult
    result_payload = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WIN-CUSTODIAN-01",
        "run_id": "run-prov-001",
        "status": "SUCCESS",
        "workkey": "courier/evidence/provenance-reload-031",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        "input_fingerprint": "fp-input-deterministic-999",
        "owner": "Windows Evidence Custodian",
        "action": "AUDIT_PROVENANCE",
        "test_result": "PASS",
        "next_action": "PERSIST_RECEIPT",
        "artifacts": [{"path": "receipt_031.txt", "sha256": art_sha}],
    }
    # Derive canonical result_id
    verified_identity = verify_result(task, result_payload, ws_root)
    result_payload["result_id"] = verified_identity["result_id"]

    # 6. Post result to server
    res_post = client.post("/tasks/result", headers=AUTH_HEADERS, json=result_payload)
    assert res_post.status_code == 200
    assert res_post.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # 7. Independent verification
    verify_post = client.post(
        "/tasks/verify",
        headers=VERIFIER_HEADERS,
        json={
            "task_id": "task-prov-031",
            "verifier_id": "VERIFIER-INDEPENDENT-01",
            "result_id": verified_identity["result_id"],
            "artifacts": result_payload["artifacts"],
            "verdict": "PASS",
        },
    )
    assert verify_post.status_code == 200
    assert verify_post.get_json()["status"] == "RECONCILED"

    # 8. Post-verification reload preserves complete reconciled provenance
    final_state = server_app.load_state()
    final_task = final_state["tasks"]["task-prov-031"]
    assert final_task["status"] == "RECONCILED"
    assert final_task["result"]["workkey"] == "courier/evidence/provenance-reload-031"
    assert final_task["result"]["source_sha"] == "fac447f5c9c22936177069566b82c7319bc35f5c"
    assert final_task["result"]["owner"] == "Windows Evidence Custodian"
    assert final_task["verification"]["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# 2. NEGATIVER PFAD: Provenienz-Mismatches & Tampering (Fail-Closed)
# ---------------------------------------------------------------------------

def test_tampered_input_fingerprint_rejected(courier_env):
    """Negative: Tampered input_fingerprint on result raises ContractError / 400."""
    _, _, ws_root = courier_env
    task = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "artifacts": ["out.txt"],
        "input_fingerprint": "fp-original",
    }
    raw = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "run_id": "run-01",
        "status": "SUCCESS",
        "input_fingerprint": "fp-tampered-altered",
    }
    canary = ws_root / "out.txt"
    canary.write_text("data")
    with pytest.raises(ContractError, match="input_fingerprint mismatch"):
        verify_result(task, raw, ws_root)


def test_tampered_owner_rejected(courier_env):
    """Negative: Tampered owner on result raises ContractError / 400."""
    _, _, ws_root = courier_env
    task = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "artifacts": ["out.txt"],
        "owner": "Authorized Owner",
    }
    raw = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "run_id": "run-01",
        "status": "SUCCESS",
        "owner": "Attacker Impersonator",
    }
    canary = ws_root / "out.txt"
    canary.write_text("data")
    with pytest.raises(ContractError, match="owner mismatch"):
        verify_result(task, raw, ws_root)


def test_tampered_lifecycle_fields_rejected(courier_env):
    """Negative: Tampered action / test_result / next_action raises ContractError."""
    _, _, ws_root = courier_env
    canary = ws_root / "out.txt"
    canary.write_text("data")

    for field in ("action", "test_result", "next_action"):
        task = {
            "goal_id": "g-01",
            "task_id": "t-01",
            "attempt_id": "t-01:attempt:1",
            "dispatch_id": "d-01",
            "worker_id": "WIN-01",
            "artifacts": ["out.txt"],
            field: "original_val",
        }
        raw = {
            "goal_id": "g-01",
            "task_id": "t-01",
            "attempt_id": "t-01:attempt:1",
            "dispatch_id": "d-01",
            "worker_id": "WIN-01",
            "run_id": "run-01",
            "status": "SUCCESS",
            field: "tampered_val",
        }
        with pytest.raises(ContractError, match=f"{field} mismatch"):
            verify_result(task, raw, ws_root)


def test_invented_provenance_rejected(courier_env):
    """Negative: Result cannot invent undeclared provenance fields."""
    _, _, ws_root = courier_env
    task = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "artifacts": ["out.txt"],
    }
    raw = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "run_id": "run-01",
        "status": "SUCCESS",
        "input_fingerprint": "invented-fp",
    }
    canary = ws_root / "out.txt"
    canary.write_text("data")
    with pytest.raises(ContractError, match="input_fingerprint invented on result"):
        verify_result(task, raw, ws_root)


def test_tampered_state_signature_detected_on_reload(courier_env):
    """Negative: Tampering with central state file signature halts reload fail-closed."""
    client, state_file, _ = courier_env

    # 1. Save valid signed state
    state = {"goals": {"g-test": {"status": "ACTIVE"}}, "tasks": {}, "workers": {}}
    server_app.save_state(state)

    sig_file = Path(f"{state_file}.sig")
    assert sig_file.is_file()

    # 2. Corrupt signature
    sig_file.write_text("deadbeef" * 8, encoding="utf-8")

    # 3. Reload must fail closed
    with pytest.raises(RuntimeError, match="State file signature mismatch! Tampering detected."):
        server_app.load_state()


def test_worker_crash_and_task_quarantine_retains_provenance(courier_env):
    """Negative: Worker loss of task quarantines task to HUMAN_REQUIRED without dropping provenance."""
    client, state_file, _ = courier_env

    # 1. Register worker
    client.post("/workers/register", headers=AUTH_HEADERS, json={"worker_id": "WIN-QUARANTINE", "capabilities": ["windows"]})

    # 2. Goal with provenance
    client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "Quarantine provenance test",
            "workflow_plan": [
                {
                    "task_id": "task-quarantine-01",
                    "target_agent": "windows",
                    "workkey": "courier/quarantine-key",
                    "source_sha": "abc123456",
                    "input_fingerprint": "fp-quarantine",
                    "owner": "Guardian",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )

    # 3. Claim
    claim = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-QUARANTINE"})
    assert claim.status_code == 200

    # 4. Worker crashes and reconnects reporting current_task=None (lost state)
    reconnect = client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": "WIN-QUARANTINE", "capabilities": ["windows"], "current_task": None},
    )
    assert reconnect.status_code == 200

    # 5. Check quarantined state
    state = server_app.load_state()
    quarantined = state["tasks"]["task-quarantine-01"]
    assert quarantined["status"] == "HUMAN_REQUIRED"
    assert quarantined["recovery_reason"] == "WORKER_RESTARTED_AND_LOST_STATE"
    # Provenance fields MUST remain intact
    assert quarantined["workkey"] == "courier/quarantine-key"
    assert quarantined["source_sha"] == "abc123456"
    assert quarantined["input_fingerprint"] == "fp-quarantine"
    assert quarantined["owner"] == "Guardian"
