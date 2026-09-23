from scripts.integration_contract import _canonical_hash
import hashlib
import json
import threading
import time
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from server import app as server_app


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


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
    import hashlib
    base = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref", "exec-mock"),
        "worker_id": task["worker_id"],
        "run_id": "pid-123",
        "status": "SUCCESS",
        "artifacts": [
            {"path": "bounded.txt", "sha256": hashlib.sha256(b"bounded\n").hexdigest()}
        ],
        "runtime_identity": task.get("server_binding", "MAC-01")
    }
    ident = dict(base)
    base["result_id"] = "result-" + _canonical_hash(ident)
    return base
def test_insecure_default_key_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "API_KEY", "dev-secret-key")
    response = server_app.app.test_client().post("/workers/register", json={"worker_id": "worker"})
    assert response.status_code == 503


@pytest.mark.parametrize("endpoint", ["/workers", "/walls"])
def test_operator_state_endpoints_require_auth(tmp_path, monkeypatch, endpoint):
    http = client(tmp_path, monkeypatch)

    assert http.get(endpoint).status_code == 401
    assert http.get(endpoint, headers=auth()).status_code == 200


@pytest.mark.parametrize(
    "script",
    [
        "scripts/courier_verifier.py",
        "scripts/courier_github_dispatcher.py",
        "scripts/courier_watchdog.py",
    ],
)
def test_background_agents_fail_closed_without_api_key(script):
    env = os.environ.copy()
    env.pop("COURIER_API_KEY", None)
    env.pop("COURIER_VERIFIER_API_KEY", None)
    env["PYTHONKEYRING_BACKEND"] = "keyring.backends.null.Keyring"

    result = subprocess.run(
        [sys.executable, script], capture_output=True, text=True, env=env, timeout=15
    )

    assert result.returncode != 0
    expected = "COURIER_VERIFIER_API_KEY" if script.endswith("courier_verifier.py") else "COURIER_API_KEY"
    assert f"{expected} is required" in result.stderr


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
        "received_runtime_identity": task.get("server_binding", "MAC-01"),
    }

    self_certification = dict(verification, verifier_id=task["worker_id"])
    assert http.post("/tasks/verify", headers=verifier_auth(), json=self_certification).status_code == 400
    accepted = http.post("/tasks/verify", headers=verifier_auth(), json=verification)
    duplicate = http.post("/tasks/verify", headers=verifier_auth(), json=verification)

    assert accepted.status_code == 200
    assert duplicate.get_json()["status"] == "ACK_DUPLICATE"
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RECONCILED"
    assert state["goals"][goal_id]["status"] == "DONE"


def test_worker_credential_cannot_self_certify_with_forged_verifier_id(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    forged = {
        "task_id": task["task_id"],
        "result_id": result["result_id"],
        "verifier_id": "VERIFIER-01",
        "verdict": "PASS",
        "artifacts": result["artifacts"],
        "received_runtime_identity": task.get("server_binding", "MAC-01"),
    }

    assert http.get("/tasks/pending_verification", headers=auth()).status_code == 401
    assert http.post("/tasks/verify", headers=auth(), json=forged).status_code == 401
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RESULT_RECEIVED"
    assert state["goals"][goal_id]["current_step_index"] == 0


def test_verifier_authority_fails_closed_when_shared_with_worker(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "test-secret")

    response = http.post(
        "/tasks/verify",
        headers=auth(),
        json={
            "task_id": task["task_id"],
            "result_id": result["result_id"],
            "verifier_id": "VERIFIER-01",
            "verdict": "PASS",
            "artifacts": result["artifacts"],
        "received_runtime_identity": task.get("server_binding", "MAC-01"),
        },
    )

    assert response.status_code == 503
    assert server_app.load_state()["tasks"][task["task_id"]]["status"] == "RESULT_RECEIVED"


def test_goal_without_manual_plan_uses_existing_planner(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)

    class DeterministicChief:
        def formulate_workflow_plan(self, goal_text, idea_type):
            assert goal_text == "build and verify one bounded artifact"
            assert idea_type == "GOAL"
            return "workflow-1", [
                {"task_id": "planned-a", "target_agent": "github", "instruction": "create artifact"},
                {"task_id": "planned-b", "target_agent": "antigravity", "instruction": "inspect artifact"},
            ]

    monkeypatch.setattr(server_app, "ChiefCommander", DeterministicChief)
    response = http.post(
        "/goals", headers=auth(), json={"goal_text": "build and verify one bounded artifact"}
    )

    assert response.status_code == 200
    goal_id = response.get_json()["goal_id"]
    observed = http.get(f"/goals/{goal_id}", headers=auth()).get_json()
    plan = observed["goal"]["workflow_plan"]
    assert [task["task_id"] for task in plan] == ["planned-a", "planned-b"]
    assert [task["target_agent"] for task in plan] == ["github", "mac"]
    assert observed["goal"]["current_step_index"] == 0


def test_corrupt_state_is_not_treated_as_empty(tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"goals":', encoding="utf-8")
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))

    with pytest.raises(json.JSONDecodeError):
        server_app.load_state()


