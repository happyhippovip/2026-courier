import pytest
import os
import sys
from scripts.check_pilot_readiness import check_readiness, pilot_failure_aborts

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
        normalized = str(path).replace("\\", "/")
        if normalized.endswith("ops/ai/PILOT_DUMMY_TASK.json"):
            return False
        return True
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()
        
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "FAILED: Missing ops/ai/PILOT_DUMMY_TASK.json" in captured.out


def test_human_intervention_aborts_the_pilot():
    assert pilot_failure_aborts({"hipg": 1, "ndr_pct": 100}) is True


def test_duplicate_execution_aborts_the_pilot():
    assert pilot_failure_aborts({"hipg": 0, "ndr_pct": 99}) is True


def test_clean_counts_do_not_abort_the_pilot():
    record = {"hipg": 0, "ndr_pct": 100}
    assert pilot_failure_aborts(record) is False
    assert pilot_failure_aborts(record) is False


def test_missing_or_boolean_counts_abort_the_pilot():
    assert pilot_failure_aborts({}) is True
    assert pilot_failure_aborts({"hipg": False, "ndr_pct": 100}) is True
    assert pilot_failure_aborts({"hipg": 0, "ndr_pct": 100, "verifier_accepted_out_of_scope": True}) is True
    assert pilot_failure_aborts({"hipg": 0, "ndr_pct": 100, "daemon_failed_to_recover": False}) is False


def test_check_readiness_from_other_cwd(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        check_readiness()

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ALL PILOT PREREQUISITES PRESENT" in captured.out
