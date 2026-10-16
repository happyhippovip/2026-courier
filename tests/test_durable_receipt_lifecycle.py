"""Test suite verifying end-to-end Execution Result to Durable Receipt binding.

Tests all required aspects of:
1. All 8 bound fields: Task-ID, Workkey, Attempt, Ausführungs-ID (dispatch/run),
   Worker-ID, Source-SHA, Status, and Resultat (artifacts).
2. Unknown values must not be invented (fail closed).
3. Test cases:
   - Erfolgreicher Task (SUCCESS)
   - Fehlerhafter Task (FAILED)
   - Fehlendes Ergebnis / Mismatch
   - Doppeltes Resultat (Idempotent ACK vs. 409 Conflict)
   - Neustart nach Ergebnisspeicherung (Reload in a fresh sub-process).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.integration_contract import (
    ContractError,
    load_durable_receipt,
    persist_durable_receipt,
    prepare_task,
    validate_durable_result,
    verify_result,
)

SOURCE_SHA = "fac447f5c9c22936177069566b82c7319bc35f5c"
WORKKEY = "WORKKEY-COURIER-RECEIPT-01"


def _make_task(tmp_path: Path, **overrides) -> tuple[dict, Path]:
    artifact_name = "canary_output.txt"
    artifact_path = tmp_path / artifact_name
    artifact_path.write_text("verified canary effect\n", encoding="utf-8")

    base = {
        "task_id": "task-receipt-001",
        "goal_id": "goal-receipt-demo",
        "target_capability": "windows",
        "workkey": WORKKEY,
        "source_sha": SOURCE_SHA,
        "artifacts": [artifact_name],
    }
    base.update(overrides)
    task = prepare_task(base)
    return task, artifact_path


def test_successful_task_produces_durable_receipt_with_all_bound_fields(tmp_path: Path):
    """Case 1: Successful task correctly binds all 8 identity/result fields into a durable receipt."""
    task, artifact_file = _make_task(tmp_path)
    workspace = tmp_path

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-windows-901",
        "status": "SUCCESS",
    }

    # 1. Verify and bind into canonical DurableResult
    durable = verify_result(task, raw_result, workspace)

    # Assert all 8 fields are strictly connected
    assert durable["task_id"] == "task-receipt-001"
    assert durable["workkey"] == WORKKEY
    assert durable["attempt_id"] == task["attempt_id"]
    assert durable["dispatch_id"] == task["dispatch_id"]
    assert durable["worker_id"] == "WINDOWS-01"
    assert durable["source_sha"] == SOURCE_SHA
    assert durable["run_id"] == "exec-run-windows-901"
    assert durable["status"] == "SUCCESS"
    assert len(durable["artifacts"]) == 1
    assert durable["artifacts"][0]["path"] == "canary_output.txt"
    assert durable["artifacts"][0]["sha256"] == hashlib.sha256(artifact_file.read_bytes()).hexdigest()

    # 2. Persist to durable receipt file
    receipt_dir = tmp_path / "events" / "receipts"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    assert receipt_path.is_file()
    assert receipt_path.name.startswith("rcpt-")

    # 3. Read back and verify
    receipt = load_durable_receipt(receipt_path)
    assert receipt["task_id"] == durable["task_id"]
    assert receipt["workkey"] == WORKKEY
    assert receipt["attempt_id"] == durable["attempt_id"]
    assert receipt["dispatch_id"] == durable["dispatch_id"]
    assert receipt["worker_id"] == durable["worker_id"]
    assert receipt["source_sha"] == SOURCE_SHA
    assert receipt["status"] == "SUCCESS"
    assert receipt["artifacts"] == durable["artifacts"]
    assert receipt["schema_version"] == "2.0"


def test_failed_task_records_durable_receipt(tmp_path: Path):
    """Case 2: Failed task is durably recorded with failure status, preserved identity and empty artifacts."""
    task, _ = _make_task(tmp_path)
    workspace = tmp_path

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-fail-902",
        "status": "FAILED",
    }

    durable = verify_result(task, raw_result, workspace)
    assert durable["status"] == "FAILED"
    assert durable["artifacts"] == []
    assert durable["workkey"] == WORKKEY
    assert durable["source_sha"] == SOURCE_SHA

    receipt_dir = tmp_path / "events" / "receipts"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    loaded = load_durable_receipt(receipt_path)
    assert loaded["status"] == "FAILED"
    assert loaded["task_id"] == task["task_id"]
    assert loaded["worker_id"] == task["worker_id"]


def test_missing_or_invented_fields_fail_closed(tmp_path: Path):
    """Case 3: Missing result fields or invented unknown fields fail closed."""
    task, _ = _make_task(tmp_path)
    workspace = tmp_path

    # Sub-case 3a: Missing run_id (Ausführungs-ID)
    incomplete = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="observable run_id is required"):
        verify_result(task, incomplete, workspace)

    # Sub-case 3b: Unknown workkey invented on result when task had none
    task_no_workkey = dict(task)
    del task_no_workkey["workkey"]
    raw_with_invented_workkey = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": "INVENTED_KEY",
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-903",
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="workkey invented on result"):
        verify_result(task_no_workkey, raw_with_invented_workkey, workspace)

    # Sub-case 3c: Unknown source_sha invented on result when task had none
    task_no_sha = dict(task)
    del task_no_sha["source_sha"]
    raw_with_invented_sha = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": "a" * 40,
        "run_id": "run-904",
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="source_sha invented on result"):
        verify_result(task_no_sha, raw_with_invented_sha, workspace)

    # Sub-case 3d: Source SHA mismatch
    raw_divergent_sha = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": "0000000000000000000000000000000000000000",
        "run_id": "run-905",
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="source_sha mismatch"):
        verify_result(task, raw_divergent_sha, workspace)


def test_duplicate_result_idempotency_and_conflict_rejection(tmp_path: Path):
    """Case 4: Resending identical result succeeds idempotently; conflicting result raises ContractError."""
    task, _ = _make_task(tmp_path)
    workspace = tmp_path

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-dupe-906",
        "status": "SUCCESS",
    }
    durable = verify_result(task, raw_result, workspace)
    receipt_dir = tmp_path / "receipts"

    # First persistence
    path1 = persist_durable_receipt(task, durable, receipt_dir)
    assert path1.is_file()

    # Second identical persistence succeeds (ACK_DUPLICATE semantics)
    path2 = persist_durable_receipt(task, durable, receipt_dir)
    assert path1 == path2

    # Conflicting result for the same receipt identity must raise ContractError
    tampered_result = dict(durable)
    tampered_result["status"] = "FAILED"
    tampered_result["artifacts"] = []
    with pytest.raises(ContractError, match="Conflicting result for already processed task"):
        persist_durable_receipt(task, tampered_result, receipt_dir)


def test_restart_after_result_storage_in_fresh_process(tmp_path: Path):
    """Case 5: Prove durability by reading back the stored receipt in a completely fresh Python process."""
    task, _ = _make_task(tmp_path)
    workspace = tmp_path

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-fresh-process-907",
        "status": "SUCCESS",
    }
    durable = verify_result(task, raw_result, workspace)
    receipt_dir = tmp_path / "isolated_receipts"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    assert receipt_path.is_file()

    # Launch a completely fresh, isolated Python interpreter process
    verify_script = f"""
