from pathlib import Path

import pytest

from scripts.integration_contract import ContractError, prepare_task, verify_result


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


@pytest.mark.parametrize("field", ["attempt_id", "dispatch_id"])
def test_prior_attempt_or_dispatch_evidence_fails_closed(tmp_path: Path, field: str):
    task = dispatched_task()
    (tmp_path / "effect.txt").write_text("observed effect\n", encoding="utf-8")
    stale = observed_result(task)
    stale[field] = f"prior-{field}"

    with pytest.raises(ContractError, match=f"{field} mismatch"):
        verify_result(task, stale, tmp_path)
