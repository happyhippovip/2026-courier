import json
from pathlib import Path

import pytest

from scripts import github_worker_adapter as adapter


def packet(**overrides):
    result = {
        "goal_id": "goal-1", "task_id": "task-1", "attempt_id": "task-1:attempt:1",
        "dispatch_id": "dispatch-1", "worker_id": "GITHUB-HOSTED",
        "task_type": "deterministic_transform", "input": "nonce",
    }
    result.update(overrides)
    return result


def test_validate_task_rejects_unsupported_or_missing_identity():
    with pytest.raises(ValueError, match="unsupported"):
        adapter.validate_task(packet(task_type="shell"))
    with pytest.raises(ValueError, match="task_id"):
        adapter.validate_task(packet(task_id=""))


def test_completed_exact_artifact_is_posted_and_persisted(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    posted = []
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 1)
    monkeypatch.setattr(
        adapter, "run_cmd",
        lambda command: (0, "happyhippovip-github-worker-reality" if command[:3] == ["git", "branch", "--show-current"] else "", ""),
    )
    monkeypatch.setattr(adapter, "find_run", lambda dispatch_id: ("123", "completed"))
    monkeypatch.setattr(adapter, "download_exact_result", lambda run_id, dispatch_id, destination: {
        **packet(), "run_id": "123", "result_id": "result-dispatch-1", "status": "SUCCESS",
        "artifacts": [{"path": "courier_output_dispatch-1.json", "sha256": "a" * 64}],
    })
    monkeypatch.setattr(adapter, "post_result", posted.append)

    assert adapter.run(str(task_file)) == 0
    assert posted[0]["dispatch_id"] == "dispatch-1"
    assert json.loads(adapter.state_path(task_file).read_text())["status"] == "POSTED"


def test_running_worker_persists_waiting_not_failed(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(
        adapter, "run_cmd",
        lambda command: (0, "happyhippovip-github-worker-reality" if command[:3] == ["git", "branch", "--show-current"] else "", ""),
    )

    assert adapter.run(str(task_file)) == 0
    state = json.loads(adapter.state_path(task_file).read_text())
    assert state["status"] == "WAITING_FOR_WORKER"
