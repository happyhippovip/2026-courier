import pytest
import os
import sys
from scripts.check_pilot_readiness import check_readiness

def test_check_readiness_success(monkeypatch, capsys):
    def mock_exists(path):
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()
        
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ALL PILOT PREREQUISITES PRESENT" in captured.out

def test_check_readiness_failure(monkeypatch, capsys):
    def mock_exists(path):
        # Simulate missing file for the first one
        if path == "ops/ai/PILOT_DUMMY_TASK.json":
            return False
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()
        
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "FAILED: Missing ops/ai/PILOT_DUMMY_TASK.json" in captured.out

def test_main_block(monkeypatch, capsys):
    def mock_exists(path):
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    import runpy
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "check_pilot_readiness.py"), run_name="__main__")
        
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ALL PILOT PREREQUISITES PRESENT" in captured.out
