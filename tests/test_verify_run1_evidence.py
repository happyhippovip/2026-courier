import sys
import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_run1_evidence.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

@pytest.fixture
def mock_evidence_clean():
    # Return True for exists
    mock_exists = MagicMock(return_value=True)
    
    # Mock sqlite3
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = ('RECONCILED',)
    
    # Mock open
    mock_log_content = "Claimed task A\nResult for task A\n"
    
    patchers = [
        patch("os.path.exists", mock_exists),
        patch("sqlite3.connect", return_value=mock_conn),
        patch("builtins.open", mock_open(read_data=mock_log_content))
    ]
    
    for p in patchers:
        p.start()
        
    yield {'cursor': mock_cursor, 'exists': mock_exists}
    
    for p in patchers:
        p.stop()

def test_verify_run1_evidence_success(capsys, mock_evidence_clean):
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "RUN_1 EVIDENCE VALID: RECONCILED, EXACTLY_ONCE, NO_FAILURES" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_run1_evidence_missing_db(capsys, mock_evidence_clean):
    mock_evidence_clean['exists'].side_effect = lambda p: False if 'ledger_run1.db' in str(p) else True
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "ledger_run1.db is missing" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run1_evidence_wrong_status(capsys, mock_evidence_clean):
    mock_evidence_clean['cursor'].fetchone.return_value = ('IN_PROGRESS',)
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "Task A is not RECONCILED. Current: IN_PROGRESS" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run1_evidence_missing_status(capsys, mock_evidence_clean):
    mock_evidence_clean['cursor'].fetchone.return_value = None
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "Task A is not RECONCILED. Current: MISSING" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run1_evidence_missing_server_log_is_not_valid(capsys, mock_evidence_clean):
    mock_evidence_clean["exists"].side_effect = lambda path: "server_run1.log" not in str(path)
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "RUN_1 EVIDENCE VALID" not in captured.out
    assert "EXACTLY_ONCE" not in captured.out
    assert "NO_FAILURES" not in captured.out
    m_exit.assert_called_once_with(1)


def test_verify_run1_evidence_log_failure_is_not_valid(capsys, mock_evidence_clean):
    with patch("builtins.open", mock_open(read_data="Claimed task A\nResult for task A\nFAILED\n")):
        m_exit = run_script()
    captured = capsys.readouterr()
    assert "RUN_1 EVIDENCE VALID" not in captured.out
    assert "NO_FAILURES" not in captured.out
    assert "records a failure" in captured.out
    m_exit.assert_called_once_with(1)


def test_verify_run1_evidence_wrong_counts(capsys, mock_evidence_clean):
    mock_log_content = "Claimed task A\nClaimed task A\n" # Missing result, double claim
    with patch("builtins.open", mock_open(read_data=mock_log_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "Task A was claimed 2 times, expected exactly 1." in captured.out
    assert "Task A result submitted 0 times, expected exactly 1." in captured.out
    m_exit.assert_called_once_with(1)
