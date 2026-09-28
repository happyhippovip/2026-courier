import subprocess
import time
import json
import urllib.request
from scripts.windows_worker.daemon import run_task, HEADERS

def test_heartbeat_during_execution(monkeypatch):
    import urllib.error
    
    heartbeat_count = 0
    def mock_urlopen(req, data=None, timeout=None):
        nonlocal heartbeat_count
        if "heartbeat" in req.full_url:
            heartbeat_count += 1
        return type("Resp", (), {"read": lambda: b'{"status": "ok"}'})()
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    task = {
        "task_id": "t1", "goal_id": "g1",
        "instruction": "Start-Sleep -Seconds 2"
    }
    
    # We will test the modified run_task that sends heartbeats
