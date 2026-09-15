import hashlib

from server import app as server_app


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def setup_claimed_task(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    registered = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
    )
    assert registered.status_code == 200
    goal = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "one bounded task",
            "workflow_plan": [
                {
                    "task_id": "task-1",
                    "target_agent": "mac",
                    "instruction": "create bounded.txt",
                    "artifacts": ["bounded.txt"],
                }
            ],
        },
    ).get_json()
    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"})
    assert claimed.status_code == 200
    return http, goal["goal_id"], claimed.get_json()["task"]


def durable_result(task):
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "result_id": "result-1",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\n").hexdigest()}
        ],
    }


def test_insecure_default_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "dev-secret-key")
    response = server_app.app.test_client().post("/workers/register", json={"worker_id": "worker"})
    assert response.status_code == 503


def test_claim_returns_complete_common_identity(tmp_path, monkeypatch):
    _, _, task = setup_claimed_task(tmp_path, monkeypatch)
    for field in (
        "goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id",
        "run_id", "result_id", "status", "artifacts",
    ):
        assert field in task
    assert task["status"] == "DISPATCHED"
    assert task["worker_id"] == "MAC-01"


def test_worker_success_cannot_advance_goal_without_independent_verifier(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)

    received = http.post("/tasks/result", headers=auth(), json=result)

    assert received.status_code == 200
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RESULT_RECEIVED"
    assert state["goals"][goal_id]["current_step_index"] == 0
    assert state["goals"][goal_id]["status"] == "ACTIVE"


def test_wrong_attempt_result_fails_closed(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    result["attempt_id"] = "wrong-attempt"

    rejected = http.post("/tasks/result", headers=auth(), json=result)

    assert rejected.status_code == 400
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "DISPATCHED"
    assert state["goals"][goal_id]["current_step_index"] == 0


def test_only_independent_verification_advances_goal_exactly_once(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    verification = {
        "task_id": task["task_id"],
        "result_id": result["result_id"],
        "verifier_id": "VERIFIER-01",
        "verdict": "PASS",
        "artifacts": result["artifacts"],
    }

    self_certification = dict(verification, verifier_id=task["worker_id"])
    assert http.post("/tasks/verify", headers=auth(), json=self_certification).status_code == 400
    accepted = http.post("/tasks/verify", headers=auth(), json=verification)
    duplicate = http.post("/tasks/verify", headers=auth(), json=verification)

    assert accepted.status_code == 200
    assert duplicate.get_json()["status"] == "ACK_DUPLICATE"
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RECONCILED"
    assert state["goals"][goal_id]["current_step_index"] == 1
    assert state["goals"][goal_id]["status"] == "DONE"
