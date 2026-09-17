"""Focused adversarial proofs for Ledger/Guard/Motor software boundaries.

These are deterministic software tests.  They deliberately do not claim the
separate physical queue-independence acceptance proof.
"""

import importlib.util
import os
from pathlib import Path

import pytest

from server import app as server_app


ROOT = Path(__file__).parent.parent.resolve()
CONTINUE_SPEC = importlib.util.spec_from_file_location(
    "courier_continue_championship", ROOT / "scripts" / "courier_continue.py"
)
assert CONTINUE_SPEC and CONTINUE_SPEC.loader
continue_module = importlib.util.module_from_spec(CONTINUE_SPEC)
CONTINUE_SPEC.loader.exec_module(continue_module)


def auth():
    return {"Authorization": "Bearer test-secret"}


def verifier_auth():
    return {"Authorization": "Bearer verifier-secret"}


@pytest.fixture
def motor(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(server_app, "BATCH_QUEUE_DIR", str(tmp_path / "batches"))
    monkeypatch.setattr(server_app, "API_KEY", "test-secret")
    monkeypatch.setattr(server_app, "VERIFIER_API_KEY", "verifier-secret")
    return server_app.app.test_client()


def register(http, worker_id="W"):
    response = http.post(
        "/workers/register",
        headers=auth(),
        json={
            "worker_id": worker_id,
            "platform": "test",
            "capabilities": ["X"],
        },
    )
    assert response.status_code == 200


def claim(http, worker_id="W"):
    response = http.post(
        "/tasks/claim", headers=auth(), json={"worker_id": worker_id}
    )
    assert response.status_code == 200
    return response.get_json().get("task")


def complete_and_verify(http, task, suffix):
    result_id = f"result-{suffix}"
    result = {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task["execution_ref"],
        "worker_id": task["worker_id"],
        "run_id": f"run-{suffix}",
        "result_id": result_id,
        "status": "SUCCESS",
        "artifacts": [],
    }
    assert http.post("/tasks/result", headers=auth(), json=result).status_code == 200
    verification = {
        "task_id": task["task_id"],
        "result_id": result_id,
        "verifier_id": "V",
        "verdict": "PASS",
        "artifacts": [],
    }
    assert (
        http.post("/tasks/verify", headers=verifier_auth(), json=verification).status_code
        == 200
    )


def test_logical_writer_scope_blocks_child_edge_without_hiding_unrelated_work():
    record = {"COLLISION_SCOPE": ["Ledger"]}
    tasks = [
        {"edge_name": "LEDGER/HANDOFF", "capabilities": []},
        {"edge_name": "PUBLICATION VERIFICATION", "capabilities": []},
    ]

    selected = continue_module.select_safe_frontier(record, tasks)

    assert [task["edge_name"] for task in selected] == ["PUBLICATION VERIFICATION"]


@pytest.mark.parametrize(
    "edge",
    [
        "SALES PACKAGE - SAFE_AUTOMATABLE_PREPARATION",
        "SALES PACKAGE-COMPLETE",
        "PUBLICATION VERIFICATION COMPLETE",
        "ONBOARD_FIRST_PILOT_CUSTOMER-COMPLETE",
    ],
)
def test_task_name_or_success_suffix_cannot_manufacture_success(edge, tmp_path):
    task = {"edge_name": edge, "instruction": f"Prove edge: {edge}"}

    _, success, blocker = continue_module.execute_task(
        task, tmp_path / "ledger.json", {}
    )

    assert success is False
    assert blocker


def test_waiting_a_does_not_stop_b_then_dependent_c_and_a_resumes_same_identity(
    motor,
):
    register(motor)
    goal_id = motor.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "A waits; B then C continue",
            "workflow_plan": [
                {
                    "task_id": "A",
                    "target_agent": "auto",
                    "instruction": "A",
                    "required_capabilities": ["X"],
                },
                {
                    "task_id": "B",
                    "target_agent": "auto",
                    "instruction": "B",
                    "required_capabilities": ["X"],
                },
                {
                    "task_id": "C",
                    "target_agent": "auto",
                    "instruction": "C",
                    "required_capabilities": ["X"],
                    "depends_on": ["B"],
                },
            ],
        },
    ).get_json()["goal_id"]

    task_a = claim(motor)
    assert task_a["task_id"] == "A"
    waited = motor.post(
        "/tasks/A/provider_wait",
        headers=auth(),
        json={"worker_id": "W", "reason": "quota"},
    )
    assert waited.get_json()["status"] == "WAITING_PROVIDER"

    task_b = claim(motor)
    assert task_b["task_id"] == "B"
    assert claim(motor) is None  # C is dependency-blocked while B is active.
    complete_and_verify(motor, task_b, "b")

    task_c = claim(motor)
    assert task_c["task_id"] == "C"
    complete_and_verify(motor, task_c, "c")

    state = server_app.load_state()
    state["tasks"]["A"]["next_retry_at"] = 0
    for step in state["goals"][goal_id]["workflow_plan"]:
        if step["task_id"] == "A":
            step["next_retry_at"] = 0
    server_app.save_state(state)

    resumed_a = claim(motor)
    assert resumed_a["task_id"] == "A"
    assert resumed_a["attempt_id"] == task_a["attempt_id"]
    assert resumed_a["dispatch_id"] == task_a["dispatch_id"]