def test_retry_gets_new_attempt_and_dispatch_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "calculate_backoff", lambda attempt: 0)
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    failed = durable_result(task)
    failed["status"] = "FAILED"
    failed["artifacts"] = []
    ident = {k: v for k, v in failed.items() if k != "result_id"}
    failed["result_id"] = "result-" + _canonical_hash(ident)
    assert http.post("/tasks/result", headers=auth(), json=failed).status_code == 200

    retried = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]

    assert retried["attempt_id"] == "task-1:attempt:2"
    assert retried["dispatch_id"] != task["dispatch_id"]
    assert retried["status"] == "DISPATCHED"


def test_worker_cannot_claim_second_task_while_first_is_active(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    assert http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
    ).status_code == 200
    for number in (1, 2):
        assert http.post(
            "/goals",
            headers=auth(),
            json={
                "goal_text": f"bounded goal {number}",
                "workflow_plan": [{
                    "task_id": f"task-{number}",
                    "target_agent": "mac",
                    "artifacts": [f"artifact-{number}.txt"],
                }],
            },
        ).status_code == 200

    first = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"})
    second = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"})

    assert first.get_json()["task"]["task_id"] == "task-1"
    assert second.get_json() == {"task": None, "reason": "WORKER_BUSY"}
    state = server_app.load_state()
    assert state["workers"]["MAC-01"]["current_task"] == "task-1"
    assert state["goals"][next(
        goal_id for goal_id, goal in state["goals"].items() if goal["goal_text"] == "bounded goal 2"
    )]["workflow_plan"][0]["status"] == "QUEUED"


def test_reregister_does_not_erase_active_worker_claim(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)

    response = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
    )

    assert response.status_code == 200
    worker = server_app.load_state()["workers"]["MAC-01"]
    assert worker["current_task"] == task["task_id"]
    assert worker["available"] is False


def test_concurrent_claims_have_exactly_one_winner(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    assert http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "MAC-01", "platform": "mac", "capabilities": ["macos"]},
    ).status_code == 200
    assert http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "one concurrent claim",
            "workflow_plan": [{
                "task_id": "task-concurrent",
                "target_agent": "mac",
                "artifacts": ["concurrent.txt"],
            }],
        },
    ).status_code == 200

    original_save = server_app.save_state
    first_save_waiting = threading.Event()
    second_save_arrived = threading.Event()
    arrival_lock = threading.Lock()
    arrivals = 0

    def coordinated_save(state):
        nonlocal arrivals
        with arrival_lock:
            arrivals += 1
            arrival = arrivals
        if arrival == 1:
            first_save_waiting.set()
            second_save_arrived.wait(timeout=0.5)
        elif first_save_waiting.is_set():
            second_save_arrived.set()
        original_save(state)

    monkeypatch.setattr(server_app, "save_state", coordinated_save)

    def claim():
        with server_app.app.test_client() as concurrent_http:
            return concurrent_http.post(
                "/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}
            ).get_json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: claim(), range(2)))

    claimed = [response["task"] for response in responses if response.get("task")]
    assert len(claimed) == 1
    assert claimed[0]["task_id"] == "task-concurrent"
    assert sorted(response.get("reason", "CLAIMED") for response in responses) == [
        "CLAIMED", "WORKER_BUSY"
    ]


