import pytest
import os
import json
import urllib.error
from unittest.mock import patch, MagicMock
from scripts.windows_worker.daemon import http_post_result, register_worker, run_task, loop, is_resource_pressure_high, acquire_lock

def test_register_worker_success():
    with patch("urllib.request.urlopen") as mock_open:
        assert register_worker("w1") == True

def test_http_post_result_duplicate():
    with patch("urllib.request.urlopen") as mock_open:
        err = urllib.error.HTTPError("url", 409, "Conflict", {}, None)
        err.read = MagicMock(return_value=b'{"error": "ACK_DUPLICATE"}')
        mock_open.side_effect = err
        http_post_result({"status": "SUCCESS"})

def test_run_task_provider_wait():
    res = run_task({"action": "provider_wait", "task_id": "t1"}, {"WORKER_ID": "w1"})
    assert res["status"] == "PROVIDER_WAIT"

def test_is_resource_pressure_high_false():
    with patch.dict(os.environ, {"SIMULATE_CPU_PERCENT": "10", "SIMULATE_MEM_PERCENT": "10"}):
        assert is_resource_pressure_high({}) == False

def test_is_resource_pressure_high_true():
    with patch.dict(os.environ, {"SIMULATE_CPU_PERCENT": "101"}):
        assert is_resource_pressure_high({}) == True

def test_acquire_lock_success(tmp_path):
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        lock = acquire_lock("test-w1")
        assert lock is not None
        assert os.path.exists(lock)
        os.remove(lock)

