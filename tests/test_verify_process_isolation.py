import sys
import os
import pytest
import socket
import psutil
from unittest.mock import patch, MagicMock
from pathlib import Path
import runpy

def run_script():
    repo_root = str(Path(__file__).resolve().parent.parent)
    script_path = Path(repo_root) / "scripts" / "verify_process_isolation.py"
    
    with patch("sys.exit", side_effect=SystemExit) as m_exit:
        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit:
            pass
        return m_exit

@pytest.fixture
def mock_clean_env():
    # Setup mocks that represent a clean environment
    patchers = [
        patch("socket.socket.connect_ex", return_value=1), # 1 means connection refused
        patch("psutil.process_iter", return_value=[]),
    ]
    if hasattr(os, "getsid"):
        patchers.append(patch("os.getsid", return_value=1234))
        
    for p in patchers:
        p.start()
        
    yield
    
    for p in patchers:
        p.stop()

def test_verify_process_isolation_success(capsys, mock_clean_env):
    m_exit = run_script()
    captured = capsys.readouterr()
    assert "PROCESS ISOLATION VALID" in captured.out
    m_exit.assert_called_once_with(0)

def test_verify_process_isolation_port_in_use(capsys, mock_clean_env):
    with patch("socket.socket.connect_ex", return_value=0):
        m_exit = run_script()
    
    captured = capsys.readouterr()
    assert "PROCESS ISOLATION FAILED:" in captured.out
    assert "Port 8080 is already in use by a foreign process!" in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_process_isolation_getsid_invalid(capsys, mock_clean_env):
    if hasattr(os, "getsid"):
        with patch("os.getsid", return_value=0):
            m_exit = run_script()
        
        captured = capsys.readouterr()
        assert "Invalid session ID." in captured.out
        m_exit.assert_called_once_with(1)

def test_verify_process_isolation_heavy_job(capsys, mock_clean_env):
    mock_proc = MagicMock()
    mock_proc.info = {'cmdline': ['python', 'server.app']}
    
    with patch("psutil.process_iter", return_value=[mock_proc]):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "Foreign server.app process detected running on this host." in captured.out
    m_exit.assert_called_once_with(1)

def test_verify_process_isolation_psutil_exceptions(capsys, mock_clean_env):
    mock_proc = MagicMock()
    # Property mock to raise AccessDenied when reading info
    type(mock_proc).info = property(lambda self: _raise(psutil.AccessDenied(pid=999)))
    
    def _raise(ex):
        raise ex

    with patch("psutil.process_iter", return_value=[mock_proc]):
        m_exit = run_script()
        
    captured = capsys.readouterr()
    assert "PROCESS ISOLATION VALID" in captured.out
    m_exit.assert_called_once_with(0)
