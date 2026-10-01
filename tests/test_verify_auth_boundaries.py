import sys
import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_auth_boundaries.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

def test_verify_auth_boundaries_success(capsys):
    mock_content = "def init():\n    if VERIFIER_API_KEY == API_KEY:\n        raise ValueError('Must be different')\n"
    
    with patch("builtins.open", mock_open(read_data=mock_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "AUTH BOUNDARIES VALID" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_auth_boundaries_failure(capsys):
    mock_content = "def init():\n    pass\n"
    
    with patch("builtins.open", mock_open(read_data=mock_content)):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "AUTH BOUNDARIES FAILED:" in captured.out
    assert "server/app.py does not prevent VERIFIER_API_KEY from being the same as API_KEY." in captured.out
    m_exit.assert_called_once_with(1)
