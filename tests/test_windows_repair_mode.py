import json
import os
from pathlib import Path
import tempfile
import pytest

from scripts.windows_repair_mode import WindowsRepairUtility


@pytest.fixture
def temp_repair_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state_file = tdp / "central_state.json"
        worker_state_file = tdp / "worker_state.json"
        env_file = tdp / ".env.txt"

        initial_state = {
            "goals": {
                "g1": {"workflow_plan": [{"task_id": "t1", "status": "RUNNING"}]}
            },
            "schema_version": "1.0.0",
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)

        initial_worker = {
            "worker_id": "WIN_TEST_01",
            "owned_pids": [],
            "ui_handles": ["handle_001"],
            "active_ui_handle": "handle_001",
        }
        with open(worker_state_file, "w", encoding="utf-8") as f:
            json.dump(initial_worker, f)

        with open(env_file, "w", encoding="utf-8") as f:
            f.write("COURIER_API_KEY=dummy-token-1234\n")

        yield {
            "root": tdp,
            "state_file": state_file,
            "worker_state_file": worker_state_file,
            "env_file": env_file,
        }


def test_credential_check_file(temp_repair_env):
    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    assert repair.check_credential_access() is True


def test_credential_check_missing_env(temp_repair_env, monkeypatch):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    monkeypatch.delenv("COURIER_VERIFIER_API_KEY", raising=False)
    temp_repair_env["env_file"].unlink()

    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    # With no env file, no env vars, and no keyring, returns False without crashing
    assert repair.check_credential_access() is False


def test_state_schema_valid(temp_repair_env):
    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    assert repair.check_state_schema() is True


def test_state_schema_missing_creates_safe_schema(temp_repair_env):
    temp_repair_env["state_file"].unlink()
    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    assert repair.check_state_schema() is True
    assert temp_repair_env["state_file"].exists()

    with open(temp_repair_env["state_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "goals" in data
    assert "tasks" in data


def test_state_schema_corrupt_creates_backup_and_safe_state(temp_repair_env):
    with open(temp_repair_env["state_file"], "w", encoding="utf-8") as f:
        f.write("{corrupt unparseable json...")

    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    assert repair.check_state_schema() is True

    # State file is now valid JSON with default structure
    with open(temp_repair_env["state_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "goals" in data
    assert data.get("recovered_from_corruption") is True

    # Backup snapshot of corrupt state was preserved
    corrupt_snapshots = list(temp_repair_env["root"].glob("*corrupt*.json"))
    assert len(corrupt_snapshots) >= 1


def test_state_schema_missing_goals_key_repaired(temp_repair_env):
    with open(temp_repair_env["state_file"], "w", encoding="utf-8") as f:
        json.dump({"schema_version": "1.0.0"}, f)

    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    assert repair.check_state_schema() is True

    with open(temp_repair_env["state_file"], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "goals" in data
    assert data["schema_version"] == "1.0.0"


def test_remove_stale_ui_handles(temp_repair_env):
    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    cleared = repair.remove_stale_ui_handles()
    assert cleared >= 1

    with open(temp_repair_env["worker_state_file"], "r", encoding="utf-8") as f:
        wdata = json.load(f)
    assert wdata["ui_handles"] == []
    assert wdata["active_ui_handle"] is None


def test_safe_orphan_executions_cleanup(temp_repair_env):
    # Put protected PIDs (0, 1, self) in owned_pids
    with open(temp_repair_env["worker_state_file"], "w", encoding="utf-8") as f:
        json.dump({"owned_pids": [0, 1, os.getpid()]}, f)

    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    # None of the protected PIDs should be terminated
    cleaned = repair.clean_orphaned_executions()
    assert cleaned == 0

    with open(temp_repair_env["worker_state_file"], "r", encoding="utf-8") as f:
        wdata = json.load(f)
    assert wdata["owned_pids"] == []


def test_end_to_end_repair_run(temp_repair_env):
    repair = WindowsRepairUtility(
        state_file=str(temp_repair_env["state_file"]),
        worker_state_file=str(temp_repair_env["worker_state_file"]),
        env_file=str(temp_repair_env["env_file"]),
    )
    res = repair.run()
    assert res["success"] is True
    assert res["credentials"] is True
    assert res["state_schema"] is True
    assert res["worker_registration"] is True
    assert res["health_check"] is True
