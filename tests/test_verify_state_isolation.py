import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_state_isolation.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

@pytest.fixture
def mock_fs():
    patchers = [
        ("exists", patch("os.path.exists", return_value=True)),
        ("makedirs", patch("os.makedirs")),
        ("listdir", patch("os.listdir", return_value=[])),
        ("isfile", patch("os.path.isfile", return_value=True)),
        ("getmtime", patch("os.path.getmtime", return_value=1000.0)),
        ("time", patch("time.time", return_value=1100.0)) # age = 100
    ]
    
    mocks = {}
    for name, p in patchers:
        mocks[name] = p.start()
        
    yield mocks
    
    for name, p in patchers:
        p.stop()

def test_verify_state_isolation_success(capsys, mock_fs):
    mock_fs['listdir'].return_value = ["file1.txt", "file2.json"]
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "STATE ISOLATION VALID" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_state_isolation_missing_dir(capsys, mock_fs):
    mock_fs['exists'].return_value = False
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "STATE ISOLATION VALID" not in captured.out
    mock_fs['makedirs'].assert_not_called()
    m_exit.assert_called_once_with(1)

def test_verify_state_isolation_stale_files(capsys, mock_fs):
    mock_fs['listdir'].return_value = ["file1.txt"]
    mock_fs['time'].return_value = 5000.0 # age = 4000 > 3600
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "Stale state file detected: file1.txt" in captured.out
    m_exit.assert_called_once_with(1)
