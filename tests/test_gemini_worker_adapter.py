import json
import subprocess
import os
import sys
from unittest import mock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts import gemini_worker_adapter

def test_gemini_worker_adapter_success(tmp_path):
    task_file = tmp_path / "dummy_task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "gemini-1", "instruction": "do it"}, f)
        
    mock_process = mock.Mock()
    mock_process.pid = 1234
    mock_process.communicate.return_value = ("```json\n{\"status\": \"SUCCESS\"}\n```", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        with mock.patch("scripts.gemini_worker_adapter.consume") as mock_consume:
            with mock.patch("os.chdir"): # prevent actual directory changes if any
                pid, dispatch_ref, result_ref = gemini_worker_adapter.run_worker(str(task_file))
                
    assert pid == 1234
    assert result_ref == "gemini_result_gemini-1.json"
    
    # Check that it wrote the file
    assert os.path.exists(result_ref)
    with open(result_ref, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"
        assert res["pid"] == 1234
        
    # cleanup
    os.remove(result_ref)

def test_gemini_worker_rejects_path_unsafe_task_id(tmp_path):
    task_file = tmp_path / "evil.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "../../outside", "instruction": "do it"}, f)

    with mock.patch("subprocess.Popen") as popen:
        with pytest.raises(ValueError, match="path-safe"):
            gemini_worker_adapter.run_worker(str(task_file))

    popen.assert_not_called()


def test_gemini_worker_negative_mode(tmp_path):
    task_file = tmp_path / "dummy_task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "gemini-neg", "instruction": "do it"}, f)
        
    mock_process = mock.Mock()
    mock_process.pid = 9999
    # Malformed output
    mock_process.communicate.return_value = ("this is garbage", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        with mock.patch("scripts.gemini_worker_adapter.consume") as mock_consume:
            with mock.patch("os.chdir"):
                pid, dispatch_ref, result_ref = gemini_worker_adapter.run_worker(str(task_file), negative_test=True)
                
    assert pid == 9999
    assert os.path.exists(result_ref)
    with open(result_ref, "r") as f:
        res = json.load(f)
        assert res["status"] == "FAILED"
        assert res["reason"] == "INVALID_RESULT"
        
    os.remove(result_ref)

def test_gemini_worker_out_clean_ticks(tmp_path):
    task_file = tmp_path / "dummy_task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "gemini-ticks", "instruction": "do it"}, f)
        
    mock_process = mock.Mock()
    mock_process.pid = 1111
    mock_process.communicate.return_value = ("```\n{\"status\": \"SUCCESS\"}\n```", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        with mock.patch("scripts.gemini_worker_adapter.consume") as mock_consume:
            with mock.patch("os.chdir"):
                pid, dispatch_ref, result_ref = gemini_worker_adapter.run_worker(str(task_file))
                
    with open(result_ref, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"
    os.remove(result_ref)

def test_gemini_worker_out_clean_no_ticks(tmp_path):
    task_file = tmp_path / "dummy_task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "gemini-noticks", "instruction": "do it"}, f)
        
    mock_process = mock.Mock()
    mock_process.pid = 2222
    mock_process.communicate.return_value = ("{\"status\": \"SUCCESS\"}", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        with mock.patch("scripts.gemini_worker_adapter.consume") as mock_consume:
            with mock.patch("os.chdir"):
                pid, dispatch_ref, result_ref = gemini_worker_adapter.run_worker(str(task_file))
                
    with open(result_ref, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"
    os.remove(result_ref)

def test_consume_creates_new(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res_json = {"status": "SUCCESS", "dispatch_ref": "ref1", "pid": 12}
    gemini_worker_adapter.consume(res_json, "task1", "ref.json")
    
    with open("central_state.json", "r") as f:
        state = json.load(f)
    assert state["tasks"]["task1"]["reconciled_status"] == "SUCCESS"
    assert state["tasks"]["task1"]["real_wall"] == "HUMAN_REVIEW_REQUIRED"

def test_consume_updates_existing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with open("central_state.json", "w") as f:
        json.dump({"tasks": {"task_old": {}}}, f)
        
    res_json = {"status": "FAILED"}
    gemini_worker_adapter.consume(res_json, "task2", "ref.json")
    
    with open("central_state.json", "r") as f:
        state = json.load(f)
    assert "task_old" in state["tasks"]
    assert state["tasks"]["task2"]["reconciled_status"] == "FAILED"
    assert state["tasks"]["task2"]["real_wall"] == "DIAGNOSTIC_REQUIRED"

def test_main_positive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_process = mock.Mock()
    mock_process.pid = 111
    mock_process.communicate.return_value = ("```json\n{\"status\": \"SUCCESS\"}\n```", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        import runpy
        import sys
        sys.argv = ["gemini_worker_adapter.py", "positive"]
        runpy.run_path("C:/Users/lol/2026-workspace/2026-courier/scripts/gemini_worker_adapter.py", run_name="__main__")
        
    assert os.path.exists("dummy_task_2.json")
    assert os.path.exists("gemini_result_task-gemini-002.json")
    assert os.path.exists("central_state.json")

def test_main_negative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mock_process = mock.Mock()
    mock_process.pid = 222
    mock_process.communicate.return_value = ("garbage", "")
    
    with mock.patch("subprocess.Popen", return_value=mock_process):
        import runpy
        import sys
        sys.argv = ["gemini_worker_adapter.py", "negative"]
        runpy.run_path("C:/Users/lol/2026-workspace/2026-courier/scripts/gemini_worker_adapter.py", run_name="__main__")
        
    assert os.path.exists("dummy_task_3.json")
    assert os.path.exists("gemini_result_task-gemini-003-invalid.json")
