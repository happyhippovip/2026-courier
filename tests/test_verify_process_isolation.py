import json
import subprocess
import sys
import os
import time
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
    assert "PROCESS ISOLATION VALID" not in captured.out
    assert "No session boundary read back." in captured.out
    m_exit.assert_called_once_with(1)

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
        assert "PROCESS ISOLATION VALID" not in captured.out
        assert "Invalid session ID." not in captured.out
        assert "No session boundary read back." in captured.out
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
    assert "PROCESS ISOLATION VALID" not in captured.out
    assert "No session boundary read back." in captured.out
    m_exit.assert_called_once_with(1)


_SESSION_CHILD = """
import json, os, sys, time
path = sys.argv[1]
os.setsid()
sid = os.getsid(0)
with open(path, "w", encoding="utf-8") as handle:
    json.dump({"pid": os.getpid(), "sid": sid}, handle)
    handle.flush()
time.sleep(30)
"""


def _wait_for_record(path: Path) -> dict:
    for _ in range(50):
        if path.exists() and path.stat().st_size > 0:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        time.sleep(0.05)
    raise AssertionError("session record was not written")


def test_process_isolation_valid_only_after_session_boundary(tmp_path, capsys):
    import scripts.verify_process_isolation as isolation

    record = tmp_path / "session.json"
    proc = subprocess.Popen(
        [sys.executable, "-c", _SESSION_CHILD, str(record)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        payload = _wait_for_record(record)
        assert payload["pid"] == proc.pid
        assert payload["sid"] != os.getsid(os.getpid())
        with patch("socket.socket.connect_ex", return_value=1), patch("psutil.process_iter", return_value=[]):
            with pytest.raises(SystemExit) as caught:
                isolation.check_process_isolation(port=8080, session_record=str(record))
    finally:
        proc.kill()
        proc.wait(timeout=5)

    assert caught.value.code == 0
    assert "PROCESS ISOLATION VALID" in capsys.readouterr().out


def test_process_isolation_rejects_own_session_record(tmp_path, capsys):
    import scripts.verify_process_isolation as isolation

    record = tmp_path / "self.json"
    record.write_text(json.dumps({"pid": os.getpid(), "sid": os.getsid(os.getpid())}), encoding="utf-8")
    with patch("socket.socket.connect_ex", return_value=1), patch("psutil.process_iter", return_value=[]):
        with pytest.raises(SystemExit) as caught:
            isolation.check_process_isolation(port=8080, session_record=str(record))
    assert caught.value.code == 1
    assert "PROCESS ISOLATION VALID" not in capsys.readouterr().out
