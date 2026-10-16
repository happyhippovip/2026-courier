"""Negative- und Sicherheitsregressionstests für Seed 030 / Catalog 0386: Result-ID-Eindeutigkeit sichern.

Phase 6: Negativ- und Sicherheitsregression.
Verifiziert striktes Fail-Closed-Verhalten gegen alle Formen von Result-ID-Manipulation,
Formatinvalidität, Identitätskonflikten und widersprüchlichen Quittungen:

Positivpfad:
- Valide, deterministisch abgeleitete Result-ID wird gebunden, verifiziert und atomar quittiert.
- Explizit mitgegebene result_id, die exakt mit dem deterministischen Hash übereinstimmt, wird akzeptiert.

Negativpfade (FAIL-CLOSED):
1. Gefälschte/abweichende result_id in raw_result -> ContractError("result_id mismatch")
2. Ungültiges result_id-Format (kein result- Präfix, ungültige Zeichen, zu kurz/lang) -> ContractError("invalid result_id format")
3. Identitätskollision: result_id entspricht run_id, dispatch_id, attempt_id, task_id, goal_id oder worker_id -> ContractError
4. Typinjektionen: int, bool, float, list, dict, leerer String -> ContractError
5. Widersprüchliches Resultat für identische Receipt-Identität in persist_durable_receipt -> ContractError("Conflicting result for already processed task")
6. Manipulierte Quittung auf Dateiebene scheitert an kryptografischer Hash-Prüfung -> ContractError("receipt hash mismatch")
"""
import hashlib
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
    _canonical_hash,
)

SOURCE_SHA = "fac447f5c9c22936177069566b82c7319bc35f5c"
WORKKEY = "WORKKEY-RESULT-ID-030"


def _setup_task(tmp_path: Path, **overrides) -> tuple[dict, Path]:
    artifact_name = "result_canary.txt"
    artifact_path = tmp_path / artifact_name
    artifact_path.write_text("result uniqueness proof canary\n", encoding="utf-8")

    base = {
        "task_id": "task-result-030",
        "goal_id": "goal-result-030",
        "target_capability": "windows",
        "workkey": WORKKEY,
        "source_sha": SOURCE_SHA,
        "artifacts": [artifact_name],
    }
    base.update(overrides)
    task = prepare_task(base)
    return task, artifact_path


def test_positive_canonical_result_id_verifies_and_persists(tmp_path: Path):
    """Positivfall: Deterministische Result-ID wird korrekt gebildet und persistiert."""
    task, artifact_file = _setup_task(tmp_path)
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-030",
        "status": "SUCCESS",
    }
    durable = verify_result(task, raw_result, tmp_path)
    assert durable["result_id"].startswith("result-")
    assert len(durable["result_id"]) == 71  # "result-" (7) + 64 hex chars

    receipt_dir = tmp_path / "receipts"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    assert receipt_path.is_file()

    loaded = load_durable_receipt(receipt_path)
    assert loaded["result_id"] == durable["result_id"]
    assert loaded["status"] == "SUCCESS"


def test_positive_matching_provided_result_id_accepted(tmp_path: Path):
    """Positivfall 2: raw_result liefert die exakt berechnete result_id mit -> akzeptiert."""
    task, artifact_file = _setup_task(tmp_path)
    # Compute matching identity
    art_sha = hashlib.sha256(artifact_file.read_bytes()).hexdigest()
    identity = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "exec-run-clean-030",
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": art_sha}],
        "workkey": task["workkey"],
        "source_sha": task["source_sha"],
    }
    matching_result_id = f"result-{_canonical_hash(identity)}"

    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-030",
        "result_id": matching_result_id,
        "status": "SUCCESS",
    }
    durable = verify_result(task, raw_result, tmp_path)
    assert durable["result_id"] == matching_result_id


def test_negative_forged_or_mismatched_result_id_fails_closed(tmp_path: Path):
    """Negativfall 1: Worker liefert eine abweichende oder gefälschte result_id in raw_result."""
    task, _ = _setup_task(tmp_path)
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-030",
        "result_id": "result-" + "f" * 64,  # Forged divergent result_id!
        "status": "SUCCESS",
    }
    with pytest.raises(ContractError, match="result_id mismatch"):
        verify_result(task, raw_result, tmp_path)


