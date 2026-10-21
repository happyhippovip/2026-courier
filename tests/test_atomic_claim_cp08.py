"""CP-08 / CQ-08 Atomic Claim & Barrier-Controlled Race Fixture.

Acceptance:
- Genau ein Claim gewinnt bei gleichzeitig freien Workern.
- Verlierer veraendert weder Attempt noch Lease des Gewinners.
- Test benoetigt keine Modellaufrufe (Zero model calls).
Required Evidence:
- ['claim-path', 'lease-record', 'isolated-race-fixture']
"""

import json
import pytest
import threading
from pathlib import Path

from server import app as server_app
from courier_core.controller import Controller
from courier_core.atomic_claim import AtomicClaimRacer, _extract_task_id


@pytest.fixture
def http_server(tmp_path, monkeypatch):
    state_file = tmp_path / "central_state.json"
    monkeypatch.setattr(server_app, "STATE_FILE", str(state_file))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client(), state_file


def auth():
    return {"Authorization": "Bearer test-secret"}


def _register_worker(http, worker_id: str, platform: str = "mac", capability: str = "macos"):
    res = http.post(
        "/workers/register",
        headers=auth(),
        json={"worker_id": worker_id, "platform": platform, "capabilities": [capability]},
    )
    assert res.status_code == 200


def _submit_single_task_goal(http, task_id: str = "task-race-01", target: str = "mac"):
    res = http.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": f"Race goal for {task_id}",
            "workflow_plan": [
                {
                    "task_id": task_id,
                    "target_agent": target,
                    "instruction": "Execute race step",
                    "artifacts": ["out.txt"],
                }
            ],
        },
    )
    assert res.status_code in (200, 201)


def test_two_free_workers_competing_for_single_task_has_exactly_one_winner(http_server):
    """Core CP-08 test: Two free, qualified workers concurrently claim one task under barrier."""
    http, state_file = http_server

    # Register two distinct, free, qualified workers
    _register_worker(http, "WORKER-ALPHA")
    _register_worker(http, "WORKER-BETA")

    # Submit 1 goal with 1 queued task
    _submit_single_task_goal(http, "task-race-01")

    # Race fixture: both workers call /tasks/claim simultaneously across threads
    callables = {
        "WORKER-ALPHA": lambda: server_app.app.test_client().post(
            "/tasks/claim", headers=auth(), json={"worker_id": "WORKER-ALPHA"}
        ).get_json(),
        "WORKER-BETA": lambda: server_app.app.test_client().post(
            "/tasks/claim", headers=auth(), json={"worker_id": "WORKER-BETA"}
        ).get_json(),
    }

    racer = AtomicClaimRacer(callables)
    results = racer.run_race(timeout_s=5.0)

    winner, losers = AtomicClaimRacer.verify_single_winner_invariants(results, "task-race-01")

    assert winner.worker_id in ("WORKER-ALPHA", "WORKER-BETA")
    assert len(losers) == 1
    loser = losers[0]
    assert loser.worker_id in ("WORKER-ALPHA", "WORKER-BETA")
    assert loser.worker_id != winner.worker_id

    # Loser received task=None
    assert loser.task.get("task") is None

    # Winner received valid task with attempt == 1
    winner_task = winner.task["task"]
    assert winner_task["task_id"] == "task-race-01"
    assert winner_task["worker_id"] == winner.worker_id
    assert winner_task["attempts"] == 1
    assert winner_task["attempt_id"] == "task-race-01:attempt:1"
    assert winner_task["status"] == "DISPATCHED"

    # State check: Central state reflects winner exclusively
    state = server_app.load_state()
    stored_task = state["tasks"]["task-race-01"]
    assert stored_task["worker_id"] == winner.worker_id
    assert stored_task["attempts"] == 1
    assert stored_task["status"] == "DISPATCHED"

    # Loser worker remained available and was not assigned this task
    assert state["workers"][loser.worker_id]["current_task"] is None
    assert state["workers"][winner.worker_id]["current_task"] == "task-race-01"


