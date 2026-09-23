import json
import os
from pathlib import Path
import tempfile
import pytest

from scripts.account_switch import trigger_account_switch


class MockWorker:
    def __init__(self, current_task=None, owned_pids=None):
        self.current_task = current_task
        self.owned_pids = set(owned_pids or [])
        self.saved = False

    def save_state(self):
        self.saved = True


@pytest.fixture
def switch_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state_file = tdp / "central_state.json"
        session_file = tdp / "account_session.json"

        initial_state = {
            "goals": {
                "G-1": {
                    "workflow_plan": [
                        {"task_id": "T-ACTIVE", "status": "RUNNING"},
                        {"task_id": "T-PENDING", "status": "WAITING"},
                    ]
                }
            }
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)

        yield {
            "root": tdp,
            "state_file": state_file,
            "session_file": session_file,
        }


def test_account_switch_idle_worker(switch_env):
    worker = MockWorker(current_task=None)
    res = trigger_account_switch(
        worker,
        "NEW_ACCOUNT_A",
        state_file=str(switch_env["state_file"]),
        session_file=str(switch_env["session_file"]),
    )
    assert res["success"] is True
    assert res["active_account"] == "NEW_ACCOUNT_A"
    assert res["resumed_task"] is None

    # Check session file was written
    assert switch_env["session_file"].exists()
    with open(switch_env["session_file"], "r", encoding="utf-8") as f:
        sess = json.load(f)
    assert sess["active_account"] == "NEW_ACCOUNT_A"


def test_account_switch_active_task_transitions(switch_env):
    worker = MockWorker(
        current_task={"task_id": "T-ACTIVE"},
        owned_pids=[0, 1]  # Protected PIDs to ensure safety
    )
    res = trigger_account_switch(
        worker,
        "NEW_ACCOUNT_B",
        state_file=str(switch_env["state_file"]),
        session_file=str(switch_env["session_file"]),
    )
    assert res["success"] is True
    assert res["resumed_task"] == "T-ACTIVE"

    # Worker PIDs cleared and saved
    assert len(worker.owned_pids) == 0
    assert worker.saved is True

    # State file task should be resumed to RUNNING with checkpoint history
    with open(switch_env["state_file"], "r", encoding="utf-8") as f:
        state = json.load(f)
    task = state["goals"]["G-1"]["workflow_plan"][0]
    assert task["status"] == "RUNNING"
    assert "checkpoint_timestamp" in task
    assert "resumed_at" in task
    assert "provider_failure_reason" not in task


def test_account_switch_null_worker(switch_env):
    res = trigger_account_switch(
        None,
        "ACCOUNT_FALLBACK",
        state_file=str(switch_env["state_file"]),
        session_file=str(switch_env["session_file"]),
    )
    assert res["success"] is True
    assert res["active_account"] == "ACCOUNT_FALLBACK"
