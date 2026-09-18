from pathlib import Path

import pytest

from scripts.integration_contract import ContractError, prepare_task, verify_result


def base_task(**changes):
    task = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "target_capability": "mac",
    }
    task.update(changes)
    return task


def test_legacy_capability_maps_to_canonical_worker_identity():
    packet = prepare_task(base_task())

    assert packet["worker_id"] == "MAC-01"
    assert packet["attempt_id"] == "task-1:attempt:1"
    assert packet["dispatch_id"].startswith("dispatch-")
    assert packet["execution_ref"].startswith("exec-")
    assert packet["status"] == "QUEUED"


def test_unknown_capability_requires_explicit_worker_identity():
    with pytest.raises(ContractError, match="worker_id is required"):
        prepare_task(base_task(target_capability="future-capability"))

    packet = prepare_task(
        base_task(target_capability="future-capability", worker_id="FUTURE-01")
    )
    assert packet["worker_id"] == "FUTURE-01"


@pytest.mark.parametrize("field", ["goal_id", "task_id", "target_capability"])
def test_missing_required_task_identity_fails_closed(field):
    with pytest.raises(ContractError, match="required"):
        prepare_task(base_task(**{field: ""}))


def test_invalid_task_state_fails_closed():
    with pytest.raises(ContractError, match="invalid task status"):
        prepare_task(base_task(status="DONE_BY_WORKER"))


def test_existing_attempt_dispatch_and_execution_identity_are_preserved():
    packet = prepare_task(
        base_task(
            attempt_id="attempt-existing",
            dispatch_id="dispatch-existing",
            execution_ref="execution-existing",
        )
    )

    assert packet["attempt_id"] == "attempt-existing"
    assert packet["dispatch_id"] == "dispatch-existing"
    assert packet["execution_ref"] == "execution-existing"


@pytest.mark.parametrize("field", ["attempt_id", "dispatch_id", "execution_ref"])
def test_explicitly_empty_execution_identity_fails_closed(field):
    with pytest.raises(ContractError, match=f"{field} is required"):
        prepare_task(base_task(**{field: ""}))


def test_success_artifact_symlink_cannot_escape_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("not workspace evidence", encoding="utf-8")
    (workspace / "evidence.txt").symlink_to(outside)
    task = prepare_task(base_task(artifacts=["evidence.txt"]))
    result = {
        **{field: task[field] for field in (
            "goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id"
        )},
        "run_id": "run-1",
        "status": "SUCCESS",
    }

    with pytest.raises(ContractError, match="missing expected artifact"):
        verify_result(task, result, workspace)
