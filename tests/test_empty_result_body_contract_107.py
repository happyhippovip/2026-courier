"""Deterministic tests for SEED 107 — LEEREN RESULTBODY VERTRAGLICH PRÜFEN.

Verifies:
1. Leerer Body (None / leerer Request):
   - /tasks/result mit empty body -> 400 Bad Request ("Empty or invalid result body").
2. Leeres JSON-Objekt ({}):
   - /tasks/result mit {} -> 400 Bad Request ("Empty or invalid result body").
3. Nicht-Objekt Payload (z. B. Array, String, Zahl, Null):
   - /tasks/result mit [1, 2, 3] oder "hello" -> 400 Bad Request.
4. Fehlende Pflichtfelder im Body (z. B. nur {"task_id": "t1"}):
   - /tasks/result wird mit 400 Bad Request abgewiesen (ContractError).
5. Gültiger, vollständiger Resultbody:
   - /tasks/result wird regulär angenommen (200 ACK_RESULT_RECEIVED).
6. Keine Zustandsmutation bei fehlerhaftem / leerem Body:
   - Task bleibt unverändert im DISPATCHED Status, keine Geisterergebnisse.
"""

import hashlib
import json
import pytest
from server import app as server_app

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
        yield client, state_file


def setup_dispatched_task(client):
    client.post(
        "/workers/register",
        headers=AUTH_HEADERS,
        json={"worker_id": "WORKER-107", "platform": "windows", "capabilities": ["windows"]},
    )
    client.post(
        "/goals",
        headers=AUTH_HEADERS,
        json={
            "goal_text": "goal-107",
            "workflow_plan": [
                {
                    "task_id": "task-seed-107",
                    "target_agent": "windows",
                    "instruction": "bounded task",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )
    claimed = client.post("/tasks/claim", headers=AUTH_HEADERS, json={"worker_id": "WORKER-107"}).get_json()["task"]
    assert claimed["status"] == "DISPATCHED"
    return claimed


def test_empty_result_body_rejected_400(env):
    """Case 1 & 2: Empty JSON payload or empty dict is strictly rejected with 400."""
    client, _ = env
    task = setup_dispatched_task(client)

    # 1. Empty body (no data sent)
    res_empty = client.post("/tasks/result", headers=AUTH_HEADERS, data="")
    assert res_empty.status_code == 400
    assert "Empty or invalid result body" in res_empty.get_json()["error"]

    # 2. Empty JSON dict ({})
    res_empty_dict = client.post("/tasks/result", headers=AUTH_HEADERS, json={})
    assert res_empty_dict.status_code == 400
    assert "Empty or invalid result body" in res_empty_dict.get_json()["error"]

    # Task remains intact in DISPATCHED state
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_non_dict_json_payload_rejected_400(env):
    """Case 3: Non-dict JSON (array, string, number) is rejected with 400."""
    client, _ = env
    task = setup_dispatched_task(client)

    # Array
    res_list = client.post("/tasks/result", headers=AUTH_HEADERS, json=["not", "a", "dict"])
    assert res_list.status_code == 400
    assert "Empty or invalid result body" in res_list.get_json()["error"]

    # Primitive string
    res_str = client.post("/tasks/result", headers=AUTH_HEADERS, json="raw string")
    assert res_str.status_code == 400
    assert "Empty or invalid result body" in res_str.get_json()["error"]

    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_incomplete_result_dict_fails_validation_400(env):
    """Case 4: Dict with missing required fields fails validation with 400."""
    client, _ = env
    task = setup_dispatched_task(client)

    incomplete = {
        "task_id": task["task_id"],
        "worker_id": "WORKER-107",
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
    }
    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=incomplete)
    assert res.status_code == 400
    assert "result is missing" in res.get_json()["error"]

    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"


def test_valid_complete_result_accepted_200(env):
    """Case 5: Well-formed complete result is accepted with 200 ACK_RESULT_RECEIVED."""
    client, _ = env
    task = setup_dispatched_task(client)

    valid_result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": "WORKER-107",
        "run_id": "run-ok-107",
        "result_id": "res-ok-107",
        "status": "SUCCESS",
        "source_sha": "0" * 40,
        "artifacts": [{"path": "out.txt", "sha256": hashlib.sha256(b"done").hexdigest()}],
    }

    res = client.post("/tasks/result", headers=AUTH_HEADERS, json=valid_result)
    assert res.status_code == 200
    assert res.get_json()["status"] == "ACK_RESULT_RECEIVED"

    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RESULT_RECEIVED"