import sys, json
from pathlib import Path
from scripts.integration_contract import load_durable_receipt

receipt_file = Path(r"{receipt_path.as_posix()}")
data = load_durable_receipt(receipt_file)

assert data["task_id"] == "{task['task_id']}"
assert data["workkey"] == "{WORKKEY}"
assert data["attempt_id"] == "{task['attempt_id']}"
assert data["dispatch_id"] == "{task['dispatch_id']}"
assert data["worker_id"] == "WINDOWS-01"
assert data["source_sha"] == "{SOURCE_SHA}"
assert data["status"] == "SUCCESS"
assert data["schema_version"] == "2.0"
assert len(data["artifacts"]) == 1
print("FRESH_PROCESS_RECEIPT_VERIFIED_OK")
"""
    cmd = [sys.executable, "-c", verify_script]
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    assert "FRESH_PROCESS_RECEIPT_VERIFIED_OK" in result.stdout

    # Now simulate file tampering: modifying one field must break cryptographic verification in a fresh process
    content = json.loads(receipt_path.read_text(encoding="utf-8"))
    content["status"] = "FORGED_STATUS"
    receipt_path.write_text(json.dumps(content, indent=2), encoding="utf-8")

    tamper_script = f"""
import sys
from pathlib import Path
from scripts.integration_contract import load_durable_receipt, ContractError

receipt_file = Path(r"{receipt_path.as_posix()}")
try:
    load_durable_receipt(receipt_file)
    sys.exit(1) # Should not pass
except ContractError as e:
    if "receipt hash mismatch" in str(e):
        print("TAMPER_DETECTED_OK")
        sys.exit(0)
    sys.exit(2)
"""
    tamper_res = subprocess.run([sys.executable, "-c", tamper_script], cwd=str(repo_root), capture_output=True, text=True)
    assert tamper_res.returncode == 0
    assert "TAMPER_DETECTED_OK" in tamper_res.stdout