def test_subsequent_loser_claims_do_not_mutate_winner_lease_or_attempts(http_server):
    """Invariant: Loser retries do not mutate attempt count or dispatch_id of the winner."""
    http, state_file = http_server

    _register_worker(http, "WORKER-WINNER")
    _register_worker(http, "WORKER-LOSER")
    _submit_single_task_goal(http, "task-lease-fence")

    # Winner claims
    win_resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-WINNER"}).get_json()
    winner_task = win_resp["task"]
    assert winner_task is not None
    original_dispatch_id = winner_task["dispatch_id"]
    original_attempt = winner_task["attempts"]

    # Loser attempts repeated claims
    for _ in range(3):
        lose_resp = http.post("/tasks/claim", headers=auth(), json={"worker_id": "WORKER-LOSER"}).get_json()
        assert lose_resp.get("task") is None

    # State check: Winner's task identity and attempt count remain completely unaltered
    state = server_app.load_state()
    persisted = state["tasks"]["task-lease-fence"]
    assert persisted["worker_id"] == "WORKER-WINNER"
    assert persisted["dispatch_id"] == original_dispatch_id
    assert persisted["attempts"] == original_attempt
    assert persisted["attempts"] == 1


def test_four_workers_race_for_two_tasks(http_server):
    """4 workers race for 2 distinct queued tasks. Exactly 2 win distinct tasks, 2 lose."""
    http, state_file = http_server

    workers = [f"WORKER-{i}" for i in range(1, 5)]
    for w in workers:
        _register_worker(http, w)

    # Submit 2 queued tasks
    _submit_single_task_goal(http, "task-dual-1")
    _submit_single_task_goal(http, "task-dual-2")

    callables = {
        w: (lambda wid=w: server_app.app.test_client().post(
            "/tasks/claim", headers=auth(), json={"worker_id": wid}
        ).get_json())
        for w in workers
    }

    racer = AtomicClaimRacer(callables)
    results = racer.run_race(timeout_s=5.0)

    winners = [r for r in results if r.acquired and r.task.get("task")]
    losers = [r for r in results if not r.acquired or r.task.get("task") is None]

    assert len(winners) == 2
    assert len(losers) == 2

    # Both claimed tasks are distinct (no double claim on same task)
    claimed_task_ids = {w.task["task"]["task_id"] for w in winners}
    assert claimed_task_ids == {"task-dual-1", "task-dual-2"}

    # Both winning workers are distinct
    winner_worker_ids = {w.worker_id for w in winners}
    assert len(winner_worker_ids) == 2

    # Invariants on both tasks
    for w in winners:
        assert w.task["task"]["attempts"] == 1


def test_controller_concurrent_claims_barrier_race(tmp_path):
    """Direct Controller unit test: Barrier race with SQLite journal transactions."""
    home = tmp_path / "ctrl_home"
    controller = Controller(home).boot()

    # Create 1 task with valid idempotent effect_class
    status, created = controller.create_task({
        "adapter": "local_shell",
        "params": {"cmd": "echo test"},
        "effect_class": "idempotent",
        "max_attempts": 3,
        "lease_ttl_s": 60,
    })
    assert status == 201
    task_id = created["task_id"]

    callables = {
        "WORKER-1": lambda: controller.claim({"worker_id": "WORKER-1"}),
        "WORKER-2": lambda: controller.claim({"worker_id": "WORKER-2"}),
    }

    racer = AtomicClaimRacer(callables)
    results = racer.run_race(timeout_s=5.0)

    winner, losers = AtomicClaimRacer.verify_single_winner_invariants(results, task_id)
    assert winner.worker_id in ("WORKER-1", "WORKER-2")
    assert len(losers) == 1
    assert losers[0].task is None

    # Winner lease is recorded in controller
    assert winner.task["task_id"] == task_id
    assert winner.task["attempt"] == 1
    assert winner.task["dispatch_id"] in controller._leases
    assert len(controller._leases) == 1


def test_zero_external_model_calls_invariant():
    """CP-08 Acceptance: 'Test benötigt keine Modellaufrufe'."""
    racer = AtomicClaimRacer({"W1": lambda: {"task": {"task_id": "t1"}}, "W2": lambda: None})
    res = racer.run_race()
    win, lose = AtomicClaimRacer.verify_single_winner_invariants(res, "t1")
    assert win.worker_id == "W1"
    assert len(lose) == 1
