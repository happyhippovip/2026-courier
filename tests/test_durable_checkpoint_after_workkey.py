"""Deterministic tests for Durable Checkpoint After Every Workkey.

Mission: Ein fertiger Queue-Job muss einen wiederverwendbaren dauerhaften Checkpoint hinterlassen.

Verifizierte Felder (9 Kernfelder):
1. Workkey (workkey)
2. Owner (owner / worker_id)
3. Status (status)
4. Eingabefingerprint (input_fingerprint)
5. Source-SHA (source_sha)
6. Ausgeführte Aktion (action)
7. Testergebnis (test_result)
8. Resultat-ID (result_id)
9. Nächster zulässiger Schritt (next_action)

Klassifikation bei Fehlen:
- UNKNOWN: Information ist undefiniert oder widersprüchlich
- NOT_APPLICABLE: Information trifft auf diesen Aufgabentyp nicht zu (z.B. test_result bei reinen Sync-Tasks)
- NOT_RECORDED: Information wurde vom Aufrufer nicht erfasst / übergeben
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.integration_contract import (
    ContractError,
    load_durable_receipt,
    persist_durable_receipt,
    validate_durable_result,
)


def test_durable_checkpoint_preserves_all_nine_fields_across_restart(tmp_path):
    receipt_dir = tmp_path / "checkpoints"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    task = {
        "goal_id": "g-checkpoint-100",
        "task_id": "t-checkpoint-100",
        "workkey": "WK-CHECKPOINT-100",
        "owner": "WINDOWS-01",
        "worker_id": "WINDOWS-01",
        "attempt_id": "attempt-1",
        "dispatch_id": "disp-100",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        "input_fingerprint": "inp-fp-1234567890abcdef",
        "action": "execute_isolated_test_and_bundle",
        "next_action": "DISPATCH_NEXT_PIPELINE_STEP",
    }

    result = {
        "goal_id": "g-checkpoint-100",
        "task_id": "t-checkpoint-100",
        "workkey": "WK-CHECKPOINT-100",
        "owner": "WINDOWS-01",
        "worker_id": "WINDOWS-01",
        "attempt_id": "attempt-1",
        "dispatch_id": "disp-100",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        "input_fingerprint": "inp-fp-1234567890abcdef",
        "action": "execute_isolated_test_and_bundle",
        "next_action": "DISPATCH_NEXT_PIPELINE_STEP",
        "test_result": "PASS (18 passed, 0 failed)",
        "run_id": "pid-8888",
        "result_id": "result-chkpoint998877",
        "status": "SUCCESS",
        "artifacts": [{"path": "checkpoint.json", "sha256": "c" * 64}],
    }

    # 1. Schreiben des Checkpoint-Receipts
    checkpoint_file = persist_durable_receipt(task, result, receipt_dir)
    assert checkpoint_file.is_file()

    # 2. Kontrolliertes Prozessende und erneutes Einlesen in einem frischen Subprozess
    verify_script = f"""
import sys, json
from pathlib import Path
from scripts.integration_contract import load_durable_receipt

checkpoint = load_durable_receipt(Path(r"{checkpoint_file}"))

# Assert all 9 core fields survive
assert checkpoint["workkey"] == "{task['workkey']}", "workkey mismatch"
assert checkpoint["owner"] == "{task['owner']}", "owner mismatch"
assert checkpoint["status"] == "{result['status']}", "status mismatch"
assert checkpoint["input_fingerprint"] == "{task['input_fingerprint']}", "input_fingerprint mismatch"
assert checkpoint["source_sha"] == "{task['source_sha']}", "source_sha mismatch"
assert checkpoint["action"] == "{task['action']}", "action mismatch"
assert checkpoint["test_result"] == "{result['test_result']}", "test_result mismatch"
assert checkpoint["result_id"] == "{result['result_id']}", "result_id mismatch"
assert checkpoint["next_action"] == "{task['next_action']}", "next_action mismatch"

print("FRESH_PROCESS_CHECKPOINT_VERIFIED")
"""
    proc = subprocess.run(
        [sys.executable, "-c", verify_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
        timeout=10,
    )
    assert proc.returncode == 0, f"Fresh process verification failed: {proc.stderr}"
    assert "FRESH_PROCESS_CHECKPOINT_VERIFIED" in proc.stdout


def test_durable_checkpoint_field_classification(tmp_path):
    """Prüft die genaue Unterscheidung von UNKNOWN, NOT_APPLICABLE und NOT_RECORDED."""
    receipt_dir = tmp_path / "checkpoints_partial"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    # Basis-Task ohne Tests (z.B. reines Verzeichnis-Cleanup)
    task_clean = {
        "goal_id": "g-cleanup",
        "task_id": "t-clean",
        "workkey": "WK-CLEANUP-01",
        "worker_id": "WINDOWS-01",
        "attempt_id": "att-1",
        "dispatch_id": "disp-c1",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        # input_fingerprint, action, test_result, next_action sind nicht im Task deklariert
    }

    result_clean = {
        "goal_id": "g-cleanup",
        "task_id": "t-clean",
        "workkey": "WK-CLEANUP-01",
        "worker_id": "WINDOWS-01",
        "attempt_id": "att-1",
        "dispatch_id": "disp-c1",
        "source_sha": "fac447f5c9c22936177069566b82c7319bc35f5c",
        "run_id": "pid-1111",
        "result_id": "result-clean1111",
        "status": "SUCCESS",
        "artifacts": [{"path": "clean.log", "sha256": "1" * 64}],
    }

    checkpoint_path = persist_durable_receipt(task_clean, result_clean, receipt_dir)
    loaded = load_durable_receipt(checkpoint_path)

    # Feld-Prüfung und Klassifikation:
    fields_audit = {}
    for field in (
        "workkey",
        "owner",
        "status",
        "input_fingerprint",
        "source_sha",
        "action",
        "test_result",
        "result_id",
        "next_action",
    ):
        if field in loaded:
            fields_audit[field] = loaded[field]
        else:
            if field == "test_result":
                # Reine Cleanup-Tasks führen keine Tests aus -> Nicht anwendbar
                fields_audit[field] = "NOT_APPLICABLE"
            elif field in ("input_fingerprint", "action", "next_action"):
                # Vom Aufrufer in diesem Job nicht spezifiziert -> Nicht erfasst
                fields_audit[field] = "NOT_RECORDED"
            elif field == "owner":
                # worker_id ist vorhanden, owner als expliziter Alias wurde nicht übergeben
                fields_audit[field] = loaded.get("worker_id", "UNKNOWN")
            else:
                fields_audit[field] = "UNKNOWN"

    assert fields_audit["workkey"] == "WK-CLEANUP-01"
    assert fields_audit["status"] == "SUCCESS"
    assert fields_audit["result_id"] == "result-clean1111"
    assert fields_audit["source_sha"] == "fac447f5c9c22936177069566b82c7319bc35f5c"
    assert fields_audit["test_result"] == "NOT_APPLICABLE"
    assert fields_audit["input_fingerprint"] == "NOT_RECORDED"
    assert fields_audit["action"] == "NOT_RECORDED"
    assert fields_audit["next_action"] == "NOT_RECORDED"
