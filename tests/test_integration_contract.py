import json
from pathlib import Path

import pytest

from scripts.integration_contract import ContractError, prepare_task, verify_result
from scripts import courier_control_plane


def task_packet(**overrides):
    task = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "description": "create the bounded artifact",
        "target_capability": "github",
        "status": "QUEUED",
    }
    task.update(overrides)
    return prepare_task(task)


def test_task_packet_has_common_identity():
    packet = task_packet()

    assert packet["attempt_id"] == "task-1:attempt:1"
    assert packet["dispatch_id"].startswith("dispatch-")
    assert packet["worker_id"] == "GITHUB-HOSTED"
    assert packet["run_id"] is None
    assert packet["result_id"] is None
    assert packet["artifacts"] == ["courier_canary_task-1.txt"]


def test_verified_result_binds_identity_and_artifact(tmp_path: Path):
    packet = task_packet()
    artifact = tmp_path / packet["artifacts"][0]
    artifact.write_text("SUCCESS\n", encoding="utf-8")

    result = verify_result(
        packet,
        {
            "goal_id": packet["goal_id"],
            "task_id": packet["task_id"],
            "worker_id": packet["worker_id"],
            "run_id": "35023245538",
            "status": "SUCCESS",
        },
        tmp_path,
    )

    assert result["goal_id"] == packet["goal_id"]
    assert result["attempt_id"] == packet["attempt_id"]
    assert result["dispatch_id"] == packet["dispatch_id"]
    assert result["run_id"] == "35023245538"
    assert result["result_id"].startswith("result-")
    assert result["artifacts"][0]["path"] == artifact.name
    assert len(result["artifacts"][0]["sha256"]) == 64


@pytest.mark.parametrize(
    "field,value",
    [
        ("goal_id", "wrong-goal"),
        ("task_id", "wrong-task"),
        ("worker_id", "wrong-worker"),
        ("run_id", ""),
    ],
)
def test_result_identity_mismatch_fails_closed(tmp_path: Path, field: str, value: str):
    packet = task_packet()
    (tmp_path / packet["artifacts"][0]).write_text("SUCCESS\n", encoding="utf-8")
    raw = {
        "goal_id": packet["goal_id"],
        "task_id": packet["task_id"],
        "worker_id": packet["worker_id"],
        "run_id": "run-1",
        "status": "SUCCESS",
    }
    raw[field] = value

    with pytest.raises(ContractError):
        verify_result(packet, raw, tmp_path)


def test_success_without_effect_fails_closed(tmp_path: Path):
    packet = task_packet()
    raw = {
        "goal_id": packet["goal_id"],
        "task_id": packet["task_id"],
        "worker_id": packet["worker_id"],
        "run_id": "run-1",
        "status": "SUCCESS",
    }

    with pytest.raises(ContractError, match="missing expected artifact"):
        verify_result(packet, raw, tmp_path)


def test_result_id_is_idempotent_for_same_observation(tmp_path: Path):
    packet = task_packet()
    (tmp_path / packet["artifacts"][0]).write_text("SUCCESS\n", encoding="utf-8")
    raw = {
        "goal_id": packet["goal_id"],
        "task_id": packet["task_id"],
        "worker_id": packet["worker_id"],
        "run_id": "run-1",
        "status": "SUCCESS",
    }

    first = verify_result(packet, raw, tmp_path)
    second = verify_result(packet, json.loads(json.dumps(raw)), tmp_path)

    assert first["result_id"] == second["result_id"]


def test_control_plane_reconciles_only_verified_effect(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packet = task_packet(status="DISPATCHED")
    artifact = tmp_path / packet["artifacts"][0]
    artifact.write_text("SUCCESS\n", encoding="utf-8")
    incoming = tmp_path / "results" / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "result.json").write_text(
        json.dumps(
            {
                "goal_id": packet["goal_id"],
                "task_id": packet["task_id"],
                "worker_id": packet["worker_id"],
                "run_id": "run-1",
                "status": "SUCCESS",
            }
        ),
        encoding="utf-8",
    )
    state = {
        "goals": {packet["goal_id"]: {"goal_id": packet["goal_id"], "status": "ACTIVE"}},
        "tasks": {packet["task_id"]: packet},
    }

    courier_control_plane.process_results(state)

    completed = state["tasks"][packet["task_id"]]
    assert completed["status"] == "RECONCILED"
    assert completed["result_id"].startswith("result-")
    assert len(list((tmp_path / "results" / "processed").glob("*.json"))) == 1


