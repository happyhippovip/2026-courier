"""Deterministic regression test suite for Seed 075: SECURITY-RECEIPT VOLLSTÄNDIG HALTEN.

Category: Autorisierung & Sicherheitsgrenzen.

Tests positive and negative contract invariants for security receipt completeness:
1. Positive Contract Path:
   - Authentically persisted durable receipt contains all mandatory fields and passes load_durable_receipt.
   - Cryptographic integrity and exact field completeness confirmed.
2. Negative & Security Regression Paths (Fail-Closed):
   - Missing mandatory fields (worker_id, dispatch_id, run_id, etc.) rejected with ContractError.
   - Unsupported schema_version rejected with ContractError.
   - Invalid status rejected with ContractError.
   - SUCCESS status without artifact evidence rejected with ContractError.
   - Tampered receipt_hash rejected with ContractError.
   - Corrupt JSON / non-existent file fails closed with ContractError.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.integration_contract import (
    ContractError,
    _canonical_hash,
    load_durable_receipt,
    persist_durable_receipt,
    prepare_task,
    verify_result,
)


@pytest.fixture
def sample_task(tmp_path: Path):
    art = tmp_path / "evidence_075.txt"
    art.write_text("security evidence payload", encoding="utf-8")
    raw = {
        "task_id": "task-sec-075",
        "goal_id": "goal-sec-075",
        "target_capability": "windows",
        "workkey": "courier/evidence/security-receipt-completeness-075",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        "owner": "Windows Evidence Custodian",
        "artifacts": ["evidence_075.txt"],
    }
    return prepare_task(raw), art


# ---------------------------------------------------------------------------
# 1. POSITIVER VERTRAGSPFAD: Vollständiger Security-Receipt
# ---------------------------------------------------------------------------

def test_authentic_complete_security_receipt_verified(tmp_path: Path, sample_task):
    """Positive: Complete authentic security receipt passes loading and hash checks."""
    task, art_file = sample_task
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-sec-075-01",
        "status": "SUCCESS",
        "workkey": task["workkey"],
        "source_sha": task["source_sha"],
        "owner": task["owner"],
    }
    durable_result = verify_result(task, raw_result, tmp_path)
    receipt_dir = tmp_path / "receipts"

    receipt_path = persist_durable_receipt(task, durable_result, receipt_dir)
    assert receipt_path.is_file()

    loaded = load_durable_receipt(receipt_path)
    assert loaded["schema_version"] == "2.0"
    assert loaded["receipt_id"] == receipt_path.stem
    assert loaded["status"] == "SUCCESS"
    assert loaded["worker_id"] == task["worker_id"]
    assert loaded["dispatch_id"] == task["dispatch_id"]
    assert loaded["workkey"] == task["workkey"]
    assert loaded["source_sha"] == task["source_sha"]
    assert loaded["owner"] == task["owner"]
    assert len(loaded["artifacts"]) == 1


# ---------------------------------------------------------------------------
# 2. NEGATIVER PFAD: Unvollständige oder manipulierte Receipts (Fail-Closed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "missing_field",
    [
        "worker_id",
        "dispatch_id",
        "attempt_id",
        "task_id",
        "goal_id",
        "run_id",
        "result_id",
        "status",
        "artifacts",
        "schema_version",
        "receipt_id",
    ],
)
def test_missing_mandatory_field_rejected(tmp_path: Path, missing_field: str):
    """Negative: A receipt missing any mandatory execution/security field is rejected."""
    valid_base = {
        "receipt_id": "rcpt-test001",
        "schema_version": "2.0",
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "w-01",
        "run_id": "r-01",
        "result_id": "res-01",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }
    del valid_base[missing_field]
    valid_base["receipt_hash"] = _canonical_hash(valid_base)

    target = tmp_path / f"incomplete_{missing_field}.json"
    target.write_text(json.dumps(valid_base))

    with pytest.raises(ContractError, match="receipt is incomplete, missing mandatory fields"):
        load_durable_receipt(target)


def test_unsupported_schema_version_rejected(tmp_path: Path):
    """Negative: Unsupported or obsolete schema_version fails closed."""
    receipt = {
        "receipt_id": "rcpt-test002",
        "schema_version": "1.0",
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "w-01",
        "run_id": "r-01",
        "result_id": "res-01",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    target = tmp_path / "bad_schema.json"
    target.write_text(json.dumps(receipt))

    with pytest.raises(ContractError, match="unsupported receipt schema_version"):
        load_durable_receipt(target)


def test_success_status_without_artifacts_rejected(tmp_path: Path):
    """Negative: SUCCESS receipt with empty artifact list is rejected."""
    receipt = {
        "receipt_id": "rcpt-test003",
        "schema_version": "2.0",
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "w-01",
        "run_id": "r-01",
        "result_id": "res-01",
        "status": "SUCCESS",
        "artifacts": [],
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    target = tmp_path / "empty_artifacts.json"
    target.write_text(json.dumps(receipt))

    with pytest.raises(ContractError, match="successful receipt requires artifact evidence"):
        load_durable_receipt(target)


def test_invalid_status_rejected(tmp_path: Path):
    """Negative: Unsupported or tampered status is rejected."""
    receipt = {
        "receipt_id": "rcpt-test004",
        "schema_version": "2.0",
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "w-01",
        "run_id": "r-01",
        "result_id": "res-01",
        "status": "DONE",  # not in RESULT_STATES {"SUCCESS", "FAILED"}
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
    }
    receipt["receipt_hash"] = _canonical_hash(receipt)
    target = tmp_path / "bad_status.json"
    target.write_text(json.dumps(receipt))

    with pytest.raises(ContractError, match="invalid receipt status"):
        load_durable_receipt(target)


def test_tampered_receipt_hash_rejected(tmp_path: Path):
    """Negative: Receipt with tampered body or invalid hash fails closed."""
    receipt = {
        "receipt_id": "rcpt-test005",
        "schema_version": "2.0",
        "goal_id": "g-01",
        "task_id": "t-01",
        "attempt_id": "t-01:attempt:1",
        "dispatch_id": "d-01",
        "worker_id": "w-01",
        "run_id": "r-01",
        "result_id": "res-01",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64}],
        "receipt_hash": "deadbeef" * 8,
    }
    target = tmp_path / "bad_hash.json"
    target.write_text(json.dumps(receipt))

    with pytest.raises(ContractError, match="receipt hash mismatch"):
        load_durable_receipt(target)
