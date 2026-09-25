"""Server-side failure/recovery matrix (real server app, temp state)."""
import json

import pytest

from test_server_integration_contract import auth, client, durable_result, setup_claimed_task, verifier_auth
from server import app as server_app


def test_duplicate_result_is_acknowledged_without_state_change(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    before = server_app.load_state()["tasks"][task["task_id"]]
    again = http.post("/tasks/result", headers=auth(), json=result)
    assert again.status_code == 200
    assert server_app.load_state()["tasks"][task["task_id"]] == before


def test_conflicting_second_result_cannot_replace_first(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    first = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=first).status_code == 200
    conflicting = dict(first, result_id="result-2", status="FAILED", artifacts=[])
    http.post("/tasks/result", headers=auth(), json=conflicting)
    stored = server_app.load_state()["tasks"][task["task_id"]]
    assert stored["result"]["result_id"] == "result-1"
    assert stored["status"] == "RESULT_RECEIVED"


def test_result_from_another_worker_is_rejected(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    http.post("/workers/register", headers=auth(), json={"worker_id": "OTHER", "capabilities": ["macos"]})
    forged = dict(durable_result(task), worker_id="OTHER")
    assert http.post("/tasks/result", headers=auth(), json=forged).status_code == 400
    assert server_app.load_state()["tasks"][task["task_id"]]["status"] == "DISPATCHED"


@pytest.mark.parametrize("field", ["goal_id", "attempt_id", "dispatch_id"])
def test_result_with_wrong_identity_is_rejected(tmp_path, monkeypatch, field):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    wrong = dict(durable_result(task), **{field: "wrong"})
    assert http.post("/tasks/result", headers=auth(), json=wrong).status_code == 400
    assert server_app.load_state()["tasks"][task["task_id"]]["status"] == "DISPATCHED"


@pytest.mark.parametrize("endpoint", ["/workers/register", "/workers/heartbeat", "/tasks/claim", "/tasks/result"])
@pytest.mark.parametrize("header", [None, "Bearer wrong-key", "Bearer ", "Bearer verifier-secret"])
def test_worker_endpoints_reject_missing_or_invalid_credentials(tmp_path, monkeypatch, endpoint, header):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    before = json.dumps(server_app.load_state(), sort_keys=True)
    headers = {"Authorization": header} if header is not None else {}
    body = durable_result(task) if endpoint == "/tasks/result" else {"worker_id": "MAC-01"}
    r = http.post(endpoint, headers=headers, json=body)
    assert r.status_code in (401, 403)
    after = json.loads(json.dumps(server_app.load_state(), sort_keys=True))
    after_workers = {k: {kk: vv for kk, vv in v.items() if kk != "last_seen"} for k, v in after["workers"].items()}
    before_state = json.loads(before)
    before_workers = {k: {kk: vv for kk, vv in v.items() if kk != "last_seen"} for k, v in before_state["workers"].items()}
    assert after_workers == before_workers and after["tasks"] == before_state["tasks"]


def test_worker_key_cannot_verify(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    http.post("/tasks/result", headers=auth(), json=result)
    r = http.post("/tasks/verify", headers=auth(), json={
        "task_id": task["task_id"], "result_id": "result-1", "verifier_id": "VERIFIER-01",
        "verdict": "PASS", "artifacts": result["artifacts"]})
    assert r.status_code in (401, 403)
    assert server_app.load_state()["tasks"][task["task_id"]]["status"] == "RESULT_RECEIVED"


def test_server_restart_keeps_dispatch_identity_and_accepts_bound_result(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    # "Restart": a fresh client over the same durable state file.
    http2 = client(tmp_path, monkeypatch)
    stored = server_app.load_state()["tasks"][task["task_id"]]
    for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
        assert stored[field] == task[field]
    assert http2.post("/tasks/result", headers=auth(), json=durable_result(task)).status_code == 200


def test_success_with_missing_artifact_evidence_is_rejected(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    no_evidence = dict(durable_result(task), artifacts=[])
    assert http.post("/tasks/result", headers=auth(), json=no_evidence).status_code == 400


def test_unregister_then_reregister_without_task_quarantines_instead_of_replaying(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    assert http.post("/workers/unregister", headers=auth(), json={"worker_id": "MAC-01"}).status_code == 200
    http.post("/workers/register", headers=auth(),
              json={"worker_id": "MAC-01", "capabilities": ["macos"], "current_task": None})
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "HUMAN_REQUIRED"
    assert state["goals"][goal_id]["status"] == "BLOCKED"
    assert http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"] is None
