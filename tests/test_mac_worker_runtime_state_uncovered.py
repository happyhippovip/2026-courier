import json
import os
import signal
if not hasattr(signal, "SIGKILL"):
    signal.SIGKILL = 9
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import scripts.mac_worker.runtime_state as runtime_state

def test_read_object(tmp_path):
    f = tmp_path / "state.json"
    
    # Missing file with default
    assert runtime_state.read_object(f, default={"a": 1}) == {"a": 1}
    # Missing file without default
    assert runtime_state.read_object(f) == {}
    
    # Write valid object
    f.write_text('{"b": 2}')
    assert runtime_state.read_object(f) == {"b": 2}
    
    # Write non-object (list)
    f.write_text('["list"]')
    with pytest.raises(ValueError):
        runtime_state.read_object(f)

def test_sync_directory(tmp_path):
    with patch("os.open", return_value=123) as mock_open, \
         patch("os.fsync") as mock_fsync, \
         patch("os.close") as mock_close:
        runtime_state.sync_directory(tmp_path)
        mock_open.assert_called_once_with(str(tmp_path), os.O_RDONLY)
        mock_fsync.assert_called_once_with(123)
        mock_close.assert_called_once_with(123)

def test_atomic_json(tmp_path):
    f = tmp_path / "atomic.json"
    
    with patch("os.fsync"), patch("scripts.mac_worker.runtime_state.sync_directory"):
        runtime_state.atomic_json(f, {"k": "v"})
        
    assert json.loads(f.read_text()) == {"k": "v"}

def test_control_lock(tmp_path):
    # Should work without fcntl
    with runtime_state.control_lock(tmp_path):
        assert (tmp_path / "control.lock").exists()

def test_process_identity():
    # Valid parse
    with patch("subprocess.check_output", return_value="  123 123 Mon Oct 23 10:00:00 2026 python \n"):
        res = runtime_state.process_identity(123)
        assert res is not None
        assert res["pid"] == 123
        assert res["pgid"] == 123
        assert "fingerprint" in res

    # PID mismatch
    with patch("subprocess.check_output", return_value="  124 124 Mon Oct 23 10:00:00 2026 python \n"):
        assert runtime_state.process_identity(123) is None

    # Error
    with patch("subprocess.check_output", side_effect=OSError("fail")):
        assert runtime_state.process_identity(123) is None

def test_same_process():
    with patch("scripts.mac_worker.runtime_state.process_identity", return_value={"pid": 1, "pgid": 1, "fingerprint": "hash"}):
        assert runtime_state.same_process(1, {"pid": 1, "pgid": 1, "fingerprint": "hash"}) is True
        assert runtime_state.same_process(1, {"pid": 1, "pgid": 1, "fingerprint": "other"}) is False
        assert runtime_state.same_process(1, None) is False

def test_group_exists():
    with patch("os.killpg", create=True) as mock_killpg:
        # Success
        assert runtime_state.group_exists(1) is True
        
        # Missing
        mock_killpg.side_effect = ProcessLookupError()
        assert runtime_state.group_exists(1) is False
        
        # Permission error (still exists)
        mock_killpg.side_effect = PermissionError()
        assert runtime_state.group_exists(1) is True

def test_cleanup_group_already_dead():
    mock_proc = MagicMock()
    mock_proc.pid = 123
    mock_proc.poll.return_value = 0 # Dead
    with patch("scripts.mac_worker.runtime_state.group_exists", return_value=False):
        assert runtime_state.cleanup_group(mock_proc, None) is True

def test_cleanup_group_identity_mismatch():
    mock_proc = MagicMock()
    mock_proc.pid = 123
    mock_proc.poll.return_value = None
    
    # Missing identity
    assert runtime_state.cleanup_group(mock_proc, None) is False
    
    # pgid mismatch
    assert runtime_state.cleanup_group(mock_proc, {"pgid": 456}) is False
    
    # Current identity mismatch
    with patch("scripts.mac_worker.runtime_state.process_identity", return_value={"pid": 123, "pgid": 123, "fingerprint": "new"}):
        assert runtime_state.cleanup_group(mock_proc, {"pid": 123, "pgid": 123, "fingerprint": "old"}) is False

def test_cleanup_group_kills():
    mock_proc = MagicMock()
    mock_proc.pid = 123
    mock_proc.poll.return_value = None
    identity = {"pid": 123, "pgid": 123, "fingerprint": "hash"}
    
    # Successful kill on SIGTERM
    with patch("scripts.mac_worker.runtime_state.process_identity", return_value=identity), \
         patch("scripts.mac_worker.runtime_state.group_exists", side_effect=[True, False]), \
         patch("os.killpg", create=True) as mock_killpg:
        assert runtime_state.cleanup_group(mock_proc, identity) is True
        mock_killpg.assert_called_once_with(123, signal.SIGTERM)

    # Process dies from SIGKILL after ignoring SIGTERM
    with patch("scripts.mac_worker.runtime_state.process_identity", return_value=identity), \
         patch("scripts.mac_worker.runtime_state.group_exists", side_effect=[True, True, True, False]), \
         patch("os.killpg", create=True) as mock_killpg, \
         patch("time.sleep"), \
         patch("time.monotonic", side_effect=[1, 2, 3, 4, 5, 6, 7]): # Advance time to timeout SIGTERM
        
        # Mock poll doesn't change anything
        assert runtime_state.cleanup_group(mock_proc, identity) is True
        assert mock_killpg.call_count == 2