def test_duplicate_result_cannot_regress_terminal_task(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packet = task_packet(status="RECONCILED")
    incoming = tmp_path / "results" / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "duplicate.json").write_text(
        json.dumps(
            {
                "goal_id": packet["goal_id"],
                "task_id": packet["task_id"],
                "worker_id": packet["worker_id"],
                "run_id": "run-1",
                "status": "SUCCESS",
            }
        ),
        encoding="utf-8",
    )
    state = {
        "goals": {packet["goal_id"]: {"goal_id": packet["goal_id"], "status": "ACTIVE"}},
        "tasks": {packet["task_id"]: packet},
    }

    courier_control_plane.process_results(state)

    assert state["tasks"][packet["task_id"]]["status"] == "RECONCILED"


def test_missing_effect_blocks_goal_and_prevents_succession(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    packet = task_packet(status="DISPATCHED")
    incoming = tmp_path / "results" / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "result.json").write_text(
        json.dumps(
            {
                "goal_id": packet["goal_id"],
                "task_id": packet["task_id"],
                "worker_id": packet["worker_id"],
                "run_id": "run-1",
                "status": "SUCCESS",
            }
        ),
        encoding="utf-8",
    )
    state = {
        "goals": {packet["goal_id"]: {"goal_id": packet["goal_id"], "status": "ACTIVE"}},
        "tasks": {packet["task_id"]: packet},
    }

    courier_control_plane.process_results(state)

    assert state["tasks"][packet["task_id"]]["status"] == "FAILED_VERIFICATION"
    assert state["goals"][packet["goal_id"]]["status"] == "BLOCKED"
    assert len(list((tmp_path / "results" / "rejected").glob("*.json"))) == 1


def test_dispatch_persists_identity_before_worker_start(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(courier_control_plane, "STATE_FILE", str(tmp_path / "state.json"))
    observed = {}

    def fake_popen(command):
        observed["command"] = command
        observed["state"] = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))

    monkeypatch.setattr(courier_control_plane.subprocess, "Popen", fake_popen)
    packet = task_packet()
    state = {
        "goals": {packet["goal_id"]: {"goal_id": packet["goal_id"], "status": "ACTIVE"}},
        "tasks": {packet["task_id"]: packet},
    }

    courier_control_plane.dispatch_task(packet, state)

    persisted = observed["state"]["tasks"][packet["task_id"]]
    assert persisted["status"] == "DISPATCHED"
    assert persisted["dispatch_id"] == packet["dispatch_id"]
    assert observed["command"][1] == "scripts/github_worker_adapter.py"


def test_verified_result_drives_automatic_successor_and_goal_done(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(courier_control_plane, "STATE_FILE", str(tmp_path / "state.json"))
    dispatched = []

    def bounded_dispatch(task, state):
        task.update(prepare_task(task))
        task["status"] = "DISPATCHED"
        dispatched.append(task["task_id"])
        courier_control_plane.save_state(state)

    monkeypatch.setattr(courier_control_plane, "dispatch_task", bounded_dispatch)
    goal_id = "goal-chain"
    state = {
        "goals": {
            goal_id: {
                "goal_id": goal_id,
                "goal_text": "bounded two-step chain",
                "status": "ACTIVE",
                "current_step_index": 0,
                "workflow_plan": [
                    {
                        "goal_id": goal_id,
                        "task_id": "task-a",
                        "description": "first bounded effect",
                        "target_capability": "github",
                        "status": "QUEUED",
                    },
                    {
                        "goal_id": goal_id,
                        "task_id": "task-b",
                        "description": "second bounded effect",
                        "target_capability": "mac",
                        "status": "QUEUED",
                    },
                ],
            }
        },
        "tasks": {},
    }
    courier_control_plane.save_state(state)

    courier_control_plane.loop()
    assert dispatched == ["task-a"]

    for task_id in ("task-a", "task-b"):
        state = courier_control_plane.load_state()
        task = state["tasks"][task_id]
        (tmp_path / task["artifacts"][0]).write_text("SUCCESS\n", encoding="utf-8")
        incoming = tmp_path / "results" / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        (incoming / f"{task_id}.json").write_text(
            json.dumps(
                {
                    "goal_id": goal_id,
                    "task_id": task_id,
                    "worker_id": task["worker_id"],
                    "run_id": f"run-{task_id}",
                    "status": "SUCCESS",
                }
            ),
            encoding="utf-8",
        )
        courier_control_plane.loop()

    final = courier_control_plane.load_state()
    assert dispatched == ["task-a", "task-b"]
    assert final["tasks"]["task-a"]["status"] == "RECONCILED"
    assert final["tasks"]["task-b"]["status"] == "RECONCILED"
    assert final["goals"][goal_id]["status"] == "DONE"