@pytest.mark.parametrize("bad_format", [
    "invalid-prefix-1234567890abcdef",  # Fehlendes result- Präfix
    "result-",                          # Leerer Suffix
    "result-foo?bar",                   # Ungültiges Sonderzeichen ?
    "result-foo#bar",                   # Ungültiges Sonderzeichen #
    "result-" + "a" * 129,              # Zu lang (> 128 Zeichen)
    "result-../../etc/passwd",          # Pfadtraversierungsversuch
    "result-12 34 56 78 90",            # Leerzeichen
])
def test_negative_invalid_result_id_format_fails_closed(tmp_path: Path, bad_format):
    """Negativfall 2: Ungültige Result-ID-Formate werden von validate_durable_result abgewiesen."""
    task, _ = _setup_task(tmp_path)
    durable = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-030",
        "result_id": bad_format,
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": "0" * 64}],
    }
    with pytest.raises(ContractError, match="invalid result_id format"):
        validate_durable_result(task, durable)


def test_negative_result_id_identity_conflation_fails_closed(tmp_path: Path):
    """Negativfall 3: result_id kollidiert mit einer anderen Entitäts-ID."""
    task, _ = _setup_task(tmp_path)
    base = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": "0" * 64}],
    }

    # 3a: result_id == run_id
    shared_id = "result-" + "a" * 16
    with pytest.raises(ContractError, match="result_id must not equal run_id"):
        validate_durable_result(task, dict(base, run_id=shared_id, result_id=shared_id))

    # 3b: result_id == dispatch_id
    task_dispatch = dict(task, dispatch_id="result-" + "b" * 16)
    with pytest.raises(ContractError, match="result_id must not equal dispatch_id"):
        validate_durable_result(task_dispatch, dict(base, dispatch_id=task_dispatch["dispatch_id"], run_id="exec-run-999", result_id=task_dispatch["dispatch_id"]))

    # 3c: result_id == attempt_id
    task_attempt = dict(task, attempt_id="result-" + "c" * 16)
    with pytest.raises(ContractError, match="result_id must not equal attempt_id"):
        validate_durable_result(task_attempt, dict(base, attempt_id=task_attempt["attempt_id"], run_id="exec-run-999", result_id=task_attempt["attempt_id"]))

    # 3d: result_id == task_id
    task_custom = dict(task, task_id="result-" + "d" * 16)
    with pytest.raises(ContractError, match="result_id must not equal task_id"):
        validate_durable_result(task_custom, dict(base, task_id=task_custom["task_id"], run_id="exec-run-999", result_id=task_custom["task_id"]))

    # 3e: result_id == goal_id
    task_goal = dict(task, goal_id="result-" + "e" * 16)
    with pytest.raises(ContractError, match="result_id must not equal goal_id"):
        validate_durable_result(task_goal, dict(base, goal_id=task_goal["goal_id"], run_id="exec-run-999", result_id=task_goal["goal_id"]))

    # 3f: result_id == worker_id
    task_worker = dict(task, worker_id="result-" + "f" * 16)
    with pytest.raises(ContractError, match="result_id must not equal worker_id"):
        validate_durable_result(task_worker, dict(base, worker_id=task_worker["worker_id"], run_id="exec-run-999", result_id=task_worker["worker_id"]))


@pytest.mark.parametrize("invalid_type", [
    12345,
    True,
    False,
    3.14,
    ["result-1234567890abcdef"],
    {"id": "result-1234567890abcdef"},
    "",
    None,
])
def test_negative_result_id_invalid_types_fail_closed(tmp_path: Path, invalid_type):
    """Negativfall 4: Nicht-String-Typen für result_id schlagen fail-closed fehl."""
    task, _ = _setup_task(tmp_path)
    durable = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-clean-030",
        "result_id": invalid_type,
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": "0" * 64}],
    }
    with pytest.raises(ContractError):
        validate_durable_result(task, durable)


