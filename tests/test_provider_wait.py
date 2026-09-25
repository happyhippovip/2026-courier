import pytest

from server import app as server_app


def auth():
    return {"Authorization": "Bearer test-secret"}


@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "empty-batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def register(http, worker_id):
    response = http.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": worker_id,
            "platform": "test",
            "capabilities": ["test"],
            "provider": "local",
            "capacity_identity": worker_id,
            "cost_class": "free",
        },
    )
    assert response.status_code == 200


def submit(http, tasks):
    response = http.post(
        "/goals",
        headers=auth(),
        json={"goal_text": "provider wait regression", "workflow_plan": tasks, "estimated_cost": 0.0},
    )
    assert response.status_code == 200
    return response.get_json()["goal_id"]


def claim(http, worker_id):
    response = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": worker_id}
    )
    assert response.status_code == 200
    return response.get_json().get("task")


def test_provider_wait_resumes_same_dispatch_without_new_attempt(motor):
    register(motor, "worker-1")
    submit(
        motor,
        [
            {
                "task_id": "waiting-task",
                "target_agent": "auto",
                "instruction": "wait once",
                "required_capabilities": ["test"],
            }
        ],
    )
    original = claim(motor, "worker-1")

    response = motor.post(
        "/tasks/waiting-task/provider_wait",
        headers=auth(),
        json={"worker_id": "worker-1", "reason": "quota"},
    )
    assert response.status_code == 200
    waiting = server_app.load_state()["tasks"]["waiting-task"]
    assert waiting["status"] == "WAITING_PROVIDER"
    assert waiting["attempt_id"] == original["attempt_id"]
    assert waiting["dispatch_id"] == original["dispatch_id"]
    assert waiting["execution_ref"] == original["execution_ref"]

    state = server_app.load_state()
    state["tasks"]["waiting-task"]["next_retry_at"] = 0
    for step in state["goals"][original["goal_id"]]["workflow_plan"]:
        if step["task_id"] == "waiting-task":
            step["next_retry_at"] = 0
    # DLQ-05: auto-resume is gated by the cluster provider lock, not the
    # per-task timestamp — expire the lock to simulate elapsed backoff.
    state["provider_locks"] = {}
    server_app.save_state(state)

    resumed = claim(motor, "worker-1")
    assert resumed["task_id"] == "waiting-task"
    assert resumed["attempt_id"] == original["attempt_id"]
    assert resumed["dispatch_id"] == original["dispatch_id"]
    assert resumed["execution_ref"] == original["execution_ref"]


def test_provider_wait_resume_uses_canonical_status_setter(motor, monkeypatch):
    """Auto-resume WAITING_PROVIDER->DISPATCHED must go through
    set_task_status (validation + ledger audit), never direct assignment."""
    calls = []
    real_setter = server_app.set_task_status

    def recording(task, new_status):
        calls.append((task.get("task_id"), new_status))
        return real_setter(task, new_status)

    monkeypatch.setattr(server_app, "set_task_status", recording)
    register(motor, "worker-1")
    submit(
        motor,
        [
            {
                "task_id": "resume-audit-task",
                "target_agent": "auto",
                "instruction": "wait once",
                "required_capabilities": ["test"],
            }
        ],
    )
    claim(motor, "worker-1")
    response = motor.post(
        "/tasks/resume-audit-task/provider_wait",
        headers=auth(),
        json={"worker_id": "worker-1", "reason": "quota"},
    )
    assert response.status_code == 200

    state = server_app.load_state()
    state["tasks"]["resume-audit-task"]["next_retry_at"] = 0
    state["provider_locks"] = {}
    server_app.save_state(state)
    calls.clear()

    resumed = claim(motor, "worker-1")
    assert resumed["task_id"] == "resume-audit-task"
    assert ("resume-audit-task", "DISPATCHED") in calls


def test_provider_wait_does_not_hide_unrelated_ready_work(motor):
    register(motor, "worker-1")
    register(motor, "worker-2")
    submit(
        motor,
        [
            {
                "task_id": "waiting-task",
                "target_agent": "auto",
                "instruction": "wait",
                "required_capabilities": ["test"],
            },
            {
                "task_id": "ready-task",
                "target_agent": "auto",
                "instruction": "continue independently",
                "required_capabilities": ["test"],
            },
        ],
    )
    waiting = claim(motor, "worker-1")
    response = motor.post(
        f"/tasks/{waiting['task_id']}/provider_wait",
        headers=auth(),
        json={"worker_id": "worker-1", "reason": "quota"},
    )
    assert response.status_code == 200

    independent = claim(motor, "worker-2")
    assert independent["task_id"] == "ready-task"
    assert server_app.load_state()["tasks"]["waiting-task"]["status"] == "WAITING_PROVIDER"


def test_provider_wait_rejects_wrong_worker_without_mutating_dispatch(motor):
    register(motor, "owner")
    register(motor, "other")
    submit(
        motor,
        [
            {
                "task_id": "owned-task",
                "target_agent": "auto",
                "instruction": "owned work",
                "required_capabilities": ["test"],
            }
        ],
    )
    original = claim(motor, "owner")

    response = motor.post(
        "/tasks/owned-task/provider_wait",
        headers=auth(),
        json={"worker_id": "other", "reason": "not my task"},
    )
    assert response.status_code == 403

    current = server_app.load_state()["tasks"]["owned-task"]
    assert current["status"] == "DISPATCHED"
    assert current["worker_id"] == "owner"
    assert current["attempt_id"] == original["attempt_id"]
    assert current["dispatch_id"] == original["dispatch_id"]
