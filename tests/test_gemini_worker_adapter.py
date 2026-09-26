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

def test_gemini_worker_timeout_kills_child_and_fails_closed(tmp_path, monkeypatch):
    """TimeoutExpired must kill+reap the child and yield FAILED/TIMEOUT, never escape."""
    monkeypatch.chdir(tmp_path)
    task_file = tmp_path / "dummy_task.json"
    task_file.write_text(json.dumps({"task_id": "gemini-1", "instruction": "do it"}))

    mock_process = mock.Mock()
    mock_process.pid = 1234
    mock_process.communicate.side_effect = [
        subprocess.TimeoutExpired("agy", 60),
        ("", "timed out"),
    ]

    with mock.patch("subprocess.Popen", return_value=mock_process):
        with mock.patch("scripts.gemini_worker_adapter.consume") as mock_consume:
            pid, dispatch_ref, result_ref = gemini_worker_adapter.run_worker(str(task_file))

    mock_process.kill.assert_called_once_with()
    assert mock_process.communicate.call_count == 2
    assert pid == 1234
    res = json.loads((tmp_path / result_ref).read_text())
    assert res["status"] == "FAILED"
    assert res["reason"] == "TIMEOUT"
    mock_consume.assert_called_once()

