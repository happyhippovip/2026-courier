import sys
import os
import pytest
import sqlite3
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_run2_evidence.py"
    
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
    
    def fetchone_side_effect():
        # First call is task A, second is task B
        return ('RECONCILED',)
        
    mock_cursor.fetchone.side_effect = [('RECONCILED',), ('RECONCILED',)]
    
    # Mock open
    mock_log_content = "Claimed task B\nResult for task B\n"
    
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

def test_verify_run2_evidence_success(capsys, mock_evidence_clean):
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "RUN_2 EVIDENCE VALID: A_SURVIVED, B_RECONCILED, NO_REPLAYS" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_run2_evidence_missing_db(capsys, mock_evidence_clean):
    mock_evidence_clean['exists'].side_effect = lambda p: False if 'ledger_run2.db' in str(p) else True
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "ledger_run2.db is missing" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run2_evidence_task_A_not_reconciled(capsys, mock_evidence_clean):
    mock_evidence_clean['cursor'].fetchone.side_effect = [('QUEUED',), ('RECONCILED',)]
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "Task A is not RECONCILED after RUN_2. Current: QUEUED" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run2_evidence_task_B_not_reconciled(capsys, mock_evidence_clean):
    mock_evidence_clean['cursor'].fetchone.side_effect = [('RECONCILED',), None]
    m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "Task B is not RECONCILED. Current: MISSING" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_run2_evidence_task_A_replayed(capsys, mock_evidence_clean):
    mock_log_content = "Claimed task A\nResult for task B\n"
    with patch("builtins.open", mock_open(read_data=mock_log_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "Task A was incorrectly dispatched again in RUN_2!" in captured.out
    m_exit.assert_called_once_with(1)
