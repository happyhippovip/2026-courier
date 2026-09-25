import pytest
import os
import sys
import json
import time
from unittest import mock
import urllib.error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import product_health_check

@pytest.fixture
def mock_env():
    with mock.patch.dict("os.environ", {"COURIER_API_KEY": "test-key"}):
        yield

def test_run_healthy(mock_env, capsys):
    mock_status_response = mock.Mock()
    mock_status_response.read.return_value = json.dumps({"goals": {}, "tasks": {}}).encode("utf-8")
    
    mock_workers_response = mock.Mock()
    mock_workers_response.read.return_value = json.dumps({
        "VERIFIER-01": {"last_heartbeat": time.time() - 10}
    }).encode("utf-8")
    
    status_cm = mock.Mock()
    status_cm.__enter__ = mock.Mock(return_value=mock_status_response)
    status_cm.__exit__ = mock.Mock(return_value=None)
    
    workers_cm = mock.Mock()
    workers_cm.__enter__ = mock.Mock(return_value=mock_workers_response)
    workers_cm.__exit__ = mock.Mock(return_value=None)
    
    def urlopen_side_effect(req, timeout):
        if "/status" in req.full_url:
            return status_cm
        if "/workers" in req.full_url:
            return workers_cm
            
    with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        product_health_check.run()
        
    captured = capsys.readouterr()
    assert "HEALTHY" in captured.out

def test_run_missing_api_key(capsys):
    with mock.patch.dict("os.environ", clear=True):
        with mock.patch("scripts.product_health_check.keyring", create=True) as mock_keyring:
            mock_keyring.get_password.return_value = None
            with pytest.raises(SystemExit) as excinfo:
                product_health_check.run()
            assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "HUMAN_REQUIRED: No credentials found" in captured.out

def test_run_unreachable(mock_env, capsys):
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
        with pytest.raises(SystemExit) as excinfo:
            product_health_check.run()
        assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "DEGRADED: Server unreachable" in captured.out

def test_run_missing_schema(mock_env, capsys):
    mock_status_response = mock.Mock()
    mock_status_response.read.return_value = json.dumps({"wrong": "data"}).encode("utf-8")
    status_cm = mock.Mock()
    status_cm.__enter__ = mock.Mock(return_value=mock_status_response)
    status_cm.__exit__ = mock.Mock(return_value=None)
    
    with mock.patch("urllib.request.urlopen", return_value=status_cm):
        with pytest.raises(SystemExit) as excinfo:
            product_health_check.run()
        assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "Schema incompatible" in captured.out

def test_run_stale_worker(mock_env, capsys):
    mock_status_response = mock.Mock()
    mock_status_response.read.return_value = json.dumps({"goals": {}, "tasks": {}}).encode("utf-8")
    
    mock_workers_response = mock.Mock()
    mock_workers_response.read.return_value = json.dumps({
        "WORKER-01": {"last_heartbeat": time.time() - 1000} # > 600
    }).encode("utf-8")
    
    status_cm = mock.Mock()
    status_cm.__enter__ = mock.Mock(return_value=mock_status_response)
    status_cm.__exit__ = mock.Mock(return_value=None)
    
    workers_cm = mock.Mock()
    workers_cm.__enter__ = mock.Mock(return_value=mock_workers_response)
    workers_cm.__exit__ = mock.Mock(return_value=None)
    
    def urlopen_side_effect(req, timeout):
        if "/status" in req.full_url:
            return status_cm
        if "/workers" in req.full_url:
            return workers_cm
            
    with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        with pytest.raises(SystemExit) as excinfo:
            product_health_check.run()
        assert excinfo.value.code == 1
            
    captured = capsys.readouterr()
    assert "Stale ownership" in captured.out
    
