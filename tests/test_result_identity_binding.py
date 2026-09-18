from pathlib import Path

import pytest

from scripts.integration_contract import (
    ContractError,
    prepare_task,
    validate_durable_result,
    verify_result,
)


def dispatched_task() -> dict:
    task = prepare_task({
        "goal_id": "goal-identity",
        "task_id": "task-identity",
        "target_capability": "github",
        "status": "DISPATCHED",
        "artifacts": ["effect.txt"],
    })
    return task


def observed_result(task: dict) -> dict:
    return {
        "goal_id": task["goal_id"],
        "task_id": task["task_id"],
        "attempt_id": task["attempt_id"],
        "dispatch_id": task["dispatch_id"],
        "execution_ref": task.get("execution_ref", "exec-mock"),
        "worker_id": task["worker_id"],
        "run_id": "observable-run-42",
        "status": "SUCCESS",
    }


def test_verified_effect_is_bound_to_exact_attempt_and_dispatch(tmp_path: Path):
    task = dispatched_task()
    (tmp_path / "effect.txt").write_text("observed effect\n", encoding="utf-8")

    result = verify_result(task, observed_result(task), tmp_path)

    assert result["attempt_id"] == task["attempt_id"]
    assert result["dispatch_id"] == task["dispatch_id"]


@pytest.mark.parametrize(
    "field",
    ["goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id"],
)
def test_wrong_execution_identity_fails_closed(tmp_path: Path, field: str):
    task = dispatched_task()
    (tmp_path / "effect.txt").write_text("observed effect\n", encoding="utf-8")
    stale = observed_result(task)
    stale[field] = f"prior-{field}"

    with pytest.raises(ContractError, match=f"{field} mismatch"):
        verify_result(task, stale, tmp_path)


@pytest.mark.parametrize(
    "field",
    ["goal_id", "task_id", "attempt_id", "dispatch_id", "execution_ref", "worker_id"],
)
def test_remote_durable_result_must_match_complete_dispatch_identity(
    tmp_path: Path, field: str
):
    task = dispatched_task()
    (tmp_path / "effect.txt").write_text("observed effect\n", encoding="utf-8")
    result = verify_result(task, observed_result(task), tmp_path)
    result[field] = f"wrong-{field}"

    with pytest.raises(ContractError, match=f"{field} mismatch"):
        validate_durable_result(task, result)


def test_batch_and_prompt_identity_are_bound_when_present(tmp_path: Path):
    task = dispatched_task()
    task["batch_id"] = "batch-1"
    task["prompt_id"] = "prompt-1"
    raw = observed_result(task)
    raw["batch_id"] = "batch-1"
    raw["prompt_id"] = "prompt-1"
    (tmp_path / "effect.txt").write_text("observed effect\n", encoding="utf-8")

    result = verify_result(task, raw, tmp_path)
    assert validate_durable_result(task, result)["batch_id"] == "batch-1"

    result["prompt_id"] = "stale-prompt"
    with pytest.raises(ContractError, match="prompt_id mismatch"):
        validate_durable_result(task, result)
