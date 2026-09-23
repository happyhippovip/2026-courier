import json
import os
from pathlib import Path
import tempfile
import pytest

from scripts.windows_crash_recovery import recover_worker


def test_recover_missing_worker_state():
    with tempfile.TemporaryDirectory() as td:
        missing = Path(td) / "missing_worker.json"
        res = recover_worker(worker_state_file=str(missing))
        assert res["recovered"] is False
        assert res["action"] == "NOOP"


def test_recover_corrupt_worker_state():
    with tempfile.TemporaryDirectory() as td:
        corrupt = Path(td) / "worker_state.json"
        with open(corrupt, "w", encoding="utf-8") as f:
            f.write("{invalid json...")
        res = recover_worker(worker_state_file=str(corrupt))
        assert res["recovered"] is False
        assert res["action"] == "FAIL_CLOSED"


def test_recover_idle_worker():
    with tempfile.TemporaryDirectory() as td:
        wfile = Path(td) / "worker_state.json"
        with open(wfile, "w", encoding="utf-8") as f:
            json.dump({"current_task": None, "owned_pids": []}, f)
        res = recover_worker(worker_state_file=str(wfile))
        assert res["recovered"] is True
        assert res["action"] == "IDLE_NOOP"


@pytest.mark.parametrize(
    "phase,expected_action",
    [
        ("PRE_EFFECT", "REQUEUE"),
        ("ARTIFACT_CREATED", "RESUME_ARTIFACT"),
        ("POST_EXTERNAL_EFFECT", "FAIL_CLOSED_HUMAN_GATE"),
        ("POST_RESULT", "ACKNOWLEDGE_RESULT"),
        ("UNEXPECTED_PHASE", "FAIL_CLOSED_UNKNOWN"),
    ],
)
def test_recover_crash_phases(phase, expected_action):
    with tempfile.TemporaryDirectory() as td:
        wfile = Path(td) / "worker_state.json"
        state = {
            "current_task": {
                "task_id": "T-100",
                "execution_ref": "exec_win_01",
                "phase": phase,
            },
            "owned_pids": [0, 1],  # Protected PIDs should be skipped safely
        }
        with open(wfile, "w", encoding="utf-8") as f:
            json.dump(state, f)

        res = recover_worker(worker_state_file=str(wfile))
        assert res["recovered"] is True
        assert res["action"] == expected_action
        assert res["task_id"] == "T-100"

        # Worker state cleared and last_recovery logged
        with open(wfile, "r", encoding="utf-8") as f:
            updated = json.load(f)
        assert updated["current_task"] is None
        assert updated["owned_pids"] == []
        assert updated["last_recovery"]["action"] == expected_action
        assert updated["last_recovery"]["recovered_task_id"] == "T-100"
