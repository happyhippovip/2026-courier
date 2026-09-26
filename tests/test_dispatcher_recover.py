"""Deterministic recovery-path tests for courier_github_dispatcher.

recover_adapters() decides which durable dispatch to resume after a
dispatcher restart. The adapter launcher is stubbed: these tests pin the
selection/validation decisions, not process spawning.
"""
import json
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts import courier_github_dispatcher


def _write_task(tmp_path, dispatch_id, task_id, extra=None):
    task = {"dispatch_id": dispatch_id, "task_id": task_id}
    if extra:
        task.update(extra)
    path = Path(
        courier_github_dispatcher.task_file_path(task).replace(
            __import__("tempfile").gettempdir(), str(tmp_path)
        )
    )
    path.write_text(json.dumps(task), encoding="utf-8")
    return task, str(path)


def test_recover_single_task_launches_once(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        task, path = _write_task(tmp_path, "dispatch-r1", "task-r1")
        with mock.patch.object(
            courier_github_dispatcher, "launch_adapter", return_value=object()
        ) as launch:
            recovered = courier_github_dispatcher.recover_adapters()
        assert list(recovered) == ["task-r1"]
        assert recovered["task-r1"]["task_file"] == path
        assert recovered["task-r1"]["retries"] == 0
        launch.assert_called_once_with(path)


def test_recover_posted_state_cleans_up(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        task, path = _write_task(tmp_path, "dispatch-r2", "task-r2")
        state = Path(path).with_name(
            f"{Path(path).stem}.github-worker-state.json"
        )
        state.write_text(json.dumps({"status": "POSTED"}), encoding="utf-8")
        with mock.patch.object(
            courier_github_dispatcher, "launch_adapter"
        ) as launch:
            recovered = courier_github_dispatcher.recover_adapters()
        assert recovered == {}
        assert not Path(path).exists()
        assert not state.exists()
        launch.assert_not_called()


def test_recover_invalid_task_refuses_startup(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        bad = tmp_path / "courier-github-deadbeef.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(RuntimeError, match="invalid persisted GitHub task"):
            courier_github_dispatcher.recover_adapters()


def test_recover_multiple_tasks_requires_reconciliation(tmp_path):
    with mock.patch("tempfile.gettempdir", return_value=str(tmp_path)):
        _write_task(tmp_path, "dispatch-r3", "task-r3")
        _write_task(tmp_path, "dispatch-r4", "task-r4")
        with pytest.raises(RuntimeError, match="require reconciliation"):
            courier_github_dispatcher.recover_adapters()
