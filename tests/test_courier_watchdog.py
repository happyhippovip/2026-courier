import pytest
import os
import json
from unittest.mock import patch, MagicMock

def test_watchdog_run_loop(monkeypatch, capsys):
    import scripts.courier_watchdog as script
    monkeypatch.setattr(script, "API_KEY", "secret")
    monkeypatch.setattr(script, "API_URL", "http://test")
    
    # We want to break out of the loop after one iteration
    call_count = 0
    original_sleep = script.time.sleep
    def mock_sleep(secs):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise KeyboardInterrupt()
            
    monkeypatch.setattr(script.time, "sleep", mock_sleep)
    
    class MockResponse:
        status_code = 200
        def json(self):
            return {"reclaimed_tasks": 2, "quarantined_tasks": 1}
            
    def mock_post(*args, **kwargs):
        return MockResponse()
        
    monkeypatch.setattr(script.requests, "post", mock_post)
    
    with pytest.raises(KeyboardInterrupt):
        script.run_loop()
        
    out, _ = capsys.readouterr()
    assert "Starting Courier Watchdog" in out
    assert "Reclaimed 2 tasks" in out
    assert "Quarantined 1 tasks" in out

def test_watchdog_no_api_key(monkeypatch):
    import scripts.courier_watchdog as script
    monkeypatch.setattr(script, "API_KEY", None)
    
    with pytest.raises(SystemExit, match="COURIER_API_KEY is required"):
        script.run_loop()

def test_watchdog_error_handling(monkeypatch, capsys):
    import scripts.courier_watchdog as script
    monkeypatch.setattr(script, "API_KEY", "secret")
    
    def mock_sleep(secs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(script.time, "sleep", mock_sleep)
    
    def mock_post(*args, **kwargs):
        raise Exception("Network failure")
    monkeypatch.setattr(script.requests, "post", mock_post)
    
    with pytest.raises(KeyboardInterrupt):
        script.run_loop()
        
    out, _ = capsys.readouterr()
    assert "Error calling watchdog endpoint: Network failure" in out