def test_stale_claim_is_quarantined_without_replay_and_other_goal_continues(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    for worker_id in ("MAC-STALE", "MAC-HEALTHY"):
        assert http.post(
            "/workers/register",
            headers=auth(),
            json={"worker_id": worker_id, "platform": "mac", "capabilities": ["macos"]},
        ).status_code == 200
    goal_ids = []
    for number in (1, 2):
        response = http.post(
            "/goals",
            headers=auth(),
            json={
                "goal_text": f"independent goal {number}",
                "workflow_plan": [{
                    "task_id": f"stale-test-{number}",
                    "target_agent": "mac",
                    "artifacts": [f"stale-test-{number}.txt"],
                }],
            },
        )
        goal_ids.append(response.get_json()["goal_id"])

    claimed = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": "MAC-STALE"}
    ).get_json()["task"]
    state = server_app.load_state()
    state["workers"]["MAC-STALE"]["last_seen"] = time.time() - 600
    server_app.save_state(state)

    recovered = http.post("/tasks/reclaim_stale", headers=auth())

    assert recovered.get_json() == {"reclaimed_tasks": 0, "quarantined_tasks": 1}
    state = server_app.load_state()
    assert state["tasks"][claimed["task_id"]]["status"] == "HUMAN_REQUIRED"
    assert state["tasks"][claimed["task_id"]]["dispatch_id"] == claimed["dispatch_id"]
    assert state["goals"][goal_ids[0]]["status"] == "BLOCKED"
    assert state["workers"]["MAC-STALE"]["current_task"] is None

    independent = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": "MAC-HEALTHY"}
    ).get_json()["task"]
    assert independent["task_id"] == "stale-test-2"

    late_result = durable_result(claimed)
    assert http.post("/tasks/result", headers=auth(), json=late_result).status_code == 409
    assert server_app.load_state()["tasks"][claimed["task_id"]]["status"] == "HUMAN_REQUIRED"


def test_schema_version_future_fails_closed_with_system_exit(tmp_path, monkeypatch):
    """Schema version > 2 must fail closed via sys.exit(1), not crash with NameError."""
    state_file = tmp_path / "future_state.json"
    state_file.write_text(json.dumps({"schema_version": 99, "goals": {}}))
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))

    with pytest.raises(SystemExit) as excinfo:
        server_app.load_state()
    assert excinfo.value.code == 1


def test_save_state_cleans_up_temp_file_on_error(tmp_path, monkeypatch):
    """save_state must clean up the .tmp file if serialization fails."""
    state_file = tmp_path / "test_cleanup.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))

    # Attempt to save state with an un-serializable object (set)
    unserializable_state = {"schema_version": 2, "bad_data": {1, 2, 3}}
    with pytest.raises(TypeError):
        server_app.save_state(unserializable_state)

    # Verify no .tmp file was leaked in the directory
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"Expected no leftover .tmp files, found: {tmp_files}"


