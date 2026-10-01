import pytest
import os
import sys
import json
from unittest import mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.bodyguard_daemon import get_temporary_role, execute_task, main, BODYGUARDS

def test_get_temporary_role_success(monkeypatch):
    class DummyManager:
        def get_all_bodyguards(self):
            return [{"id": "agent-bodyguard-alpha", "temporary_role": "QA_WORKER"}]
    
    # Mock the import inside the function
    import scripts.bodyguard_daemon as bd
    
    # We mock the entire run_bodyguards module to be accessible
    mock_rb = mock.MagicMock()
    mock_rb.BodyguardPoolManager.return_value = DummyManager()
    sys.modules['run_bodyguards'] = mock_rb
    
    try:
        assert get_temporary_role("agent-bodyguard-alpha") == "QA_WORKER"
        assert get_temporary_role("agent-bodyguard-beta") == "TECHNICAL_WORKER"
    finally:
        del sys.modules['run_bodyguards']

def test_get_temporary_role_exception(monkeypatch):
    import scripts.bodyguard_daemon as bd
    
    # Mock to throw exception on BodyguardPoolManager instantiation
    mock_rb = mock.MagicMock()
    mock_rb.BodyguardPoolManager.side_effect = Exception("forced error")
    sys.modules['run_bodyguards'] = mock_rb
    
    try:
        assert get_temporary_role("agent-bodyguard-alpha") == "TECHNICAL_WORKER"
    finally:
        del sys.modules['run_bodyguards']

def test_execute_task_success(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "events" / "agent-states").mkdir(parents=True)
    
    task = {"task_id": "task_xyz", "goal_id": "g1", "attempt_id": "a1", "dispatch_id": "d1"}
    
    class DummyProc:
        returncode = 0
        stdout = "ok"
        stderr = ""
        
    def mock_run(cmd, *args, **kwargs):
        assert cmd[1] == "scripts/run_codex_bridge.py"
        assert cmd[3].endswith("task_xyz.json")
        return DummyProc()
        
    monkeypatch.setattr("subprocess.run", mock_run)
    
    res = execute_task(task, "w1", "QA_WORKER")
    assert res["status"] == "SUCCESS"
    assert res["stdout"] == "ok"
    assert res["worker_id"] == "w1"
    assert "result_id" in res
    
def test_execute_task_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "events" / "agent-states").mkdir(parents=True)
    
    task = {"task_id": "task_xyz", "goal_id": "g1"}
    
    class DummyProc:
        returncode = 1
        stdout = ""
        stderr = "error"
        
    def mock_run(cmd, *args, **kwargs):
        assert cmd[1] == "scripts/run_antigravity_bridge.py"
        return DummyProc()
        
    monkeypatch.setattr("subprocess.run", mock_run)
    
    res = execute_task(task, "w1", "SOME_OTHER_ROLE")
    assert res["status"] == "FAILED"
    assert res["stderr"] == "error"

def test_execute_task_exception(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "events" / "agent-states").mkdir(parents=True)
    
    task = {"task_id": "task_xyz"}
    
    def mock_run(*args, **kwargs):
        raise RuntimeError("boom")
        
    monkeypatch.setattr("subprocess.run", mock_run)
    
    res = execute_task(task, "w1", "QA_WORKER")
    assert res["status"] == "FAILED"
    assert "boom" in res["stderr"]

def test_main_missing_key(monkeypatch, capsys):
    monkeypatch.delenv("COURIER_API_KEY", raising=False)
    import scripts.bodyguard_daemon as bd
    bd.API_KEY = None
    main()
    out, _ = capsys.readouterr()
    assert "COURIER_API_KEY is required" in out

def test_main_loop(monkeypatch):
    import scripts.bodyguard_daemon as bd
    bd.API_KEY = "testkey"
    bd.BODYGUARDS = ["agent-bodyguard-alpha"]
    
    # Track calls
    req_post_calls = []
    
    class DummyResp:
        def __init__(self, sc, j=None):
            self.status_code = sc
            self._j = j or {}
        def json(self):
            return self._j
            
    # Mock requests.post
    def mock_post(url, *args, **kwargs):
        req_post_calls.append(url)
        if "/workers/register" in url:
            return DummyResp(200)
        elif "/tasks/claim" in url:
            return DummyResp(200, {"task": {"task_id": "t1"}})
        elif "/tasks/result" in url:
            return DummyResp(200)
        raise ValueError(url)
    monkeypatch.setattr("requests.post", mock_post)
    
    # Mock execute_task
    monkeypatch.setattr(bd, "execute_task", lambda t, w, r: {"status": "SUCCESS"})
    monkeypatch.setattr(bd, "get_temporary_role", lambda w: "R")
    
    # Break infinite loop by monkeypatching time.sleep to raise an exception
    def mock_sleep(s):
        raise InterruptedError("stop")
    monkeypatch.setattr("time.sleep", mock_sleep)
    
    with pytest.raises(InterruptedError):
        main()
        
    assert len(req_post_calls) >= 3
    assert any("/workers/register" in c for c in req_post_calls)
    assert any("/tasks/claim" in c for c in req_post_calls)
    assert any("/tasks/result" in c for c in req_post_calls)

def test_main_registration_exception(monkeypatch, capsys):
    import scripts.bodyguard_daemon as bd
    bd.API_KEY = "testkey"
    bd.BODYGUARDS = ["agent-bodyguard-alpha"]
    
    def mock_post(url, *args, **kwargs):
        if "/workers/register" in url:
            raise requests.exceptions.ConnectionError("conn refused")
        return mock.MagicMock()
        
    monkeypatch.setattr("requests.post", mock_post)
    
    def mock_sleep(s):
        raise InterruptedError("stop")
    monkeypatch.setattr("time.sleep", mock_sleep)
    
    with pytest.raises(InterruptedError):
        main()
        
    out, _ = capsys.readouterr()
    assert "Failed to register" in out