def test_negative_persist_durable_receipt_conflicting_result_fails_closed(tmp_path: Path):
    """Negativfall 5: Widersprüchliches Resultat für identische Receipt-Identität wird abgewiesen."""
    task, _ = _setup_task(tmp_path)
    receipt_dir = tmp_path / "receipts"

    res1 = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-030",
        "result_id": "result-" + "1" * 64,
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": "0" * 64}],
    }
    p1 = persist_durable_receipt(task, res1, receipt_dir)
    assert p1.is_file()

    # Conflicting result asserting the same receipt identity but with FAILED status
    res2 = dict(res1, status="FAILED", artifacts=[])
    with pytest.raises(ContractError, match="Conflicting result for already processed task"):
        persist_durable_receipt(task, res2, receipt_dir)


def test_negative_tampered_receipt_file_hash_mismatch(tmp_path: Path):
    """Negativfall 6: Eine auf Plattenebene manipulierte Quittungsdatei scheitert an load_durable_receipt."""
    task, _ = _setup_task(tmp_path)
    receipt_dir = tmp_path / "receipts"

    res = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-030",
        "result_id": "result-" + "a" * 64,
        "status": "SUCCESS",
        "artifacts": [{"path": "result_canary.txt", "sha256": "0" * 64}],
    }
    receipt_path = persist_durable_receipt(task, res, receipt_dir)

    # Tamper with the file content without updating receipt_hash
    content = json.loads(receipt_path.read_text(encoding="utf-8"))
    content["result_id"] = "result-" + "b" * 64  # Tampered!
    receipt_path.write_text(json.dumps(content), encoding="utf-8")

    with pytest.raises(ContractError, match="receipt hash mismatch"):
        load_durable_receipt(receipt_path)


def test_persistence_and_cold_restart_with_verified_result_id(tmp_path: Path):
    """Phase 7: Beweist Persistenz, Kaltstart-Reload und Idempotenz von result_id über Prozessgrenzen."""
    task, artifact_path = _setup_task(tmp_path)
    raw_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "workkey": task["workkey"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "source_sha": task["source_sha"],
        "run_id": "exec-run-restart-030",
        "status": "SUCCESS",
    }
    # 1. Verifiziere und persistiere
    durable = verify_result(task, raw_result, tmp_path)
    receipt_dir = tmp_path / "receipts_030"
    receipt_path = persist_durable_receipt(task, durable, receipt_dir)
    assert receipt_path.is_file()

    # 2. Idempotenz: Zweiter identischer Schreibversuch liefert dieselbe Datei ohne Nebeneffekt
    re_written = persist_durable_receipt(task, durable, receipt_dir)
    assert re_written == receipt_path

    # 3. Kaltstart in einem frischen, isolierten Python-Prozess
    expected_result_id = durable["result_id"]
    reload_script = f"""
import sys, json
from pathlib import Path
from scripts.integration_contract import load_durable_receipt, validate_durable_result

receipt_file = Path(r"{receipt_path.as_posix()}")
loaded = load_durable_receipt(receipt_file)

# Exakte Identitätsübereinstimmung und result_id Erhaltung
assert loaded["task_id"] == "{task['task_id']}"
assert loaded["workkey"] == "{task['workkey']}"
assert loaded["attempt_id"] == "{task['attempt_id']}"
assert loaded["dispatch_id"] == "{task['dispatch_id']}"
assert loaded["worker_id"] == "{task['worker_id']}"
assert loaded["goal_id"] == "{task['goal_id']}"
assert loaded["run_id"] == "exec-run-restart-030"
assert loaded["status"] == "SUCCESS"
assert loaded["result_id"] == "{expected_result_id}"

# Disjunktionsprüfung: result_id ist disjunkt von allen anderen IDs
assert loaded["result_id"] != loaded["dispatch_id"]
assert loaded["result_id"] != loaded["attempt_id"]
assert loaded["result_id"] != loaded["task_id"]
assert loaded["result_id"] != loaded["goal_id"]
assert loaded["result_id"] != loaded["worker_id"]
assert loaded["result_id"] != loaded["run_id"]

task_ref = json.loads(r'''{json.dumps(task)}''')
validated = validate_durable_result(task_ref, loaded)
assert validated["result_id"] == "{expected_result_id}"
print("COLD_START_RESULT_ID_RELOAD_SUCCESSFUL")
"""
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run([sys.executable, "-c", reload_script], cwd=str(repo_root), capture_output=True, text=True)
    assert proc.returncode == 0, f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    assert "COLD_START_RESULT_ID_RELOAD_SUCCESSFUL" in proc.stdout

    # 4. Negativ-Simulation: Wenn eine persistierte Quittung so manipuliert wird,
    # dass result_id == run_id, wehrt der frische Prozess dies sofort fail-closed ab.
    corrupted_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    corrupted_data["run_id"] = "result-colliding-030"
    corrupted_data["result_id"] = "result-colliding-030"
    corrupted_path = tmp_path / "corrupted_receipt_result_id.json"
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
    assert "result_id must not equal run_id" in str(exc)
    print("TAMPERED_RESULT_ID_CORRECTLY_REJECTED")