def test_terminal_verification_failure_releases_resources_and_blocks_goal(tmp_path, monkeypatch):
    """When a task terminally fails verification, its exclusive resources are freed and goal is BLOCKED."""
    http = client(tmp_path, monkeypatch)
    http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "W-FAIL", "platform": "mac", "capabilities": ["macos"]},
    )
    goal_res = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "failing goal",
            "workflow_plan": [
                {
                    "task_id": "t-fail-verify",
                    "target_agent": "mac",
                    "instruction": "do work",
                    "artifacts": ["out.txt"],
                    "exclusive_resources": ["gpu-0"],
                }
            ],
        },
    ).get_json()
    gid = goal_res["goal_id"]

    # Claim the task
    claim_res = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-FAIL"})
    task = claim_res.get_json()["task"]

    # Check resource was acquired
    st = server_app.load_state()
    assert "gpu-0" in st.get("resource_owners", {})

    # Submit success result so it reaches RESULT_RECEIVED
    res_payload = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=res_payload).status_code == 200

    # Exhaust verification retries (MAX_RETRIES is 3)
    # Fail 1
    v1 = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": "t-fail-verify",
        "verifier_id": "V-01",
        "result_id": res_payload["result_id"],
        "artifacts": res_payload["artifacts"],
        "verdict": "FAIL",
        "reason": "bad output 1",
        "received_runtime_identity": task["server_binding"],
    })
    assert v1.status_code == 200
    assert v1.get_json()["status"] == "QUEUED"

    # Reset backoff to allow immediate re-claim in test
    st = server_app.load_state()
    st["tasks"]["t-fail-verify"]["next_retry_at"] = 0
    for step in st["goals"][gid]["workflow_plan"]:
        if step["task_id"] == "t-fail-verify":
            step["next_retry_at"] = 0
    server_app.save_state(st)

    # Re-claim and re-submit result for attempt 2
    claim2 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-FAIL"}).get_json()["task"]
    assert claim2 is not None
    res2 = durable_result(claim2)
    http.post("/tasks/result", headers=auth(), json=res2)

    # Fail 2
    v2 = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": "t-fail-verify",
        "verifier_id": "V-01",
        "result_id": res2["result_id"],
        "artifacts": res2["artifacts"],
        "verdict": "FAIL",
        "reason": "bad output 2",
        "received_runtime_identity": claim2["server_binding"],
    })
    assert v2.status_code == 200
    assert v2.get_json()["status"] == "QUEUED"

    # Reset backoff to allow immediate re-claim in test
    st = server_app.load_state()
    st["tasks"]["t-fail-verify"]["next_retry_at"] = 0
    for step in st["goals"][gid]["workflow_plan"]:
        if step["task_id"] == "t-fail-verify":
            step["next_retry_at"] = 0
    server_app.save_state(st)

    # Re-claim and re-submit result for attempt 3
    claim3 = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-FAIL"}).get_json()["task"]
    assert claim3 is not None
    res3 = durable_result(claim3)
    http.post("/tasks/result", headers=auth(), json=res3)

    # Fail 3 -> should hit FAILED_TERMINAL
    v3 = http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": "t-fail-verify",
        "verifier_id": "V-01",
        "result_id": res3["result_id"],
        "artifacts": res3["artifacts"],
        "verdict": "FAIL",
        "reason": "bad output 3",
        "received_runtime_identity": claim3["server_binding"],
    })
    assert v3.status_code == 200
    assert v3.get_json()["status"] == "FAILED_TERMINAL"

    # Verify state: goal is BLOCKED and resource gpu-0 is freed
    st_final = server_app.load_state()
    assert st_final["tasks"]["t-fail-verify"]["status"] == "FAILED_TERMINAL"
    assert st_final["goals"][gid]["status"] == "BLOCKED"
    assert "gpu-0" not in st_final.get("resource_owners", {})