def test_two_real_replenishment_cycles_do_not_false_done(motor, monkeypatch):
    register(motor)

    class TwoCyclePlanner:
        calls = 0

        def formulate_workflow_plan(self, goal_text, idea_type):
            assert goal_text == "two replenishment cycles"
            assert idea_type == "GOAL"
            type(self).calls += 1
            cycle = type(self).calls
            return f"workflow-{cycle}", [
                {
                    "task_id": f"R{cycle}",
                    "target_agent": "windows",
                    "instruction": f"replenished {cycle}",
                    "required_capabilities": ["X"],
                }
            ]

    monkeypatch.setattr(server_app, "ChiefCommander", TwoCyclePlanner)
    goal_id = motor.post(
        "/goals",
        headers=auth(),
        json={
            "goal_text": "two replenishment cycles",
            "terminal": False,
            "workflow_plan": [
                {
                    "task_id": "INITIAL",
                    "target_agent": "auto",
                    "instruction": "initial",
                    "required_capabilities": ["X"],
                }
            ],
        },
    ).get_json()["goal_id"]

    initial = claim(motor)
    assert initial["task_id"] == "INITIAL"
    complete_and_verify(motor, initial, "initial")
    assert server_app.load_state()["goals"][goal_id]["replenish_count"] == 1

    first_replenished = claim(motor)
    assert first_replenished["task_id"] == "R1"
    complete_and_verify(motor, first_replenished, "r1")

    goal = server_app.load_state()["goals"][goal_id]
    assert goal["replenish_count"] == 2
    assert goal["status"] == "ACTIVE"
    assert any(
        step["task_id"] == "R2" and step["status"] == "QUEUED"
        for step in goal["workflow_plan"]
    )


def test_stale_writer_is_fail_closed_not_clean_idle():
    record = {
        "STATUS": "DONE",
        "FIRST_CAUSAL_BLOCKER": "NONE",
        "CONTINUATION_CHECKPOINT": "none",
        "NEXT_EXECUTABLE_ACTION": "NONE",
        "CLEAN_IDLE": "YES",
        "QUEUE_INDEPENDENT": "YES",
        "ACTIVE_WRITERS": ["stale-or-unverified-writer"],
    }
    guard = {
        "transition_state": "CANONICAL_ACCEPTED",
        "binding": {},
        "evidence": [],
    }

    updates = continue_module.derive_frontier_updates(record, guard, [], [])

    assert updates["CLEAN_IDLE"] == "NO"
    assert updates["QUEUE_INDEPENDENT"] == "NO"
    assert updates["NEXT_EXECUTABLE_ACTION"].startswith("Reconcile active writers")
