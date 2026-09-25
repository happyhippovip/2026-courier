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

    result = subprocess.run(
        [sys.executable, script], capture_output=True, text=True, env=env, timeout=5
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
    }

    self_certification = dict(verification, verifier_id=task["worker_id"])
    assert http.post("/tasks/verify", headers=verifier_auth(), json=self_certification).status_code == 400
    accepted = http.post("/tasks/verify", headers=verifier_auth(), json=verification)
    duplicate = http.post("/tasks/verify", headers=verifier_auth(), json=verification)

    assert accepted.status_code == 200
    assert duplicate.get_json()["status"] == "ACK_DUPLICATE"
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "RECONCILED"
    assert state["goals"][goal_id]["current_step_index"] == 1
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
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    failed = durable_result(task)
    failed["status"] = "FAILED"
    failed["artifacts"] = []
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


def _verify(http, task, result, verdict):
    return http.post("/tasks/verify", headers=verifier_auth(), json={
        "task_id": task["task_id"],
        "result_id": result["result_id"],
        "verifier_id": "VERIFIER-01",
        "verdict": verdict,
        "artifacts": result["artifacts"],
    })


def test_verification_outcome_is_mirrored_into_workflow_step(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    assert _verify(http, task, result, "PASS").status_code == 200

    step = server_app.load_state()["goals"][goal_id]["workflow_plan"][0]
    assert step["status"] == "RECONCILED"


def test_failed_verification_can_be_resumed_with_new_attempt(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    assert _verify(http, task, result, "FAIL").get_json()["status"] == "FAILED_VERIFICATION"

    resumed = http.post(f"/tasks/{task['task_id']}/resume", headers=auth(), json={"action": "retry"})

    assert resumed.status_code == 200
    state = server_app.load_state()
    assert state["goals"][goal_id]["status"] == "ACTIVE"
    assert state["tasks"][task["task_id"]]["status"] == "QUEUED"
    retried = http.post("/tasks/claim", headers=auth(), json={"worker_id": "MAC-01"}).get_json()["task"]
    assert retried["attempt_id"] == "task-1:attempt:2"
    assert retried["dispatch_id"] != task["dispatch_id"]
    # The superseded attempt's result can no longer bind to the task.
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 400


def test_resume_cannot_force_success_without_bound_evidence(tmp_path, monkeypatch):
    http, goal_id, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    assert _verify(http, task, result, "FAIL").status_code == 200

    forced = http.post(f"/tasks/{task['task_id']}/resume", headers=auth(), json={"action": "force_success"})

    assert forced.status_code == 400
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "FAILED_VERIFICATION"
    assert state["goals"][goal_id]["workflow_plan"][0]["status"] == "FAILED_VERIFICATION"


def test_resume_route_is_registered_when_run_as_script():
    source = open(server_app.__file__, encoding="utf-8").read()
    main_guard = source.index('if __name__ == "__main__":')
    assert source.index("def resume_task") < main_guard


def test_resent_result_is_acknowledged_idempotently(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200

    resent = http.post("/tasks/result", headers=auth(), json=result)

    assert resent.status_code == 200
    assert resent.get_json()["status"] == "ACK_DUPLICATE"


def test_conflicting_result_for_processed_task_is_rejected(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    result = durable_result(task)
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    conflicting = dict(result, result_id="result-other")

    rejected = http.post("/tasks/result", headers=auth(), json=conflicting)

    assert rejected.status_code == 409
    assert server_app.load_state()["tasks"][task["task_id"]]["result"]["result_id"] == "result-1"


def test_resent_failed_result_is_acknowledged_after_requeue(tmp_path, monkeypatch):
    http, _, task = setup_claimed_task(tmp_path, monkeypatch)
    failed = dict(durable_result(task), status="FAILED", artifacts=[])
    assert http.post("/tasks/result", headers=auth(), json=failed).status_code == 200

    resent = http.post("/tasks/result", headers=auth(), json=failed)

    assert resent.status_code == 200
    assert resent.get_json()["status"] == "ACK_DUPLICATE"
    state = server_app.load_state()
    assert state["tasks"][task["task_id"]]["status"] == "QUEUED"
    assert state["tasks"][task["task_id"]]["attempts"] == 1
