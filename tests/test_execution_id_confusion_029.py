"""Negative- und Sicherheitsregressionstests für Seed 029 / Catalog 0376: Execution-ID-Verwechslung abfangen.

Phase 6: Negativ- und Sicherheitsregression.
Verifiziert striktes Fail-Closed-Verhalten gegen alle Formen von Execution-ID-Verwechslungen,
ungültigen Typinjektionen und manipulierten Quittungen:

Positivpfad:
- Valider, disjunkter run_id wird akzeptiert und bildet deterministische Result-ID.

Negativpfade (FAIL-CLOSED):
1. Verwechslung run_id == dispatch_id -> ContractError("run_id must not equal dispatch_id")
2. Verwechslung run_id == attempt_id -> ContractError("run_id must not equal attempt_id")
3. Verwechslung run_id == task_id -> ContractError("run_id must not equal task_id")
4. Verwechslung run_id == goal_id -> ContractError("run_id must not equal goal_id")
5. Verwechslung run_id == worker_id -> ContractError("run_id must not equal worker_id")
6. Gebundener run_id im Task weicht vom Resultat ab -> ContractError("run_id mismatch")
7. Typinjektionen: int, bool, float, list, dict, leerer String -> ContractError
8. validate_durable_result wehrt Verwechslungen ebenfalls strikt ab
9. Manipulierte Quittungen (tampered receipt) mit verwechselter run_id scheitern an Re-Validierung
"""
import json
from pathlib import Path
import subprocess
import sys
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
WORKKEY = "WORKKEY-COURIER-EXEC-029"


def _setup_task(tmp_path: Path, **overrides) -> tuple[dict, Path]:
    artifact_name = "exec_canary.txt"
    artifact_path = tmp_path / artifact_name
    artifact_path.write_text("execution canary proof\n", encoding="utf-8")

    base = {
        "task_id": "task-exec-029",
        "goal_id": "goal-exec-029",
        "target_capability": "windows",
        "workkey": WORKKEY,
        "source_sha": SOURCE_SHA,
        "artifacts": [artifact_name],
    }
    base.update(overrides)
    task = prepare_task(base)
    return task, artifact_path


def test_positive_distinct_execution_id_verifies(tmp_path: Path):
    """Positivfall: Valider und disjunkter run_id wird erfolgreich gebunden und quittiert."""
    task, _ = _setup_task(tmp_path)
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-777",
        "status": "SUCCESS",
    }
    durable = verify_result(task, raw_result, tmp_path)
    assert durable["run_id"] == "exec-run-clean-777"
    assert durable["dispatch_id"] == task["dispatch_id"]
    assert durable["attempt_id"] == task["attempt_id"]
    assert durable["status"] == "SUCCESS"


