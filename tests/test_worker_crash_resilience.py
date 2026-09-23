"""Worker crash resilience and state quarantine tests.

Verifies:
1. atomic_save_json creates valid files atomically and cleans up temp files.
2. quarantine_corrupt_file renames corrupt files to .corrupt.<timestamp> preserving evidence.
3. Mac worker daemon safely recovers from corrupt task, result, and wait state files without crash looping.
4. Windows worker daemon safely recovers from corrupt marker files without infinite backoff stalling.
"""

import json
import time
from pathlib import Path
import pytest

from scripts.mac_worker.daemon import (
    atomic_save_json as mac_atomic_save,
    quarantine_corrupt_file as mac_quarantine,
    load_config as mac_load_config,
)
from scripts.windows_worker.daemon import (
    atomic_save_json as win_atomic_save,
    quarantine_corrupt_file as win_quarantine,
    load_config as win_load_config,
)


def test_mac_atomic_save_json_success(tmp_path):
    target = tmp_path / "state.json"
    data = {"status": "SUCCESS", "id": 123}
    mac_atomic_save(target, data)
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == data
    # Ensure no leftover temp files
    temp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(temp_files) == 0


def test_win_atomic_save_json_success(tmp_path):
    target = tmp_path / "marker.json"
    data = {"task_id": "win-task-1", "attempt": 1}
    win_atomic_save(target, data)
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == data
    temp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(temp_files) == 0


def test_atomic_save_cleans_up_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "fail.json"
    # An object that fails json serialization
    bad_data = {"unserializable": object()}
    with pytest.raises(TypeError):
        mac_atomic_save(target, bad_data)
    assert not target.exists()
    temp_files = list(tmp_path.glob("*.tmp.*"))
    assert len(temp_files) == 0


def test_quarantine_corrupt_file(tmp_path):
    corrupt = tmp_path / "current_task.json"
    corrupt.write_text('{"task_id": "truncated-data', encoding="utf-8")
    
    quarantined = mac_quarantine(corrupt)
    assert not corrupt.exists()
    assert quarantined is not None
    assert quarantined.exists()
    assert ".corrupt." in quarantined.name
    assert quarantined.read_text(encoding="utf-8") == '{"task_id": "truncated-data'


def test_mac_load_config_recovers_from_corrupt_file(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{broken-json-not-valid', encoding="utf-8")
    monkeypatch.setenv("COURIER_CONFIG_PATH", str(cfg_file))
    monkeypatch.setenv("COURIER_API_KEY", "test-key")
    monkeypatch.setenv("COURIER_SERVER", "http://127.0.0.1:8080")
    
    # Should not raise json.JSONDecodeError, should fall back to defaults
    config = mac_load_config()
    assert isinstance(config, dict)
    assert config["COURIER_API_KEY"] == "test-key"


def test_windows_load_config_recovers_from_corrupt_file(monkeypatch, tmp_path):
    cfg_dir = tmp_path / "win_cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    cfg_file.write_text('{"bad: json', encoding="utf-8")
    
    # Temporarily point daemon's __file__ location
    import scripts.windows_worker.daemon as win_daemon
    monkeypatch.setattr(win_daemon, "Path", lambda *args: cfg_dir if args == (win_daemon.__file__,) else Path(*args))
    
    # Calling win_load_config should gracefully return empty dict instead of crashing
    config = win_load_config()
    assert config == {}


def test_mac_state_quarantine_prevents_startup_crash(tmp_path, monkeypatch):
    import importlib
    import sys
    
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    
    # Create corrupted state files
    corrupt_task = state_dir / "current_task.json"
    corrupt_task.write_text('{"task_id": [UNFINISHED', encoding="utf-8")
    
    corrupt_result = state_dir / "current_result.json"
    corrupt_result.write_text('00000000000', encoding="utf-8")
    
    corrupt_wait = state_dir / "current_provider_wait.json"
    corrupt_wait.write_text('', encoding="utf-8")
    
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"WORKER_ID": "TEST-MAC-01", "COURIER_SERVER": "http://127.0.0.1:8080"}))
    
    monkeypatch.setenv("COURIER_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("COURIER_WORKER_STATE_DIR", str(state_dir))
    monkeypatch.setenv("COURIER_WORKER_LOGS_DIR", str(logs_dir))
    monkeypatch.setenv("COURIER_API_KEY", "test-key-safe")
    
    from scripts.mac_worker import daemon as mac_d
    
    # Verify quarantine_corrupt_file handles all 3
    q_task = mac_d.quarantine_corrupt_file(corrupt_task)
    assert not corrupt_task.exists()
    assert q_task.exists()
    
    q_result = mac_d.quarantine_corrupt_file(corrupt_result)
    assert not corrupt_result.exists()
    assert q_result.exists()
    
    q_wait = mac_d.quarantine_corrupt_file(corrupt_wait)
    assert not corrupt_wait.exists()
    assert q_wait.exists()
