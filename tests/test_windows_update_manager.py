import json
import os
import sys
import tempfile

from scripts.windows_update_manager import WindowsUpdateManager, main


def test_windows_update_manager_success():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"goals": {}}, f)

        manager = WindowsUpdateManager(repo_dir=tmp_dir)
        success = manager.run_update_flow(simulate_failure=False)
        assert success is True

        # Verify schema version was added idempotently
        with open(state_file, "r", encoding="utf-8") as f:
            updated_state = json.load(f)
        assert updated_state.get("schema_version") == "1.1.0"

        # Verify backup was cleaned up
        assert not os.path.exists(manager.backup_dir)


def test_windows_update_manager_rollback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        original_data = {"goals": {"G1": "done"}, "unique_field": 12345}
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(original_data, f)

        manager = WindowsUpdateManager(repo_dir=tmp_dir)
        success = manager.run_update_flow(simulate_failure=True)
        assert success is False

        # Verify original data was restored via rollback
        with open(state_file, "r", encoding="utf-8") as f:
            restored_data = json.load(f)
        assert restored_data == original_data
        assert "schema_version" not in restored_data