def test_negative_run_id_confused_with_dispatch_id(tmp_path: Path):
    """Negativfall 1: run_id spiegelt dispatch_id wider."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": task["dispatch_id"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id must not equal dispatch_id"):
        verify_result(task, bad_result, tmp_path)


def test_negative_run_id_confused_with_attempt_id(tmp_path: Path):
    """Negativfall 2: run_id spiegelt attempt_id wider."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": task["attempt_id"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id must not equal attempt_id"):
        verify_result(task, bad_result, tmp_path)


def test_negative_run_id_confused_with_task_id(tmp_path: Path):
    """Negativfall 3: run_id spiegelt task_id wider."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": task["task_id"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id must not equal task_id"):
        verify_result(task, bad_result, tmp_path)


def test_negative_run_id_confused_with_goal_id(tmp_path: Path):
    """Negativfall 4: run_id spiegelt goal_id wider."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": task["goal_id"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id must not equal goal_id"):
        verify_result(task, bad_result, tmp_path)


def test_negative_run_id_confused_with_worker_id(tmp_path: Path):
    """Negativfall 5: run_id spiegelt worker_id wider."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": task["worker_id"],
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id must not equal worker_id"):
        verify_result(task, bad_result, tmp_path)


def test_negative_prebound_run_id_mismatch(tmp_path: Path):
    """Negativfall 6: Pre-bound task['run_id'] weicht von raw_result['run_id'] ab."""
    task, _ = _setup_task(tmp_path, run_id="exec-run-expected-999")
    divergent_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-divergent-888",
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="run_id mismatch"):
        verify_result(task, divergent_result, tmp_path)


@pytest.mark.parametrize("invalid_run_id", [
    "",
    None,
    12345,
    True,
    False,
    3.1415,
    ["exec-run-001"],
    {"run": "exec-001"},
])
def test_negative_invalid_run_id_types_fail_closed(tmp_path: Path, invalid_run_id):
    """Negativfall 7: Nicht-String-Typen und leere Werte für run_id schlagen fail-closed fehl."""
    task, _ = _setup_task(tmp_path)
    bad_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": invalid_run_id,
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="observable run_id is required"):
        verify_result(task, bad_result, tmp_path)


def test_negative_validate_durable_result_enforces_all_confusion_guards(tmp_path: Path):
    """Negativfall 8: validate_durable_result verifiziert ebenfalls alle 5 Verwechslungsfälle."""
    task, _ = _setup_task(tmp_path)
    base_durable = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "result_id": "result-abc12345",
        "status": "SUCCESS",
        "artifacts": [{"path": "exec_canary.txt", "sha256": "0" * 64}],
    }

    # 8a: dispatch_id confusion in validate_durable_result
    bad_dispatch = dict(base_durable, run_id=task["dispatch_id"])
    with pytest.raises(ContractError, match="run_id must not equal dispatch_id"):
        validate_durable_result(task, bad_dispatch)

    # 8b: attempt_id confusion in validate_durable_result
    bad_attempt = dict(base_durable, run_id=task["attempt_id"])
    with pytest.raises(ContractError, match="run_id must not equal attempt_id"):
        validate_durable_result(task, bad_attempt)

    # 8c: task_id confusion in validate_durable_result
    bad_task = dict(base_durable, run_id=task["task_id"])
    with pytest.raises(ContractError, match="run_id must not equal task_id"):
        validate_durable_result(task, bad_task)

    # 8d: goal_id confusion in validate_durable_result
    bad_goal = dict(base_durable, run_id=task["goal_id"])
    with pytest.raises(ContractError, match="run_id must not equal goal_id"):
        validate_durable_result(task, bad_goal)

    # 8e: worker_id confusion in validate_durable_result
    bad_worker = dict(base_durable, run_id=task["worker_id"])
    with pytest.raises(ContractError, match="run_id must not equal worker_id"):
        validate_durable_result(task, bad_worker)

    # 8f: bound run_id mismatch in validate_durable_result
    task_bound = dict(task, run_id="exec-run-expected-999")
    bad_mismatch = dict(base_durable, run_id="exec-run-divergent-888")
    with pytest.raises(ContractError, match="run_id mismatch"):
        validate_durable_result(task_bound, bad_mismatch)


def test_persistence_and_restart_with_verified_execution_id(tmp_path: Path):
    """Phase 7: Beweist Persistenz, Kaltstart-Reload und Idempotenz über Prozessgrenzen."""
    task, artifact_path = _setup_task(tmp_path)
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-durable-029",
        "status": "SUCCESS",
    }
    # 1. Verifiziere und persistiere
    durable = verify_result(task, raw_result, tmp_path)
    receipt_dir = tmp_path / "receipts_029"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    assert receipt_path.is_file()

    # 2. Idempotenz: Zweiter identischer Schreibversuch liefert dieselbe Datei (ACK_DUPLICATE)
    re_written = persist_durable_receipt(task, durable, receipt_dir)
    assert re_written == receipt_path

    # 3. Kaltstart in einem frischen, isolierten Python-Prozess
    reload_script = f"""
import sys, json
from pathlib import Path
from scripts.integration_contract import load_durable_receipt, validate_durable_result

receipt_file = Path(r"{receipt_path.as_posix()}")
loaded = load_durable_receipt(receipt_file)

# Exakte Identitätsübereinstimmung
assert loaded["task_id"] == "{task['task_id']}"
assert loaded["workkey"] == "{task['workkey']}"
assert loaded["attempt_id"] == "{task['attempt_id']}"
assert loaded["dispatch_id"] == "{task['dispatch_id']}"
assert loaded["worker_id"] == "{task['worker_id']}"
assert loaded["goal_id"] == "{task['goal_id']}"
assert loaded["run_id"] == "exec-run-durable-029"
assert loaded["status"] == "SUCCESS"

# Disjunktionsprüfung: run_id ist disjunkt von allen anderen IDs
assert loaded["run_id"] != loaded["dispatch_id"]
assert loaded["run_id"] != loaded["attempt_id"]
assert loaded["run_id"] != loaded["task_id"]
assert loaded["run_id"] != loaded["goal_id"]
assert loaded["run_id"] != loaded["worker_id"]

task_ref = json.loads(r'''{json.dumps(task)}''')
validated = validate_durable_result(task_ref, loaded)
assert validated["run_id"] == "exec-run-durable-029"
print("COLD_START_RELOAD_SUCCESSFUL")
"""
    cmd = [sys.executable, "-c", reload_script]
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
    assert proc.returncode == 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "COLD_START_RELOAD_SUCCESSFUL" in proc.stdout

    # 4. Negativ-Simulation: Wenn eine persistierte Quittung so manipuliert wird,
    # dass run_id == dispatch_id, wehrt der frische Prozess dies sofort fail-closed ab.
    corrupted_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    corrupted_data["run_id"] = corrupted_data["dispatch_id"]
    corrupted_path = tmp_path / "corrupted_receipt.json"
    corrupted_path.write_text(json.dumps(corrupted_data), encoding="utf-8")

    tamper_script = f"""
import sys, json
from pathlib import Path
from scripts.integration_contract import validate_durable_result, ContractError

corrupted_file = Path(r"{corrupted_path.as_posix()}")
data = json.loads(corrupted_file.read_text(encoding="utf-8"))
task_ref = json.loads(r'''{json.dumps(task)}''')

try:
    validate_durable_result(task_ref, data)
    sys.exit(1)
except ContractError as exc:
    assert "run_id must not equal dispatch_id" in str(exc)
    print("TAMPERED_RECEIPT_CORRECTLY_REJECTED")
"""
    proc_tamper = subprocess.run([sys.executable, "-c", tamper_script], cwd=str(repo_root), capture_output=True, text=True, check=True)
    assert "TAMPERED_RECEIPT_CORRECTLY_REJECTED" in proc_tamper.stdout

