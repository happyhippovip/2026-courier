import json
import os
import sys
import pytest
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

from scripts import revenue_worker_adapter

@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("COURIER_SERVER", raising=False)
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    
    # redirect paths
    monkeypatch.setattr(revenue_worker_adapter, "STATE_DIR", tmp_path / "revenue_worker_state")
    monkeypatch.setattr(revenue_worker_adapter, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(revenue_worker_adapter, "CONFIG_PATH", tmp_path / "revenue_worker_config.json")
    
    # Ensure dirs exist
    (tmp_path / "revenue_worker_state").mkdir(exist_ok=True)
    (tmp_path / "logs").mkdir(exist_ok=True)

def test_get_config_new(clean_env, monkeypatch):
    def mock_check_output(cmd, **kwargs):
        if "-s" in cmd and "courier_api_key" in cmd:
            return b"key_from_keychain"
        if "-s" in cmd and "courier_server_url" in cmd:
            return b"http://keychain.local"
        raise Exception("not found")
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    config = revenue_worker_adapter.get_config()
    assert config["COURIER_API_KEY"] == "key_from_keychain"
    assert config["COURIER_SERVER"] == "http://keychain.local"
    assert "WORKER_ID" in config

def test_get_config_existing(clean_env, monkeypatch):
    # write existing config
    c = {"COURIER_SERVER": "x", "COURIER_API_KEY": "y"}
    revenue_worker_adapter.CONFIG_PATH.write_text(json.dumps(c))
    
    # also simulate env var override
    monkeypatch.setenv("COURIER_SERVER", "http://env.local")
    
    def mock_check_output(*a, **kw): raise Exception("fail")
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    config = revenue_worker_adapter.get_config()
    assert config["COURIER_SERVER"] == "http://env.local"
    assert config["COURIER_API_KEY"] == "y"

def test_get_config_exit(clean_env, monkeypatch):
    def mock_check_output(*a, **kw): raise Exception("fail")
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    with pytest.raises(SystemExit) as e:
        revenue_worker_adapter.get_config()
    assert e.value.code == 1

def test_http_post_success(monkeypatch):
    class MockResponse:
        def read(self):
            return b'{"ok": true}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
            
    def mock_urlopen(req):
        assert req.full_url == "http://local/foo"
        assert req.get_header("Authorization") == "Bearer AAA"
        return MockResponse()
        
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    config = {"COURIER_SERVER": "http://local", "COURIER_API_KEY": "AAA"}
    res = revenue_worker_adapter.http_post(config, "/foo", {"data": 1})
    assert res == {"ok": True}

def test_http_post_http_error(monkeypatch, clean_env):
    def mock_urlopen(req):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad", {}, None)
        
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    config = {"COURIER_SERVER": "http://local", "COURIER_API_KEY": "AAA"}
    res = revenue_worker_adapter.http_post(config, "/foo")
    assert res is None

def test_http_post_exception(monkeypatch, clean_env):
    def mock_urlopen(req):
        raise ValueError("Generic")
        
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    config = {"COURIER_SERVER": "http://local", "COURIER_API_KEY": "AAA"}
    res = revenue_worker_adapter.http_post(config, "/foo")
    assert res is None

class StopLoop(Exception):
    pass

def test_main_loop(clean_env, monkeypatch):
    c = {"COURIER_SERVER": "x", "COURIER_API_KEY": "y", "WORKER_ID": "W1", "POLL_INTERVAL_SECONDS": 1}
    revenue_worker_adapter.CONFIG_PATH.write_text(json.dumps(c))
    
    call_count = 0
    def mock_http_post(config, endpoint, data=None):
        nonlocal call_count
        if endpoint == "/tasks/claim":
            call_count += 1
            if call_count == 1:
                # create work_dir so cleanup is triggered
                (revenue_worker_adapter.STATE_DIR / "T1").mkdir(parents=True, exist_ok=True)
                return {"task_id": "T1", "attempt_id": "A1"}
            else:
                return None
        return {}
        
    monkeypatch.setattr(revenue_worker_adapter, "http_post", mock_http_post)
    
    def mock_check_output(cmd, **kwargs):
        if "revenue_v1_safety_baseline.py" in str(cmd):
            # Create dummy reports
            work_dir = Path(cmd[-1])
            (work_dir / "report.json").write_text("{}")
            (work_dir / "report.md").write_text("ok")
            return b'{"result": "pass"}'
        return b""
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    sleep_count = 0
    def mock_sleep(s):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count >= 2:
            raise StopLoop()
            
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    with pytest.raises(StopLoop):
        revenue_worker_adapter.main()
        
    assert call_count > 0

def test_main_loop_subprocess_fail(clean_env, monkeypatch):
    c = {"COURIER_SERVER": "x", "COURIER_API_KEY": "y", "WORKER_ID": "W1", "POLL_INTERVAL_SECONDS": 1}
    revenue_worker_adapter.CONFIG_PATH.write_text(json.dumps(c))
    
    def mock_http_post(config, endpoint, data=None):
        if endpoint == "/tasks/claim":
            return {"task_id": "T2"}
        return {}
        
    monkeypatch.setattr(revenue_worker_adapter, "http_post", mock_http_post)
    
    def mock_check_output(cmd, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, output=b"err")
        
    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    
    def mock_sleep(s):
        raise StopLoop()
            
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    with pytest.raises(StopLoop):
        revenue_worker_adapter.main()

def test_main_loop_generic_error(clean_env, monkeypatch):
    c = {"COURIER_SERVER": "x", "COURIER_API_KEY": "y", "WORKER_ID": "W1", "POLL_INTERVAL_SECONDS": 1}
    revenue_worker_adapter.CONFIG_PATH.write_text(json.dumps(c))
    
    def mock_http_post(config, endpoint, data=None):
        raise ValueError("Generic crash inside loop")
        
    monkeypatch.setattr(revenue_worker_adapter, "http_post", mock_http_post)
    
    def mock_sleep(s):
        raise StopLoop()
            
    monkeypatch.setattr(time, "sleep", mock_sleep)
    
    with pytest.raises(StopLoop):
        revenue_worker_adapter.main()

def test_main_executes(monkeypatch):
    def mock_main():
        raise StopLoop()
    monkeypatch.setattr(revenue_worker_adapter, "main", mock_main)
    
    import runpy
    with pytest.raises(StopLoop):
        runpy.run_path("scripts/revenue_worker_adapter.py", run_name="__main__")
