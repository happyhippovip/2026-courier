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


def test_result_schema_boundary_enforces_artifact_keys():
    from scripts.integration_contract import validate_durable_result, ContractError
    import pytest
    
    # Valid artifact sets conforming to the exact contract
    valid_result = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "worker_id": "worker-1",
        "attempt_id": "attempt-1",
        "dispatch_id": "dispatch-1",
        "run_id": "run-1",
        "status": "SUCCESS",
        "result_id": "result-1",
        "artifacts": [
            {"path": "a.txt", "sha256": "a"*64},
            {"path": "b.txt", "sha256": "b"*64, "artifact_id": "art-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "size": 10},
            {"path": "c.txt", "sha256": "c"*64, "expected_sha256": "d"*64} # explicitly permitted by schema
        ]
    }
    
    # Should pass without raising
    task = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "worker_id": "worker-1",
        "attempt_id": "attempt-1",
        "dispatch_id": "dispatch-1",
    }
    validate_durable_result(task, valid_result)
    
    # Invalid artifact set: extra unauthorized key
    invalid_result = dict(valid_result)
    invalid_result["artifacts"] = [{"path": "a.txt", "sha256": "a"*64, "malicious_override": "true"}]
    
    with pytest.raises(ContractError, match="invalid artifact evidence"):
        validate_durable_result(task, invalid_result)

def test_result_id_changes_when_status_changes(tmp_path):
    from scripts.integration_contract import verify_result
    packet = task_packet()
    (tmp_path / packet['artifacts'][0]).write_text('SUCCESS\n', encoding='utf-8')
    
    raw_success = {
        'goal_id': packet['goal_id'],
        'task_id': packet['task_id'],
        'worker_id': packet['worker_id'],
        'attempt_id': packet['attempt_id'],
        'dispatch_id': packet['dispatch_id'],
        'run_id': 'run-1',
        'status': 'SUCCESS',
    }
    raw_failed = dict(raw_success, status='FAILED')
    
    res_success = verify_result(packet, raw_success, tmp_path)
    res_failed = verify_result(packet, raw_failed, tmp_path)
    
    assert res_success['result_id'] != res_failed['result_id']


def test_result_id_changes_when_artifact_changes(tmp_path):
    from scripts.integration_contract import verify_result
    packet = task_packet()
    (tmp_path / packet['artifacts'][0]).write_text('SUCCESS\n', encoding='utf-8')
    
    raw1 = {
        'goal_id': packet['goal_id'],
        'task_id': packet['task_id'],
        'worker_id': packet['worker_id'],
        'attempt_id': packet['attempt_id'],
        'dispatch_id': packet['dispatch_id'],
        'run_id': 'run-1',
        'status': 'SUCCESS',
    }
    
    res1 = verify_result(packet, raw1, tmp_path)
    
    # change artifact contents
    (tmp_path / packet['artifacts'][0]).write_text('DIFFERENT\n', encoding='utf-8')
    
    res2 = verify_result(packet, raw1, tmp_path)
    
    assert res1['result_id'] != res2['result_id']

