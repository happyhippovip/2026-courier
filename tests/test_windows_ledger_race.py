import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest import mock

from scripts.agent_handoff_ledger import atomic_write, load_bundle, LedgerError

def test_windows_ledger_race_read_transient(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    bundle = {"schema_version": 2, "record": {"TEST": "OK"}, "history": []}
    ledger_path.write_text(json.dumps(bundle))
    
    call_count = 0
    original_read_text = Path.read_text
    
    def mock_read_text(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise PermissionError("Simulated Windows file contention")
        return original_read_text(*args, **kwargs)
        
    with mock.patch("pathlib.Path.read_text", side_effect=mock_read_text):
        # Target behavior: bounded retry should eventually succeed.
        # Defect: this will throw LedgerError("cannot read ledger") because there is no retry.
        loaded = load_bundle(ledger_path)
        assert loaded["record"]["TEST"] == "OK"

def test_windows_ledger_race_write_transient(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    bundle = {"schema_version": 2, "record": {"TEST": "OK"}, "history": []}
    
    call_count = 0
    original_replace = os.replace
    
    def mock_replace(src, dst, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise PermissionError("Simulated Windows file contention")
        return original_replace(src, dst, *args, **kwargs)
        
    with mock.patch("os.replace", side_effect=mock_replace):
        # Target behavior: bounded retry should eventually succeed.
        # Defect: this will throw PermissionError because there is no retry.
        atomic_write(ledger_path, bundle)
        
    assert json.loads(ledger_path.read_text())["record"]["TEST"] == "OK"

def test_windows_ledger_race_persistent_failure(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    bundle = {"schema_version": 2, "record": {}, "history": []}
    ledger_path.write_text(json.dumps(bundle))
    
    call_count = 0
    original_read_text = Path.read_text
    
    def mock_read_text(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise PermissionError("Simulated persistent Windows file contention")
        
    with mock.patch("pathlib.Path.read_text", side_effect=mock_read_text):
        # Negative behavior: persistent error must fail boundedly, never infinite hang.
        with pytest.raises(LedgerError) as exc_info:
            load_bundle(ledger_path)
        assert "cannot read ledger" in str(exc_info.value)
        # Verify it didn't hang infinitely (by checking call count bounds)
        assert call_count <= 50, f"Expected bounded retry, but hit {call_count} attempts"
