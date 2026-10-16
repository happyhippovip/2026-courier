"""Deterministic test suite for Seed 074: OWNER-CLAIM-SPOOFING ABWEHREN.

Category: Autorisierung & Sicherheitsgrenzen.

Tests positive and negative security invariants:
1. Positive Path:
   - Legitimate owner acquires exclusive claim in VerifiedContinuation.
   - Legitimate owner renews claim before expiry.
   - Legitimate owner releases claim cleanly.
   - Legitimate task with bound owner matches DurableResult owner.
2. Negative & Security Invariants (Fail-Closed):
   - Impersonator cannot overwrite or steal an active lease held by another owner.
   - Impersonator cannot spoof release of another owner's claim.
   - Result with spoofed owner rejected with ContractError ('owner mismatch').
   - Result with tampered owner rejected by verify_result.
   - Server rejects result with owner mismatch.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.integration_contract import (
    ContractError,
    validate_durable_result,
    verify_result,
)
from scripts.verified_continuation import VerifiedContinuation
from server import app as server_app

TEST_SECRET = "test-secret-074"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}
VERIFIER_HEADERS = {"Authorization": "Bearer verifier-secret-074", "Content-Type": "application/json"}


@pytest.fixture
def continuation_engine(tmp_path):
    root_dir = tmp_path / "repo"
    ledger_dir = tmp_path / "ledger"
    root_dir.mkdir(parents=True, exist_ok=True)
    return VerifiedContinuation(root_dir=root_dir, ledger_dir=ledger_dir)


@pytest.fixture
def courier_server(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    init_state = {"goals": {}, "tasks": {}, "workers": {}, "seq": 0}
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret-074")
    with server_app.app.test_client() as client:
        yield client, state_file, tmp_path


# ---------------------------------------------------------------------------
# 1. VERIFIED CONTINUATION: ATOMIC OWNER LEASE GUARDS
# ---------------------------------------------------------------------------

def test_legitimate_owner_claim_renew_release(continuation_engine):
    """Positive: Authorized owner claims, renews, and cleanly releases workkey."""
    workkey = "LEGITIMATE_TASK_01"
    owner = "Windows Evidence Custodian"

    assert continuation_engine.claim(workkey, owner=owner, ttl_s=3600) is True
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info is not None
    assert claim_info["owner"] == owner

    # Renewal by same owner succeeds
    assert continuation_engine.claim(workkey, owner=owner, ttl_s=3600) is True

    # Clean release by same owner succeeds
    assert continuation_engine.release(workkey, owner=owner) is True
    assert continuation_engine.is_claimed(workkey) is None


def test_impersonator_claim_spoof_prevented(continuation_engine):
    """Negative: Impersonator cannot steal or overwrite an active claim owned by another."""
    workkey = "PROTECTED_WORKKEY_99"
    legit_owner = "Windows Evidence Custodian"
    impersonator = "Rogue Attacker"

    # Legitimate owner claims
    assert continuation_engine.claim(workkey, owner=legit_owner, ttl_s=3600) is True

    # Impersonator attempts to claim same active workkey -> REJECTED
    assert continuation_engine.claim(workkey, owner=impersonator, ttl_s=3600) is False

    # Owner remains the legitimate owner
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info["owner"] == legit_owner


def test_impersonator_release_spoof_prevented(continuation_engine):
    """Negative: Impersonator cannot release or evict another owner's active claim."""
    workkey = "PROTECTED_WORKKEY_100"
    legit_owner = "Windows Evidence Custodian"
    impersonator = "Rogue Attacker"

    assert continuation_engine.claim(workkey, owner=legit_owner, ttl_s=3600) is True

    # Impersonator attempts to release -> REJECTED
    assert continuation_engine.release(workkey, owner=impersonator) is False

    # Claim remains actively locked by legitimate owner
    claim_info = continuation_engine.is_claimed(workkey)
    assert claim_info is not None
    assert claim_info["owner"] == legit_owner


# ---------------------------------------------------------------------------
# 2. INTEGRATION CONTRACT: DURABLE RESULT OWNER SPOOFING GUARDS
# ---------------------------------------------------------------------------

def test_spoofed_result_owner_rejected_by_verify_result(tmp_path):
    """Negative: Result asserting a spoofed owner is rejected fail-closed by verify_result."""
    canary = tmp_path / "art.txt"
    canary.write_text("proof")

    task = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "artifacts": ["art.txt"],
        "owner": "Authorized Owner",
    }
    spoofed_result = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "run_id": "run-01",
        "status": "SUCCESS",
        "owner": "Spoofed Owner",
        "artifacts": [{"path": "art.txt", "sha256": "0" * 64}],
    }

    with pytest.raises(ContractError, match="owner mismatch"):
        verify_result(task, spoofed_result, tmp_path)


def test_spoofed_result_owner_rejected_by_validate_durable_result():
    """Negative: validate_durable_result rejects mismatched owner."""
    task = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "owner": "Authentic Owner",
    }
    spoofed = {
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "WIN-01",
        "run_id": "run-01",
        "result_id": "result-12345",
        "status": "SUCCESS",
        "owner": "Fraudulent Impersonator",
        "artifacts": [{"path": "out.txt", "sha256": "a" * 64}],
    }

    with pytest.raises(ContractError, match="owner mismatch"):
        validate_durable_result(task, spoofed)


# ---------------------------------------------------------------------------
# 3. CONTROL PLANE: SERVER-SIDE OWNER INTEGRITY
# ---------------------------------------------------------------------------

def test_server_enforces_owner_integrity_on_result_submission(courier_server):
    """End-to-end: Server rejects result submission when result owner conflicts with task owner."""
    client, _, ws_root = courier_server

    client.post("/workers/register", headers=AUTH_HEADERS, json={"worker_id": "WIN-01", "capabilities": ["windows"]})

    # Create goal with owner on task
    client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "Owner protection goal",
            "workflow_plan": [
                {
                    "task_id": "task-owner-01",
                    "target_agent": "windows",
                    "owner": "Original Owner",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )

    # Claim
    claim_res = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WIN-01"})
    task = claim_res.get_json()["task"]
    assert task["owner"] == "Original Owner"

    # Worker creates artifact
    (ws_root / "out.txt").write_text("done")

    # Worker attempts to submit result with spoofed owner
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WIN-01",
        "run_id": "run-owner-test",
        "result_id": "result-fake-1",
        "status": "SUCCESS",
        "owner": "Spoofed Impersonator",
        "artifacts": [{"path": "out.txt", "sha256": "b" * 64}],
    }

    res_post = client.post("/tasks/result", headers=AUTH_HEADERS, json=bad_result)
    assert res_post.status_code == 400
    assert "owner mismatch" in res_post.get_json()["error"]