def test_ambiguous_crash_in_result_blocks_goal(tmp_path, monkeypatch):
    """When a worker reports AMBIGUOUS_CRASH, task is HUMAN_REQUIRED and goal is BLOCKED."""
    http = client(tmp_path, monkeypatch)
    http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "W-CRASH", "platform": "mac", "capabilities": ["macos"]},
    )
    goal = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "crash test goal",
            "workflow_plan": [{"task_id": "t-crash", "target_agent": "mac", "instruction": "do work"}],
        },
    ).get_json()
    gid = goal["goal_id"]

    claimed = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-CRASH"}).get_json()["task"]
    crash_res = durable_result(claimed)
    crash_res["status"] = "FAILED"
    crash_res["artifacts"] = []
    # Re-compute result_id using only canonical identity fields (without stderr)
    ident = {
        "goal_id": crash_res["goal_id"],
        "task_id": crash_res["task_id"],
        "attempt_id": crash_res["attempt_id"],
        "dispatch_id": crash_res["dispatch_id"],
        "execution_ref": crash_res["execution_ref"],
        "worker_id": crash_res["worker_id"],
        "run_id": crash_res["run_id"],
        "status": "FAILED",
        "artifacts": [],
        "runtime_identity": crash_res["runtime_identity"],
    }
    crash_res["result_id"] = f"result-{_canonical_hash(ident)}"
    crash_res["stderr"] = "AMBIGUOUS_CRASH: process terminated unexpectedly"

    resp = http.post("/tasks/result", headers=auth(), json=crash_res)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ACK_RESULT_RECEIVED"

    st = server_app.load_state()
    assert st["tasks"]["t-crash"]["status"] == "HUMAN_REQUIRED"
    assert st["goals"][gid]["status"] == "BLOCKED"


def test_terminal_result_failure_releases_resources_and_blocks_goal(tmp_path, monkeypatch):
    """When a task reaches FAILED_TERMINAL in /tasks/result, resources are freed and goal is BLOCKED."""
    http = client(tmp_path, monkeypatch)
    http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": "W-FAIL-RES", "platform": "mac", "capabilities": ["macos"]},
    )
    goal = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "terminal failure goal",
            "workflow_plan": [{
                "task_id": "t-term-res",
                "target_agent": "mac",
                "instruction": "fail work",
                "exclusive_resources": ["exclusive-lock-1"],
            }],
        },
    ).get_json()
    gid = goal["goal_id"]

    for attempt in range(1, 5):  # 1 initial attempt + 3 retries = 4 attempts
        claim = http.post("/tasks/claim", headers=auth(), json={"worker_id": "W-FAIL-RES"}).get_json()["task"]
        assert claim is not None
        # Check resource is held while active
        st = server_app.load_state()
        assert "exclusive-lock-1" in st.get("resource_owners", {})

        fail_res = durable_result(claim)
        fail_res["status"] = "FAILED"
        fail_res["artifacts"] = []
        ident = {
            "goal_id": fail_res["goal_id"],
            "task_id": fail_res["task_id"],
            "attempt_id": fail_res["attempt_id"],
            "dispatch_id": fail_res["dispatch_id"],
            "execution_ref": fail_res["execution_ref"],
            "worker_id": fail_res["worker_id"],
            "run_id": fail_res["run_id"],
            "status": "FAILED",
            "artifacts": [],
            "runtime_identity": fail_res["runtime_identity"],
        }
        fail_res["result_id"] = f"result-{_canonical_hash(ident)}"
        fail_res["stderr"] = f"deterministic execution failure attempt {attempt}"

        resp = http.post("/tasks/result", headers=auth(), json=fail_res)
        assert resp.status_code == 200

        if attempt < 4:
            # Clear backoff for next iteration
            st = server_app.load_state()
            st["tasks"]["t-term-res"]["next_retry_at"] = 0
            for step in st["goals"][gid]["workflow_plan"]:
                if step["task_id"] == "t-term-res":
                    step["next_retry_at"] = 0
            server_app.save_state(st)

    # After 3 failed attempts, task must be FAILED_TERMINAL, goal BLOCKED, and resource released
    st_final = server_app.load_state()
    assert st_final["tasks"]["t-term-res"]["status"] == "FAILED_TERMINAL"
    assert st_final["goals"][gid]["status"] == "BLOCKED"
    assert "exclusive-lock-1" not in st_final.get("resource_owners", {})

