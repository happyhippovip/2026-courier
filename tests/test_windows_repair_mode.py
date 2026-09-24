import json
import os
import sys
import tempfile
import pytest

from scripts.windows_repair_mode import WindowsRepairUtility, main


def test_windows_repair_credentials(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        env_file = os.path.join(tmp_dir, ".env.txt")
        repair = WindowsRepairUtility(repo_dir=tmp_dir, env_file=env_file)

        # 1. No credentials present
        monkeypatch.delenv("COURIER_API_KEY", raising=False)
        assert repair.check_credential_access() is False

        # 2. Credential via environment variable
        monkeypatch.setenv("COURIER_API_KEY", "test-secret-token")
        assert repair.check_credential_access() is True

        # 3. Credential via env file
        monkeypatch.delenv("COURIER_API_KEY", raising=False)
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("COURIER_API_KEY=file-token\n")
        assert repair.check_credential_access() is True


def test_windows_repair_schema():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        repair = WindowsRepairUtility(repo_dir=tmp_dir, state_file=state_file)

        # 1. Missing state file
        assert repair.check_state_schema() == "MISSING"

        # 2. Valid state file
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"goals": []}, f)
        assert repair.check_state_schema() == "VALID"

        # 3. Malformed schema (dict without known top-level keys)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"foo": "bar"}, f)
        assert repair.check_state_schema() == "MALFORMED"

        # 4. Corrupted json
        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{ invalid json")
        assert repair.check_state_schema() == "CORRUPTED"
        assert not os.path.exists(state_file)
        # Check quarantine file
        files = os.listdir(tmp_dir)
        assert any(f.startswith("central_state.json.corrupt.") for f in files)


def test_windows_repair_orphaned_executions():
    with tempfile.TemporaryDirectory() as tmp_dir:
        worker_file = os.path.join(tmp_dir, "worker_state.json")
        repair = WindowsRepairUtility(repo_dir=tmp_dir, worker_state_file=worker_file)

        # 1. No file exists
        assert repair.clean_orphaned_executions() == []

        # 2. With dummy non-existent PID
        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({"owned_pids": [9999999]}, f)

        # Should handle gracefully without error and clear pids
        cleaned = repair.clean_orphaned_executions()
        assert isinstance(cleaned, list)

        with open(worker_file, "r", encoding="utf-8") as f:
            wstate = json.load(f)
        assert wstate["owned_pids"] == []


def test_windows_repair_run_full():
    with tempfile.TemporaryDirectory() as tmp_dir:
        state_file = os.path.join(tmp_dir, "central_state.json")
        worker_file = os.path.join(tmp_dir, "worker_state.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"status": "RUNNING"}, f)
        with open(worker_file, "w", encoding="utf-8") as f:
            json.dump({"owned_pids": []}, f)

        repair = WindowsRepairUtility(
            repo_dir=tmp_dir,
            state_file=state_file,
            worker_state_file=worker_file,
        )
        res = repair.run()
        assert res["state_status"] == "VALID"
        assert res["worker_ok"] is True
        assert res["ui_ok"] is True
        assert res["health_ok"] is True
        assert res["restart_ok"] is True


def test_windows_repair_cli_json(capsys):
    orig_argv = sys.argv
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sys.argv = ["windows_repair_mode.py", "--repo-dir", tmp_dir, "--json"]
            main()
            captured = capsys.readouterr()
            assert "state_status" in captured.out
            assert "worker_ok" in captured.out
    finally:
        sys.argv = orig_argv