"""
    proc_tamper = subprocess.run([sys.executable, "-c", tamper_script], cwd=str(repo_root), capture_output=True, text=True)
    assert proc_tamper.returncode == 0, f"STDOUT: {proc_tamper.stdout}\nSTDERR: {proc_tamper.stderr}"
    assert "TAMPERED_RESULT_ID_CORRECTLY_REJECTED" in proc_tamper.stdout


def test_server_state_restart_reconstruction_with_unique_result_id(tmp_path: Path, monkeypatch):
    """Beweist Server-State-Persistenz, Restart-Rekonstruktion und Idempotenz."""
    from server import app as server_app
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {
            "WINDOWS-01": {"current_task": "task-restart-030", "available": False, "last_seen": 1000.0}
        },
        "walls": {},
        "seq": 0,
    }
    task = {
        "goal_id": "goal-restart-030",
        "task_id": "task-restart-030",
        "attempt_id": "task-restart-030:attempt:1",
        "dispatch_id": "dispatch-restart-030",
        "worker_id": "WINDOWS-01",
        "status": "DISPATCHED",
        "artifacts": ["out_restart.txt"],
        "workkey": WORKKEY,
        "source_sha": SOURCE_SHA,
    }
    init_state["tasks"][task["task_id"]] = task
    init_state["goals"][task["goal_id"]] = {
        "status": "ACTIVE",
        "workflow_plan": [{"task_id": task["task_id"], "status": "DISPATCHED", "worker_id": "WINDOWS-01"}]
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")

    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret-030")

    auth_headers = {"Authorization": "Bearer test-secret-030"}

    with server_app.app.test_client() as client:
        # Erstelle valides Resultat
        art_hash = hashlib.sha256(b"restart-evidence").hexdigest()
        valid_res = {
            "goal_id": task["goal_id"],
            "task_id": task["task_id"],
            "attempt_id": task["attempt_id"],
            "dispatch_id": task["dispatch_id"],
            "worker_id": task["worker_id"],
            "workkey": task["workkey"],
            "source_sha": task["source_sha"],
            "run_id": "exec-run-server-restart",
            "result_id": "result-" + "e" * 64,
            "status": "SUCCESS",
            "artifacts": [{"path": "out_restart.txt", "sha256": art_hash}],
        }
        res_post = client.post("/tasks/result", headers=auth_headers, json=valid_res)
        assert res_post.status_code == 200
        assert res_post.get_json()["status"] == "ACK_RESULT_RECEIVED"

    # Simuliere Server-Neustart: Lade den Zustand frisch von der Festplatte
    reconstructed_state = json.loads(state_file.read_text(encoding="utf-8"))
    reconstructed_task = reconstructed_state["tasks"][task["task_id"]]
    assert reconstructed_task["status"] == "RESULT_RECEIVED"
    assert reconstructed_task["result"]["result_id"] == valid_res["result_id"]
    assert reconstructed_task["result"]["status"] == "SUCCESS"

    # Starte neue Client-Instanz gegen den rekonstruierten Zustand
    with server_app.app.test_client() as client2:
        # Idempotenter Replay nach Server-Restart
        res_dupe = client2.post("/tasks/result", headers=auth_headers, json=valid_res)
        assert res_dupe.status_code == 200
        assert res_dupe.get_json()["status"] == "ACK_DUPLICATE"

        # Conflicting result mit anderer result_id wird abgewiesen
        conflict_res = dict(valid_res, result_id="result-" + "f" * 64)
        res_conflict = client2.post("/tasks/result", headers=auth_headers, json=conflict_res)
        assert res_conflict.status_code == 409
        assert "Conflicting result for already processed task" in res_conflict.get_json()["error"]

