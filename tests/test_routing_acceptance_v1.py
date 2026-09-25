import threading

import pytest

from server import app as server_app


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "empty-batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setattr(server_app, "calculate_backoff", lambda *_args, **_kwargs: 0.0)
    return server_app.app.test_client()


def register(http, worker_id, capabilities, *, platform="test"):
    response = http.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": worker_id,
            "platform": platform,
            "capabilities": capabilities,
            "authorities": [],
            "provider": "local",
            "capacity_identity": f"capacity-{worker_id}",
            "cost_class": "free",
        },
    )
    assert response.status_code == 200


def submit(http, tasks):
    response = http.post(
        "/goals",
        headers=auth(),
        json={"goal_text": "routing acceptance", "workflow_plan": tasks, "estimated_cost": 0.0},
    )
    assert response.status_code == 200
    return response.get_json()["goal_id"]


def task(task_id, **overrides):
    value = {
        "task_id": task_id,
        "target_agent": "auto",
        "instruction": f"execute {task_id}",
    }
    value.update(overrides)
    return value


def claim(http, worker_id):
    response = http.post("/tasks/claim", headers=auth(), json={"worker_id": worker_id})
    assert response.status_code == 200
    return response.get_json().get("task")


from server.app import SERVER_BINDING
from scripts.integration_contract import _canonical_hash

def result_for(claimed, worker_id, result_id, status, stderr=None):
    from server.app import SERVER_BINDING
    result = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": worker_id,
        "run_id": f"run-{result_id}",
        "status": status,
        "runtime_identity": SERVER_BINDING,
        "artifacts": [],
    }
    identity = dict(result)
    result["result_id"] = f"result-{_canonical_hash(identity)}"
    
    if stderr is not None:
        result["stderr"] = stderr
    return result


def test_capability_insufficient_cannot_claim(motor):
    register(motor, "INSUFFICIENT", ["read"])
    goal_id = submit(motor, [task("needs-write", required_capabilities=["write"])])

    observed = claim(motor, "INSUFFICIENT")
    state = server_app.load_state()
    queued = state["goals"][goal_id]["workflow_plan"][0]
    worker = state["workers"]["INSUFFICIENT"]

    assert observed is None
    assert queued["task_id"] == "needs-write"
    assert queued["status"] == "QUEUED"
    assert queued["attempts"] == 0
    assert worker["current_task"] is None
    assert worker["available"] is True
    assert "needs-write" not in state["tasks"]


def test_concurrent_independent_claims_get_distinct_ready_tasks(motor):
    register(motor, "W1", ["X"])
    register(motor, "W2", ["X"])
    submit(
        motor,
        [
            task("independent-a", required_capabilities=["X"]),
            task("independent-b", required_capabilities=["X"]),
        ],
    )

    barrier = threading.Barrier(2)
    observed = {}
    observed_lock = threading.Lock()

    def race(worker_id):
        http = server_app.app.test_client()
        barrier.wait()
        claimed = claim(http, worker_id)
        with observed_lock:
            observed[worker_id] = claimed

    threads = [threading.Thread(target=race, args=(worker_id,)) for worker_id in ("W1", "W2")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert set(observed) == {"W1", "W2"}
    assert all(claimed is not None for claimed in observed.values())
    assert {claimed["task_id"] for claimed in observed.values()} == {
        "independent-a",
        "independent-b",
    }
    assert {claimed["worker_id"] for claimed in observed.values()} == {"W1", "W2"}


def test_cross_worker_reexecution_can_move_mac_record_to_windows_record(motor):
    register(motor, "MAC", ["macos", "shared"], platform="macos")
    register(motor, "WINDOWS", ["windows", "shared"], platform="windows")
    submit(motor, [task("portable", required_capabilities=["shared"])])

    first = claim(motor, "MAC")
    assert first is not None
    assert first["worker_id"] == "MAC"
    first_attempt = first["attempt_id"]
    first_dispatch = first["dispatch_id"]

    response = motor.post(
        "/tasks/result",
        headers=auth(),
        json=result_for(
            first,
            "MAC",
            "result-mac-failed",
            "FAILED",
            stderr="deterministic pre-effect failure",
        ),
    )
    assert response.status_code == 200
    after_failure = server_app.load_state()["tasks"]["portable"]
    assert after_failure["status"] == "QUEUED"
    assert after_failure["worker_id"] is None

    second = claim(motor, "WINDOWS")
    assert second is not None
    assert second["task_id"] == "portable"
    assert second["worker_id"] == "WINDOWS"
    assert second["attempt_id"] == "portable:attempt:2"
    assert second["attempt_id"] != first_attempt
    assert second["dispatch_id"] != first_dispatch


def test_ambiguous_worker_loss_is_quarantined_not_taken_over(motor):
    register(motor, "MAC", ["macos", "shared"], platform="macos")
    register(motor, "WINDOWS", ["windows", "shared"], platform="windows")
    goal_id = submit(motor, [task("ambiguous", required_capabilities=["shared"])])

    first = claim(motor, "MAC")
    assert first is not None

    state = server_app.load_state()
    state["workers"]["MAC"]["last_seen"] = 0
    server_app.save_state(state)

    response = motor.post("/tasks/reclaim_stale", headers=auth())
    assert response.status_code == 200
    assert response.get_json()["reclaimed_tasks"] == 0
    assert response.get_json()["quarantined_tasks"] == 1

    state = server_app.load_state()
    assert state["tasks"]["ambiguous"]["status"] == "HUMAN_REQUIRED"
    assert state["goals"][goal_id]["status"] == "BLOCKED"
    assert state["workers"]["MAC"]["current_task"] is None
    assert claim(motor, "WINDOWS") is None


def test_reconciliation_exposes_next_ready_task_without_manual_state_edit(motor):
    register(motor, "W", ["X"])
    submit(
        motor,
        [
            task("first", required_capabilities=["X"]),
            task("second", required_capabilities=["X"]),
        ],
    )

    first = claim(motor, "W")
    assert first["task_id"] == "first"

    result_id = "result-first-success"
    res_payload = result_for(first, "W", result_id, "SUCCESS")
    received = motor.post(
        "/tasks/result",
        headers=auth(),
        json=res_payload,
    )
    assert received.status_code == 200

    verified = motor.post(
        "/tasks/verify",
        headers=verifier_auth(),
        json={
            "task_id": "first",
            "result_id": res_payload["result_id"],
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
            "received_runtime_identity": SERVER_BINDING,
        },
    )
    if verified.status_code != 200:
        print("VERIFY ERROR:", verified.get_data(as_text=True))
    assert verified.status_code == 200
    assert verified.get_json()["status"] == "RECONCILED"

    second = claim(motor, "W")
    assert second is not None
    assert second["task_id"] == "second"
    assert second["attempt_id"] == "second:attempt:1"
