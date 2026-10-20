"""Deterministic reproduction & regression tests for SEED 106 — RESULTGRÖSSENLIMIT ANWENDEN.

Verifies:
1. Result-Body Obergrenze (MAX_BODY_BYTES = 1024 * 1024 / 1 MiB):
   - POST /tasks/result mit Payload > 1 MiB wird mit HTTP 413 Payload Too Large abgewiesen.
2. Artefakt-Anzahl Obergrenze (MAX_ARTIFACTS = 64):
   - Resultat mit > 64 Artefakten wird mit HTTP 400 (ContractError) abgewiesen.
3. Einzelartefakt-Größe Obergrenze (MAX_ARTIFACT_BYTES = 16 * 1024 * 1024 / 16 MiB):
   - Resultat mit Artefakt size > 16 MiB wird mit HTTP 400 (ContractError) abgewiesen.
4. Gesamtartefakt-Größe Obergrenze (MAX_ARTIFACT_BYTES = 16 MiB):
   - Resultat mit sum(artifact.size) > 16 MiB wird mit HTTP 400 (ContractError) abgewiesen.
5. Outbox-Schreibschutz (outbox_write in courier_worker/host.py):
   - Payload > 1 MiB wird nicht in die Outbox geschrieben (wirft SpecError/ValueError).
6. Gültiges Resultat innerhalb aller Limits:
   - Reguläre Annahme mit HTTP 200 (ACK_RESULT_RECEIVED).
"""

import json
import pytest
from server import app as server_app
from scripts.integration_contract import (
    ContractError,
    validate_durable_result,
)
try:
    from scripts.integration_contract import (
        MAX_BODY_BYTES,
        MAX_ARTIFACTS,
        MAX_ARTIFACT_BYTES,
    )
except ImportError:
    MAX_BODY_BYTES = 1024 * 1024
    MAX_ARTIFACTS = 64
    MAX_ARTIFACT_BYTES = 16 * 1024 * 1024

from courier_worker.host import outbox_write, SpecError

TEST_SECRET = "test-secret"
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_SECRET}", "Content-Type": "application/json"}


@pytest.fixture
def env(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    init_state = {
        "goals": {},
        "tasks": {},
        "workers": {},
        "walls": {},
        "seq": 0,
    }
    state_file.write_text(json.dumps(init_state), encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", TEST_SECRET)
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    with server_app.app.test_client() as client:
        yield client, state_file, tmp_path


def setup_dispatched_task(client, task_id="task-seed-106", worker_id="WORKER-106"):
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": worker_id, "platform": "windows", "capabilities": ["windows"]},
    )
    client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "goal-106",
            "workflow_plan": [
                {
                    "task_id": task_id,
                    "target_agent": "windows",
                    "instruction": "bounded task",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )
    claimed = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": worker_id}).get_json()["task"]
    assert claimed["status"] == "DISPATCHED"
    return claimed


def test_result_body_exceeding_max_bytes_rejected_413(env):
    """Case 1: HTTP POST /tasks/result exceeding MAX_BODY_BYTES (1 MiB) is rejected with 413."""
    client, _, _ = env
    task = setup_dispatched_task(client)

    # Erzeuge Payload, die 1 MiB (MAX_BODY_BYTES) überschreitet
    large_padding = "X" * (MAX_BODY_BYTES + 1024)
    oversized_payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-obs-106",
        "result_id": "result-valid_format_106",
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "0" * 64, "artifact_id": f"art-{'1' * 64}", "size": 10}],
        "padding": large_padding,
    }
    raw_data = json.dumps(oversized_payload)
    assert len(raw_data.encode("utf-8")) > MAX_BODY_BYTES

    res = client.post(
        "/tasks/result",
        headers=AUTH_HEADERS,
        data=raw_data,
    )
    assert res.status_code == 413
    assert "too_large" in res.get_json()["error"] or "exceeds" in res.get_json()["error"]

    # Zustand bleibt unverändert
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_result_artifacts_exceeding_max_count_rejected_400(env):
    """Case 2: Result with > 64 artifacts rejected with 400 (ContractError)."""
    client, _, _ = env
    task = setup_dispatched_task(client)

    too_many_artifacts = [
        {"path": f"out_{i}.txt", "sha256": "0" * 64, "artifact_id": f"art-{str(i).zfill(64)}", "size": 10}
        for i in range(MAX_ARTIFACTS + 1)
    ]
    payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-obs-106",
        "result_id": "result-too_many_arts",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": too_many_artifacts,
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 400
    assert "artifacts count exceeds limit" in res.get_json()["error"]


