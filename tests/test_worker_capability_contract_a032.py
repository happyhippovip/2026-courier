"""Tests for Worker Capability Contract and Eligibility Gate (ANTIGRAVITY 032).

Verifies fail-closed task routing and capability matching:
- Worker A: Windows, python & powershell available -> Compatible Worker (Task X claimed).
- Worker B: Linux, claims Task X -> Wrong OS rejected (matched=False, claim returns None).
- Worker C: Windows, but lacks required capability -> Missing Capability rejected (claim returns None).
- Worker D: Stale or malformed capability record -> Stale Record rejected (claim returns None).
- Unknown Runtime: Task requires unsupported runtime -> Unknown Runtime rejected.
- Direct helper verification: is_worker_eligible_for_task invariants tested across all boundary conditions.
"""

import pytest

import server.app as server_app
from server.app import is_worker_eligible_for_task


def auth_headers():
    return {"Authorization": "Bearer test-secret", "Content-Type": "application/json"}


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setenv("COURIER_API_KEY", "test-secret")
    monkeypatch.setenv("COURIER_VERIFIER_API_KEY", "verifier-secret")
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "server_state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    return server_app.app.test_client()


def test_compatible_worker_claims_task_x(http):
    """Worker A: Windows with required python & powershell capabilities claims Task X."""
    worker_a = {
        "worker_id": "WORKER-A",
        "platform": "windows",
        "capabilities": ["windows", "python", "powershell"],
        "supported_runtimes": ["python3.11"],
    }
    http.post("/workers/register", headers=auth_headers(), json=worker_a)

    task_x = {
        "task_id": "task-x",
        "target_agent": "windows",
        "required_capabilities": ["powershell", "python"],
        "artifacts": ["out.txt"],
    }
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "run task x", "workflow_plan": [task_x]},
    )

    res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WORKER-A"})
    claimed = res.get_json()["task"]
    assert claimed is not None
    assert claimed["task_id"] == "task-x"
    assert claimed["worker_id"] == "WORKER-A"


def test_wrong_os_worker_rejected_for_task_x(http):
    """Worker B: Linux worker claiming Task X (target_agent: windows) is rejected."""
    worker_b = {
        "worker_id": "WORKER-B",
        "platform": "linux",
        "capabilities": ["linux", "python"],
    }
    http.post("/workers/register", headers=auth_headers(), json=worker_b)

    task_x = {
        "task_id": "task-x-linux-test",
        "target_agent": "windows",
        "required_capabilities": ["powershell"],
        "artifacts": ["out.txt"],
    }
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "windows goal", "workflow_plan": [task_x]},
    )

    res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WORKER-B"})
    assert res.get_json()["task"] is None


def test_missing_capability_worker_rejected_for_task_x(http):
    """Worker C: Windows worker lacking required 'powershell' capability is rejected."""
    worker_c = {
        "worker_id": "WORKER-C",
        "platform": "windows",
        "capabilities": ["windows"],  # Lacks "powershell"
    }
    http.post("/workers/register", headers=auth_headers(), json=worker_c)

    task_x = {
        "task_id": "task-x-missing-cap",
        "target_agent": "windows",
        "required_capabilities": ["powershell"],
        "artifacts": ["out.txt"],
    }
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "powershell task", "workflow_plan": [task_x]},
    )

    res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WORKER-C"})
    assert res.get_json()["task"] is None


def test_stale_capability_record_rejected(http):
    """Worker D: Marked stale or with invalid capabilities metadata is rejected."""
    # Register worker D
    http.post(
        "/workers/register",
        headers=auth_headers(),
        json={"worker_id": "WORKER-D", "platform": "windows", "capabilities": ["windows", "powershell"]},
    )

    # Corrupt or mark capabilities stale in state
    state = server_app.load_state()
    state["workers"]["WORKER-D"]["capabilities_stale"] = True
    server_app.save_state(state)

    task_x = {
        "task_id": "task-x-stale-test",
        "target_agent": "windows",
        "artifacts": ["out.txt"],
    }
    http.post(
        "/goals",
        headers=auth_headers(),
        json={"goal_text": "stale test", "workflow_plan": [task_x]},
    )

    res = http.post("/tasks/claim", headers=auth_headers(), json={"worker_id": "WORKER-D"})
    assert res.get_json()["task"] is None


def test_unknown_runtime_rejected():
    """Direct helper test: Task requires unsupported runtime -> fails closed."""
    worker = {
        "platform": "windows",
        "capabilities": ["windows", "python"],
        "supported_runtimes": ["python3.10"],
    }
    task = {
        "target_agent": "windows",
        "required_capabilities": ["python"],
        "required_runtime": "ruby3.2",  # Unsupported
    }
    assert is_worker_eligible_for_task(worker, task) is False

    # Supported runtime matches
    task_supported = {
        "target_agent": "windows",
        "required_capabilities": ["python"],
        "required_runtime": "python3.10",
    }
    assert is_worker_eligible_for_task(worker, task_supported) is True


def test_is_worker_eligible_for_task_boundary_matrix():
    """Verify all capability and platform boundary conditions fail closed."""
    # Non-dict inputs
    assert is_worker_eligible_for_task(None, {}) is False
    assert is_worker_eligible_for_task({}, None) is False

    # Non-list capabilities
    assert is_worker_eligible_for_task({"capabilities": "windows"}, {"target_agent": "windows"}) is False

    # Stale flags
    assert is_worker_eligible_for_task({"capabilities": ["windows"], "stale": True}, {"target_agent": "windows"}) is False

    # Platform mismatch: claims 'windows' capability but platform is 'linux'
    mismatched_worker = {
        "platform": "linux",
        "capabilities": ["windows"],
    }
    windows_task = {"target_agent": "windows"}
    assert is_worker_eligible_for_task(mismatched_worker, windows_task) is False
