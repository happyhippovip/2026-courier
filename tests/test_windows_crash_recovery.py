import json
import os
import tempfile
import pytest

from scripts.windows_crash_recovery import recover_worker, main


def test_recover_worker_no_state():
    with tempfile.TemporaryDirectory() as tmp_dir:
        non_existent = os.path.join(tmp_dir, "does_not_exist.json")
        result = recover_worker(non_existent)
        assert result["status"] == "NO_STATE"
        assert result["action"] == "NONE"


def test_recover_worker_corrupt_state():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "worker_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json")

        result = recover_worker(state_file)
        assert result["status"] == "CORRUPT_STATE"
        assert result["action"] == "QUARANTINED"
        assert not os.path.exists(state_file)
        # Check that quarantine file was created
        files = os.listdir(tmp_dir)
        assert any(f.startswith("worker_state.json.corrupt.") for f in files)


def test_recover_worker_idle():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "worker_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"current_task": None, "owned_pids": []}, f)

        result = recover_worker(state_file)
        assert result["status"] == "IDLE"
        assert result["action"] == "NONE"


@pytest.mark.parametrize(
    "phase,expected_action",
    [
        ("PRE_EFFECT", "RE_QUEUE"),
        ("ARTIFACT_CREATED", "RESUME_ARTIFACT"),
        ("POST_EXTERNAL_EFFECT", "FAIL_CLOSED"),
        ("POST_RESULT", "ACK_SERVER_RESULT"),
        ("UNKNOWN_PHASE", "FAIL_CLOSED"),
    ],
)
def test_recover_worker_phases(phase, expected_action):
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "worker_state.json")
        initial_state = {
            "current_task": {
                "task_id": "TASK-123",
                "execution_ref": "exec_WIN_TASK-123",
                "phase": phase,
            },
            "owned_pids": [],
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)

        result = recover_worker(state_file)
        assert result["status"] == "RECOVERED"
        assert result["task_id"] == "TASK-123"
        assert result["phase"] == phase
        assert result["action"] == expected_action

        # Verify that state was cleared and written atomically
        with open(state_file, "r", encoding="utf-8") as f:
            updated_state = json.load(f)
        assert updated_state["current_task"] is None
        assert updated_state["owned_pids"] == []


def test_windows_crash_recovery_demo_cli(capsys):
    import sys
    orig_argv = sys.argv
    try:
        sys.argv = ["windows_crash_recovery.py", "--demo"]
        main()
        captured = capsys.readouterr()
        assert "Simulating crash in phase: PRE_EFFECT" in captured.out
        assert "Simulating crash in phase: ARTIFACT_CREATED" in captured.out
        assert "Simulating crash in phase: POST_EXTERNAL_EFFECT" in captured.out
        assert "Simulating crash in phase: POST_RESULT" in captured.out
    finally:
        sys.argv = orig_argv