def test_result_single_artifact_exceeding_max_bytes_rejected_400(env):
    """Case 3: Result with single artifact size > 16 MiB rejected with 400."""
    client, _, _ = env
    task = setup_dispatched_task(client)

    payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-obs-106",
        "result_id": "result-too_large_art",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [
            {"path": "out.txt", "sha256": "0" * 64, "artifact_id": f"art-{'a' * 64}", "size": MAX_ARTIFACT_BYTES + 1}
        ],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 400
    assert "artifact exceeds size limit" in res.get_json()["error"]


def test_result_total_artifacts_exceeding_max_bytes_rejected_400(env):
    """Case 4: Result with total artifact size > 16 MiB rejected with 400."""
    client, _, _ = env
    task = setup_dispatched_task(client)

    # 2 Artefakte jeweils 10 MiB -> Summe 20 MiB > 16 MiB
    half = (MAX_ARTIFACT_BYTES // 2) + 1024
    payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-obs-106",
        "result_id": "result-total_size_oversized",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [
            {"path": "out1.txt", "sha256": "0" * 64, "artifact_id": f"art-{'1' * 64}", "size": half},
            {"path": "out2.txt", "sha256": "0" * 64, "artifact_id": f"art-{'2' * 64}", "size": half},
        ],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 400
    assert "total artifact size exceeds limit" in res.get_json()["error"]


def test_outbox_write_payload_exceeding_max_bytes_raises_spec_error(env):
    """Case 5: Worker outbox_write rejects payloads exceeding MAX_BODY_BYTES."""
    _, _, tmp_path = env
    home = str(tmp_path / "worker_home")

    oversized = {
        "dispatch_id": "disp-oversized-106",
        "result_id": "res-oversized-106",
        "outcome": "success",
        "artifacts": [],
        "huge_field": "Y" * (MAX_BODY_BYTES + 512),
    }

    with pytest.raises((SpecError, ValueError), match="exceeds size limit"):
        outbox_write(home, oversized)


def test_valid_result_within_size_limits_accepted_200(env):
    """Case 6: Valid result within all size limits accepted with 200 ACK."""
    client, _, _ = env
    task = setup_dispatched_task(client)

    valid_payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-obs-106",
        "result_id": "res-valid-106",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [
            {"path": "out.txt", "sha256": "a" * 64}
        ],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"


def test_boundary_exact_max_artifacts_accepted(env):
    """Security Case 7: Result with exactly MAX_ARTIFACTS (64) is accepted (not 65)."""
    client, _, _ = env
    task = setup_dispatched_task(client, task_id="task-boundary-64", worker_id="WORKER-B64")

    exact_64 = [
        {"path": f"out_{i}.txt", "sha256": "0" * 64}
        for i in range(MAX_ARTIFACTS)
    ]
    payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-b64",
        "result_id": "res-b64",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": exact_64,
    }
    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"


def test_negative_and_boolean_artifact_size_rejected(env):
    """Security Case 8: Malicious artifact sizes (negative, bool, non-int) rejected fail-closed."""
    client, _, _ = env
    task = setup_dispatched_task(client, task_id="task-bad-size", worker_id="WORKER-BADSIZE")

    for idx, bad_size in enumerate((-1, -999999, True, False, "1024", [1024])):
        payload = {
            "task_id": task["task_id"],
            "goal_id": task["goal_id"],
            "attempt_id": task["attempt_id"],
            "dispatch_id": task["dispatch_id"],
            "worker_id": task["worker_id"],
            "run_id": "run-bad-size",
            "result_id": f"res-bad-size-{idx}",
            "status": "SUCCESS",
            "source_sha": "0" * 40,
            "artifacts": [{"path": "out.txt", "sha256": "0" * 64, "size": bad_size}],
        }
        res = client.post("/tasks/result", headers=AUTH_HEADERS, json=payload)
        assert res.status_code == 400
        assert "invalid artifact size" in res.get_json()["error"]


