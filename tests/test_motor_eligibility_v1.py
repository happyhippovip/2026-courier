import threading

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


def register(
    http,
    worker_id,
    capabilities,
    authorities=None,
    provider="local",
    capacity_identity="capacity-1",
):
    response = http.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": worker_id,
            "platform": "test",
            "capabilities": capabilities,
            "authorities": authorities or [],
            "provider": provider,
            "capacity_identity": capacity_identity,
            "cost_class": "free",
        },
    )
    assert response.status_code == 200


def submit(http, tasks):
    response = http.post(
        "/goals",
        headers=auth(),
        json={"goal_text": "eligibility test", "workflow_plan": tasks},
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


def test_required_capabilities_all_satisfied_is_eligible(motor):
    register(motor, "W", ["X", "Y"])
    submit(motor, [task("xy", required_capabilities=["X", "Y"])])

    assert claim(motor, "W")["task_id"] == "xy"


def test_missing_required_capability_is_not_eligible(motor):
    register(motor, "W", ["X"])
    submit(motor, [task("xy", required_capabilities=["X", "Y"])])

    assert claim(motor, "W") is None


def test_unknown_capability_safely_remains_unclaimed(motor):
    register(motor, "W", ["X"])
    submit(motor, [task("unknown", required_capabilities=["brand-new-capability"])])

    assert claim(motor, "W") is None
    assert server_app.load_state()["goals"]


def test_missing_required_authority_is_not_eligible(motor):
    register(motor, "W", ["X"], authorities=[])
    submit(
        motor,
        [task("authority", required_capabilities=["X"], required_authorities=["repo:write"])],
    )

    assert claim(motor, "W") is None


def test_authorized_worker_is_eligible(motor):
    register(motor, "W", ["X"], authorities=["repo:write"])
    submit(
        motor,
        [task("authority", required_capabilities=["X"], required_authorities=["repo:write"])],
    )

    assert claim(motor, "W")["task_id"] == "authority"


def test_same_exclusive_resource_is_never_concurrently_claimed(motor):
    register(motor, "W1", ["X"])
    register(motor, "W2", ["X"])
    submit(
        motor,
        [
            task("r1", required_capabilities=["X"], exclusive_resources=["R"]),
            task("r2", required_capabilities=["X"], exclusive_resources=["R"]),
        ],
    )

    first = claim(motor, "W1")
    second = claim(motor, "W2")

    assert first["task_id"] == "r1"
    assert second is None
    assert server_app.load_state()["resource_owners"]["R"]["task_id"] == "r1"


def test_unrelated_exclusive_resources_proceed_independently(motor):
    register(motor, "W1", ["X"])
    register(motor, "W2", ["X"])
    submit(
        motor,
        [
            task("r", required_capabilities=["X"], exclusive_resources=["R"]),
            task("s", required_capabilities=["X"], exclusive_resources=["S"]),
        ],
    )

    assert claim(motor, "W1")["task_id"] == "r"
    assert claim(motor, "W2")["task_id"] == "s"


def test_incompatible_first_ready_does_not_hide_later_compatible(motor):
    register(motor, "W", ["Y"])
    submit(
        motor,
        [
            task("needs-x", required_capabilities=["X"]),
            task("needs-y", required_capabilities=["Y"]),
        ],
    )

    assert claim(motor, "W")["task_id"] == "needs-y"


def test_waiting_provider_does_not_hide_unrelated_ready_work(motor):
    register(motor, "W", ["X"])
    submit(
        motor,
        [
            task("waiting", required_capabilities=["X"]),
            task("ready", required_capabilities=["X"]),
        ],
    )
    waiting = claim(motor, "W")
    response = motor.post(
        f"/tasks/{waiting['task_id']}/provider_wait",
        headers=auth(),
        json={"worker_id": "W", "reason": "quota"},
    )
    assert response.status_code == 200

    assert claim(motor, "W")["task_id"] == "ready"


def test_waiting_provider_retains_exclusive_resource_until_genuinely_terminal(motor):
    register(motor, "W1", ["X"])
    register(motor, "W2", ["X"])
    submit(
        motor,
        [
            task("waiting-r", required_capabilities=["X"], exclusive_resources=["R"]),
            task("other-r", required_capabilities=["X"], exclusive_resources=["R"]),
        ],
    )
    waiting = claim(motor, "W1")
    response = motor.post(
        f"/tasks/{waiting['task_id']}/provider_wait",
        headers=auth(),
        json={"worker_id": "W1", "reason": "quota"},
    )

    assert response.get_json()["status"] == "WAITING_PROVIDER"
    assert claim(motor, "W2") is None
    assert server_app.load_state()["resource_owners"]["R"]["task_id"] == "waiting-r"


def test_independently_verified_terminal_task_releases_exclusive_resource(motor):
    register(motor, "W", ["X"])
    submit(
        motor,
        [task("terminal", required_capabilities=["X"], exclusive_resources=["R"])],
    )
    claimed = claim(motor, "W")
    result = {
        "goal_id": claimed["goal_id"],
        "task_id": claimed["task_id"],
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": "W",
        "run_id": "run-1",
        "result_id": "result-1",
        "status": "SUCCESS",
        "artifacts": [],
    }
    assert motor.post("/tasks/result", headers=auth(), json=result).status_code == 200
    verified = motor.post(
        "/tasks/verify",
        headers={"Authorization": "Bearer verifier-secret"},
        json={
            "task_id": "terminal",
            "result_id": "result-1",
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
        },
    )

    assert verified.get_json()["status"] == "RECONCILED"
    assert server_app.load_state()["resource_owners"] == {}


def test_protected_code_does_not_unlock_dependencies_before_explicit_merge_approval(motor):
    register(motor, "W", ["X"], authorities=["repo:write", "merge"])
    submit(
        motor,
        [
            task(
                "protected",
                required_capabilities=["X"],
                required_authorities=["repo:write"],
                merge_scope="protected_code",
            ),
            task("after-merge", required_capabilities=["X"], depends_on=["protected"]),
        ],
    )
    claimed = claim(motor, "W")
    result = {
        "goal_id": claimed["goal_id"],
        "task_id": "protected",
        "attempt_id": claimed["attempt_id"],
        "dispatch_id": claimed["dispatch_id"],
        "execution_ref": claimed["execution_ref"],
        "worker_id": "W",
        "run_id": "run-protected",
        "result_id": "result-protected",
        "status": "SUCCESS",
        "artifacts": [],
    }
    assert motor.post("/tasks/result", headers=auth(), json=result).status_code == 200
    verified = motor.post(
        "/tasks/verify",
        headers={"Authorization": "Bearer verifier-secret"},
        json={
            "task_id": "protected",
            "result_id": "result-protected",
            "verifier_id": "independent-verifier",
            "verdict": "PASS",
            "artifacts": [],
        },
    )
    assert verified.get_json()["status"] == "RECONCILED_PENDING_MERGE"
    assert claim(motor, "W") is None

    approved = motor.post(
        "/tasks/protected/approve_merge",
        headers=auth(),
        json={"approver": "human-owner", "merge_ref": "approved-ref"},
    )
    assert approved.get_json()["status"] == "RECONCILED"
    assert claim(motor, "W")["task_id"] == "after-merge"


def test_legacy_target_agent_behavior_remains_compatible(motor):
    register(motor, "MAC", ["macos"])
    submit(motor, [task("legacy", target_agent="mac")])

    assert claim(motor, "MAC")["task_id"] == "legacy"


@pytest.mark.parametrize(
    "gate_fields",
    [
        {"requires_spend": True},
        {"estimated_cost_eur": 1},
        {"requested_action": "merge"},
        {"requested_action": "purchase_tier"},
        {"requires_human_approval": True},
        {"human_gate_required": "YES"},
        {"required_authorities": ["spend"]},
    ],
)
def test_advertised_authority_cannot_bypass_spend_or_human_gate(motor, gate_fields):
    register(motor, "W", ["X"], authorities=["spend", "merge", "release", "approve"])
    fields = {"required_capabilities": ["X"], "required_authorities": ["spend"]}
    fields.update(gate_fields)
    gated = task("gated", **fields)
    submit(motor, [gated])

    assert claim(motor, "W") is None


def test_concurrent_claims_preserve_exactly_one_task_and_resource_owner(motor):
    worker_ids = [f"W{i}" for i in range(8)]
    for worker_id in worker_ids:
        register(motor, worker_id, ["X"])
    submit(
        motor,
        [task("single", required_capabilities=["X"], exclusive_resources=["R"])],
    )
    barrier = threading.Barrier(len(worker_ids))
    results = []
    results_lock = threading.Lock()

    def race(worker_id):
        http = server_app.app.test_client()
        barrier.wait()
        claimed = claim(http, worker_id)
        with results_lock:
            results.append(claimed)

    threads = [threading.Thread(target=race, args=(worker_id,)) for worker_id in worker_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    winners = [claimed for claimed in results if claimed is not None]
    state = server_app.load_state()
    assert len(winners) == 1
    assert winners[0]["task_id"] == "single"
    assert list(state["resource_owners"]) == ["R"]
    owner = state["resource_owners"]["R"]
    assert owner["task_id"] == "single"
    assert owner["attempt_id"] == "single:attempt:1"
    assert owner["worker_id"] == winners[0]["worker_id"]


def test_registration_persists_safe_provider_capacity_metadata_without_secrets(motor):
    register(
        motor,
        "W",
        ["X"],
        authorities=["repo:read"],
        provider="local-provider",
        capacity_identity="local-account-a",
    )
    observed = server_app.load_state()["workers"]["W"]
    assert observed["provider"] == "local-provider"
    assert observed["capacity_identity"] == "local-account-a"
    assert observed["provider_available"] is True
    assert observed["capacity_available"] is True
    assert observed["authorities"] == ["repo:read"]

    rejected = motor.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": "BAD",
            "capabilities": ["X"],
            "capacity_identity": "sk-secret-material-should-not-persist",
        },
    )
    assert rejected.status_code == 400
    assert "BAD" not in server_app.load_state()["workers"]


def test_unavailable_provider_capacity_does_not_block_other_worker(motor):
    register(motor, "WAITING", ["X"])
    register(motor, "READY", ["X"])
    response = motor.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": "WAITING",
            "capabilities": ["X"],
            "provider_available": False,
            "capacity_available": False,
        },
    )
    assert response.status_code == 200
    submit(motor, [task("work", required_capabilities=["X"])])

    assert claim(motor, "WAITING") is None
    assert claim(motor, "READY")["task_id"] == "work"
