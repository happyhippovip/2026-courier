import json
from pathlib import Path

import pytest

from scripts.integration_contract import ContractError, prepare_task, verify_result


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
            "attempt_id": packet["attempt_id"],
            "dispatch_id": packet["dispatch_id"],
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
        "attempt_id": packet["attempt_id"],
        "dispatch_id": packet["dispatch_id"],
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
        "attempt_id": packet["attempt_id"],
        "dispatch_id": packet["dispatch_id"],
        "run_id": "run-1",
        "status": "SUCCESS",
    }

    first = verify_result(packet, raw, tmp_path)
    second = verify_result(packet, json.loads(json.dumps(raw)), tmp_path)

    assert first["result_id"] == second["result_id"]


def test_antigravity_capability_binds_to_mac_worker():
    packet = task_packet(target_capability="antigravity")
    assert packet["target_capability"] == "antigravity"
    assert packet["worker_id"] == "MAC-01"
    assert packet["dispatch_id"].startswith("dispatch-")