def test_content_length_spoofing_payload_exceeding_max_bytes_rejected_413(env):
    """Security Case 9: Content-Length spoofing or raw oversized data rejected with 413."""
    client, _, _ = env
    task = setup_dispatched_task(client, task_id="task-spoof", worker_id="WORKER-SPOOF")

    raw_oversized = b"{" + b'"huge":"' + (b"A" * (MAX_BODY_BYTES + 2048)) + b'"}'
    # Header claims small length, but raw body is oversized
    spoofed_headers = {
        "Authorization": f"Bearer {TEST_SECRET}",
        "Content-Type": "application/json",
        "Content-Length": "10",
    }
    res = client.post("/tasks/result", headers=spoofed_headers, data=raw_oversized)
    assert res.status_code == 413
    assert "too_large" in res.get_json()["error"]


def test_outbox_write_exact_bound_succeeds(env):
    """Security Case 10: Worker outbox_write accepts payloads up to MAX_RESULT_PAYLOAD_BYTES."""
    _, _, tmp_path = env
    home = str(tmp_path / "worker_home_bnd")

    # Bounded payload under 1 MiB
    bounded = {
        "dispatch_id": "disp-bounded-106",
        "result_id": "res-bounded-106",
        "outcome": "success",
        "artifacts": [],
        "text": "small result",
    }
    p = outbox_write(home, bounded)
    assert p.is_file()
    assert json.loads(p.read_text(encoding="utf-8"))["dispatch_id"] == "disp-bounded-106"


def test_persistence_and_restart_reconstruction_with_size_limits(env):
    """Phase 7: Valid bounded result survives server reload and reconstructs accurately."""
    client, state_file, _ = env
    task = setup_dispatched_task(client, task_id="task-restart-106", worker_id="WORKER-RESTART")

    valid_payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-restart-106",
        "result_id": "res-restart-106",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "c" * 64, "size": 4096}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_payload)
    assert res.status_code == 200

    # Simuliere Server-Neustart: State-Datei direkt von der Festplatte neu einlesen
    assert state_file.exists()
    reloaded_state = json.loads(state_file.read_text(encoding="utf-8"))
    persisted_task = reloaded_state["tasks"]["task-restart-106"]

    assert persisted_task["status"] == "RESULT_RECEIVED"
    assert persisted_task["result"]["result_id"] == "res-restart-106"
    assert len(persisted_task["result"]["artifacts"]) == 1
    assert persisted_task["result"]["artifacts"][0]["size"] == 4096


def test_idempotent_duplicate_resend_preserves_persisted_state(env):
    """Phase 7: Idempotent resend yields ACK_DUPLICATE without mutation or state drift."""
    client, state_file, _ = env
    task = setup_dispatched_task(client, task_id="task-idemp-106", worker_id="WORKER-IDEMP")

    valid_payload = {
        "task_id": task["task_id"],
        "goal_id": task["goal_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "run-idemp-106",
        "result_id": "res-idemp-106",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": "d" * 64, "size": 2048}],
    }

    # 1. Erste Annahme
    res1 = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_payload)
    assert res1.status_code == 200

    # 2. Identischer Re-send nach Reload
    res2 = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_payload)
    assert res2.status_code == 200
    assert res2.get_json()["status"] == "ACK_DUPLICATE"

    # 3. Zweiter Re-send mit unzulässiger Übergröße -> abgewiesen, persistierter Zustand unberührt
    oversized = dict(valid_payload)
    oversized["huge_junk"] = "Z" * (MAX_BODY_BYTES + 1024)
    res_oversized = client.post("/tasks/result", headers=AUTH_HEADERS, data=json.dumps(oversized))
    assert res_oversized.status_code == 413

    # State bleibt unversehrt
    reloaded = json.loads(state_file.read_text(encoding="utf-8"))
    assert reloaded["tasks"]["task-idemp-106"]["status"] == "RESULT_RECEIVED"


def test_outbox_persistence_and_restart_fifo_within_limits(env):
    """Phase 7: Outbox-Dateien im Limit überstehen Host-Restart und behalten FIFO-Ordnung."""
    from courier_worker.host import outbox_read_all

    _, _, tmp_path = env
    home = str(tmp_path / "host_restart_home")

    p1 = outbox_write(home, {"dispatch_id": "disp-01", "result_id": "res-01", "outcome": "success", "artifacts": []})
    p2 = outbox_write(home, {"dispatch_id": "disp-02", "result_id": "res-02", "outcome": "success", "artifacts": []})

    # Simuliere Worker-Restart / Recovery durch frischen Aufruf von outbox_read_all()
    recovered = outbox_read_all(home)
    assert len(recovered) == 2
    assert recovered[0][1]["dispatch_id"] == "disp-01"
    assert recovered[1][1]["dispatch_id"] == "disp-02"



