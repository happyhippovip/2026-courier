"""Dispatch-identity binding on result intake: a result carrying a dispatch_id
that does not match the task's current dispatch must be rejected (409),
while the matching dispatch is accepted. Guards against cross-dispatch
replay on a still-DISPATCHED task."""
import hashlib

from test_server_integration_contract import auth, setup_claimed_task


def _result(task, dispatch_id):
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": dispatch_id,
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "result_id": "result-1",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\n").hexdigest()}
        ],
    }


def test_result_with_wrong_dispatch_id_is_rejected(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    bad = _result(task, "dispatch-deadbeef")
    assert bad["dispatch_id"] != task["dispatch_id"]
    resp = http.post("/tasks/result", headers=auth(), json=bad)
    assert resp.status_code == 409
    assert "dispatch_id mismatch" in resp.get_json()["error"]


def test_result_with_matching_dispatch_id_is_accepted(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    resp = http.post("/tasks/result", headers=auth(), json=_result(task, task["dispatch_id"]))
    assert resp.status_code == 200


def test_result_missing_dispatch_id_fails_validation_not_conflict(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    bad = _result(task, task["dispatch_id"])
    del bad["dispatch_id"]
    resp = http.post("/tasks/result", headers=auth(), json=bad)
    assert resp.status_code == 400
    assert "missing" in resp.get_json()["error"]


def test_result_empty_dispatch_id_fails_validation_not_conflict(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    resp = http.post("/tasks/result", headers=auth(), json=_result(task, ""))
    assert resp.status_code == 400
