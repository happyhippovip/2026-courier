import json
import os
from pathlib import Path
import tempfile
import pytest

from scripts.windows_update_manager import WindowsUpdateManager


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state_file = tdp / "central_state.json"
        backup_dir = tdp / "backup"
        
        initial_state = {
            "goals": {
                "g1": {"workflow_plan": [{"task_id": "t1", "status": "RUNNING"}]}
            },
            "schema_version": "1.0.0"
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(initial_state, f)
            
        yield {
            "root": tdp,
            "state_file": state_file,
            "backup_dir": backup_dir,
            "initial_state": initial_state,
        }


def test_detect_version(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    assert mgr.detect_version() == "1.0.0"


def test_schema_compatibility(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.2.0"
    )
    mgr.detect_version()
    assert mgr.schema_compatibility_check() is True

    # Major version downgrade should fail
    mgr.target_version = "0.9.0"
    assert mgr.schema_compatibility_check() is False


def test_checkpoint_creates_manifest(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    count = mgr.checkpoint_state()
    assert count >= 1
    assert temp_env["backup_dir"].exists()

    manifest_file = temp_env["backup_dir"] / "manifest.json"
    assert manifest_file.exists()
    with open(manifest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "manifest" in data
    assert "central_state.json" in data["manifest"]
    assert data["manifest"]["central_state.json"] == str(temp_env["state_file"].resolve())


def test_migrate_schema_idempotent(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    assert mgr.migrate_schema() is True

    with open(temp_env["state_file"], "r", encoding="utf-8") as f:
        migrated = json.load(f)
    assert migrated["schema_version"] == "1.1.0"
    assert "updated_at" in migrated

    # Run again: should stay 1.1.0
    assert mgr.migrate_schema() is True
    with open(temp_env["state_file"], "r", encoding="utf-8") as f:
        second = json.load(f)
    assert second["schema_version"] == "1.1.0"


def test_successful_update_flow(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    res = mgr.run_update_flow(simulate_failure=False)
    assert res["success"] is True
    assert res["status"] == "COMPLETED"
    assert res["version"] == "1.1.0"

    # Backup directory cleaned up on success
    assert not temp_env["backup_dir"].exists()

    # State file updated
    with open(temp_env["state_file"], "r", encoding="utf-8") as f:
        final_state = json.load(f)
    assert final_state["schema_version"] == "1.1.0"


def test_rollback_on_failed_health_check(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    res = mgr.run_update_flow(simulate_failure=True)
    assert res["success"] is False
    assert res["status"] == "ROLLEDBACK"
    assert res["version"] == "1.0.0"

    # State restored to original 1.0.0
    with open(temp_env["state_file"], "r", encoding="utf-8") as f:
        restored_state = json.load(f)
    assert restored_state["schema_version"] == "1.0.0"
    assert "updated_at" not in restored_state


def test_rollback_on_corrupt_state_health_check(temp_env):
    mgr = WindowsUpdateManager(
        state_file=str(temp_env["state_file"]),
        backup_dir=str(temp_env["backup_dir"]),
        target_version="1.1.0"
    )
    # Checkpoint initial state
    mgr.checkpoint_state()

    # Simulate corrupt state written during bad update
    with open(temp_env["state_file"], "w", encoding="utf-8") as f:
        f.write("{bad json...")

    # Health check should fail
    assert mgr.restart_and_health_check() is False

    # Rollback restores original state
    assert mgr.rollback() is True
    with open(temp_env["state_file"], "r", encoding="utf-8") as f:
        restored = json.load(f)
    assert restored["schema_version"] == "1.0.0"
