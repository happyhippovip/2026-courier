import os
import sys
import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.orphan_task_reaper import (
    get_canonical_state_path,
    get_worker_state_path,
    atomic_save_json,
    safely_terminate_pid,
    check_task_health,
)


def test_path_resolution(tmp_path, monkeypatch):
    custom_state = tmp_path / "custom_state.json"
    custom_state.write_text("{}")
    assert get_canonical_state_path(str(custom_state)) == custom_state.resolve()

    monkeypatch.setenv("COURIER_STATE_FILE", str(custom_state))
    assert get_canonical_state_path() == custom_state.resolve()

    custom_worker = tmp_path / "custom_worker.json"
    custom_worker.write_text("{}")
    assert get_worker_state_path(str(custom_worker)) == custom_worker.resolve()

    monkeypatch.setenv("COURIER_WORKER_STATE_FILE", str(custom_worker))
    assert get_worker_state_path() == custom_worker.resolve()


def test_atomic_save_json(tmp_path):
    target = tmp_path / "state.json"
    data = {"status": "ok", "count": 42}
    atomic_save_json(target, data)
    assert target.exists()
    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data

    # Verify no tmp files leftover
    tmp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(tmp_files) == 0


def test_safely_terminate_pid_guards():
    # Never terminate PID 0 or 1
    assert safely_terminate_pid(0) is False
    assert safely_terminate_pid(1) is False
    assert safely_terminate_pid(-5) is False
    assert safely_terminate_pid("invalid") is False

    # Never terminate self or parent
    assert safely_terminate_pid(os.getpid()) is False
    assert safely_terminate_pid(os.getppid()) is False


def test_safely_terminate_pid_mock():
    mock_proc = MagicMock()
    mock_child = MagicMock()
    mock_proc.children.return_value = [mock_child]

    with patch("psutil.Process", return_value=mock_proc):
        assert safely_terminate_pid(99999) is True
        mock_child.terminate.assert_called_once()
        mock_proc.terminate.assert_called_once()


def test_check_task_health_valid_running(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "G1": {
                "workflow_plan": [
                    {"task_id": "TASK-123", "status": "RUNNING"}
                ]
            }
        }
    }))

    worker_file = tmp_path / "worker_state.json"
    worker_file.write_text(json.dumps({
        "current_task": {"task_id": "TASK-123"},
        "owned_pids": [99999],
        "last_heartbeat": time.time()
    }))

    res = check_task_health(str(state_file), str(worker_file))
    assert res["cleaned"] is False
    assert res["orphaned_task_id"] is None

    # Verify worker file unchanged
    with open(worker_file) as f:
        w = json.load(f)
    assert w["current_task"]["task_id"] == "TASK-123"


def test_check_task_health_orphaned_missing_canonical(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "G1": {
                "workflow_plan": [
                    {"task_id": "TASK-DIFFERENT", "status": "RUNNING"}
                ]
            }
        }
    }))

    worker_file = tmp_path / "worker_state.json"
    worker_file.write_text(json.dumps({
        "current_task": {"task_id": "TASK-ORPHANED"},
        "owned_pids": [99999],
        "last_heartbeat": time.time()
    }))

    with patch("scripts.orphan_task_reaper.safely_terminate_pid", return_value=True):
        res = check_task_health(str(state_file), str(worker_file))

    assert res["cleaned"] is True
    assert res["orphaned_task_id"] == "TASK-ORPHANED"
    assert 99999 in res["terminated_pids"]

    # Verify worker state cleaned
    with open(worker_file) as f:
        w = json.load(f)
    assert w["current_task"] is None
    assert w["owned_pids"] == []
    assert "Cleaned orphaned task" in w["cleanup_evidence"]


def test_check_task_health_orphaned_stale_heartbeat(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text(json.dumps({
        "goals": {
            "G1": {
                "workflow_plan": [
                    {"task_id": "TASK-STALE", "status": "RUNNING"}
                ]
            }
        }
    }))

    worker_file = tmp_path / "worker_state.json"
    worker_file.write_text(json.dumps({
        "current_task": {"task_id": "TASK-STALE"},
        "owned_pids": [],
        "last_heartbeat": time.time() - 400  # >300s
    }))

    res = check_task_health(str(state_file), str(worker_file))
    assert res["cleaned"] is True
    assert res["orphaned_task_id"] == "TASK-STALE"


def test_check_task_health_corrupt_worker_json(tmp_path):
    state_file = tmp_path / "central_state.json"
    state_file.write_text("{}")
    worker_file = tmp_path / "worker_state.json"
    worker_file.write_text("{broken json...")

    res = check_task_health(str(state_file), str(worker_file))
    assert res["cleaned"] is False
    assert "error" in res
