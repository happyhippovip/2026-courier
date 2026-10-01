import json
import os
import sys
import tempfile
import uuid
import hashlib
import io
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch, MagicMock, mock_open

import pytest
import urllib.error
import urllib.request

import scripts.windows_worker.daemon as daemon

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {}, clear=True):
        yield

def test_require_api_key(mock_env):
    daemon.API_KEY = ""
    with pytest.raises(daemon.MissingCredentialError):
        daemon.require_api_key()
    daemon.API_KEY = "test"
    daemon.require_api_key() # Should not raise

def test_apply_config_credentials(mock_env):
    # Set up global state so it's clean
    daemon.API_KEY = ""
    daemon.API_URL = ""
    
    with patch.dict(os.environ, {"COURIER_API_KEY": "env_key", "COURIER_SERVER": "http://env"}, clear=True):
        daemon.apply_config_credentials({})
        assert daemon.API_KEY == "" # wait, it only overrides if os.environ doesn't have it, but here it assumes it's already read
        # Let's mock how the script behaves initially. The script reads os.environ initially.
    
    # We can just test that it falls back to config if env is empty
    daemon.API_KEY = ""
    daemon.API_URL = ""
    with patch.dict(os.environ, {}, clear=True):
        daemon.apply_config_credentials({"COURIER_API_KEY": "config_key", "COURIER_SERVER": "http://config"})
        assert daemon.API_KEY == "config_key"
        assert daemon.API_URL == "http://config"

def test_load_config():
    with patch("builtins.open", mock_open(read_data='{"WORKER_ID": "w1"}')):
        config = daemon.load_config()
        assert config["WORKER_ID"] == "w1"

def test_register_worker():
    daemon.API_KEY = "key"
    with patch("urllib.request.urlopen") as mock_urlopen:
        assert daemon.register_worker("w1") is True
        mock_urlopen.assert_called_once()
        
    with patch("urllib.request.urlopen", side_effect=Exception("error")):
        assert daemon.register_worker("w1", release_task=True) is False

def test_upload_enabled():
    assert daemon.upload_enabled({"ARTIFACT_UPLOAD": "1"}) is True
    with patch.dict(os.environ, {"COURIER_ARTIFACT_UPLOAD": "true"}):
        assert daemon.upload_enabled({}) is True

def test_upload_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    daemon.API_KEY = "key"
    art_path = tmp_path / "test.txt"
    art_path.write_bytes(b"content")
    sha256 = hashlib.sha256(b"content").hexdigest()
    
    # Test valid upload
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"artifact_id": "art-1", "sha256": sha256, "size": 7}).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        
        outcome, rec = daemon.upload_artifact({"task_id": "t1"}, {"path": "test.txt", "sha256": sha256})
        assert outcome == "OK"
        assert rec["artifact_id"] == "art-1"
        
    # Test unsafe path
    outcome, _ = daemon.upload_artifact({}, {"path": "../test.txt", "sha256": sha256})
    assert outcome == "REJECTED"
    
    # Test changed hash
    art_path.write_bytes(b"changed")
    outcome, _ = daemon.upload_artifact({}, {"path": "test.txt", "sha256": sha256})
    assert outcome == "REJECTED"

def test_upload_artifact_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    daemon.API_KEY = "key"
    art_path = tmp_path / "test.txt"
    art_path.write_bytes(b"content")
    sha256 = hashlib.sha256(b"content").hexdigest()
    art = {"path": "test.txt", "sha256": sha256}
    
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 400, "msg", {}, None)):
        assert daemon.upload_artifact({}, art)[0] == "REJECTED"
        
    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("url", 500, "msg", {}, None)):
        assert daemon.upload_artifact({}, art)[0] == "UNDELIVERED"
        
    with patch("urllib.request.urlopen", side_effect=Exception("network")):
        assert daemon.upload_artifact({}, art)[0] == "UNDELIVERED"

    # Test invalid response (hash mismatch)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"artifact_id": "art-1", "sha256": "wrong", "size": 7}).encode()
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        assert daemon.upload_artifact({}, art)[0] == "REJECTED"

def test_upload_pending_artifacts():
    with patch("scripts.windows_worker.daemon.upload_artifact") as mock_upload, \
         patch("scripts.windows_worker.daemon.persist_task") as mock_persist:
        
        mock_upload.return_value = ("OK", {"artifact_id": "art-2", "size": 10})
        
        task = {"result_payload": {"artifacts": [{"artifact_id": "art-1"}, {"path": "new"}]}}
        assert daemon.upload_pending_artifacts(task, Path("dummy")) == "READY"
        
        mock_upload.return_value = ("REJECTED", None)
        task = {"result_payload": {"artifacts": [{"path": "fail"}]}}
        assert daemon.upload_pending_artifacts(task, Path("dummy")) == "REJECTED"

def test_http_post_result():
    daemon.API_KEY = "key"
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp
        assert daemon.http_post_result({}) == "DELIVERED"
        
    with patch("urllib.request.urlopen") as mock_urlopen:
        err = urllib.error.HTTPError("url", 400, "msg", {}, io.BytesIO(b"err"))
        mock_urlopen.side_effect = err
        assert daemon.http_post_result({}) == "REJECTED"

    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("time.sleep"):
        err = urllib.error.HTTPError("url", 500, "msg", {}, io.BytesIO(b"err"))
        mock_urlopen.side_effect = err
        assert daemon.http_post_result({}) == "UNDELIVERED"
        
    with patch("urllib.request.urlopen", side_effect=Exception("net")), patch("time.sleep"):
        assert daemon.http_post_result({}) == "UNDELIVERED"

def test_persist_task(tmp_path):
    f = tmp_path / "task.json"
    daemon.persist_task(f, {"k": "v"})
    assert json.loads(f.read_text()) == {"k": "v"}

def test_is_safe_artifact_path():
    assert daemon.is_safe_artifact_path("valid/path.txt") is True
    assert daemon.is_safe_artifact_path("../invalid") is False
    assert daemon.is_safe_artifact_path("/absolute") is False
    assert daemon.is_safe_artifact_path("C:\\windows") is False
    assert daemon.is_safe_artifact_path(None) is False

def test_build_result_payload(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    art_path = tmp_path / "art.txt"
    art_path.write_bytes(b"data")
    
    task = {"task_id": "t1", "artifacts": [{"path": "art.txt"}]}
    result = {"status": "SUCCESS", "run_id": "r1", "stdout": "ok"}
    config = {"WORKER_ID": "w1"}
    
    payload = daemon.build_result_payload(task, result, config)
    assert payload["status"] == "SUCCESS"
    assert len(payload["artifacts"]) == 1
    
    # Missing artifact
    task = {"task_id": "t1", "artifacts": [{"path": "missing.txt"}]}
    payload = daemon.build_result_payload(task, result, config)
    assert payload["status"] == "FAILED"
    assert "Missing artifact" in payload["stderr"]
    
    # Unsafe path
    task = {"task_id": "t1", "artifacts": [{"path": "../unsafe"}]}
    payload = daemon.build_result_payload(task, result, config)
    assert payload["status"] == "FAILED"
    assert "Unsafe artifact path" in payload["stderr"]
    
    # No artifact evidence for success
    task = {"task_id": "t1", "artifacts": []}
    payload = daemon.build_result_payload(task, result, config)
    assert payload["status"] == "FAILED"
    assert "No artifact evidence" in payload["stderr"]

def test_run_task():
    config = {"WORKER_ID": "w1"}
    task = {"task_id": "t1", "instruction": "echo test"}
    
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 123
        mock_proc.communicate.return_value = ("test out", "err out")
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc
        
        res = daemon.run_task(task, config)
        assert res["status"] == "SUCCESS"
        assert res["stdout"] == "test out"
        assert res["run_id"] == "123"
        
        # Exception case
        mock_popen.side_effect = Exception("crash")
        res = daemon.run_task(task, config)
        assert res["status"] == "FAILED"
        assert "crash" in res["stderr"]

def test_is_resource_pressure_high():
    with patch("subprocess.check_output", return_value=b" 50 \n 60 "):
        assert daemon.is_resource_pressure_high() is False
        
    with patch("subprocess.check_output", return_value=b" 90 \n 95 "):
        assert daemon.is_resource_pressure_high() is True
        
    with patch("subprocess.check_output", side_effect=Exception("err")):
        assert daemon.is_resource_pressure_high() is False

def test_acquire_lock(tmp_path):
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        # Provide a mock for msvcrt since it might not be available
        with patch.dict("sys.modules", {"msvcrt": MagicMock()}):
            lock1 = daemon.acquire_lock("w1")
            assert lock1 is not None
            
            with patch("os.open", side_effect=OSError("locked")):
                assert daemon.acquire_lock("w1") is None

def test_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    with patch("scripts.windows_worker.daemon.load_config", return_value={"WORKER_ID": "w1"}), \
         patch("scripts.windows_worker.daemon.apply_config_credentials"), \
         patch("scripts.windows_worker.daemon.require_api_key"), \
         patch("scripts.windows_worker.daemon.acquire_lock", return_value=str(tmp_path / "lock")), \
         patch("scripts.windows_worker.daemon.STATE_DIR", tmp_path), \
         patch("urllib.request.urlopen") as mock_urlopen, \
         patch("scripts.windows_worker.daemon.run_task", return_value={"status": "SUCCESS"}) as mock_run, \
         patch("scripts.windows_worker.daemon.build_result_payload", return_value={"ok": 1}), \
         patch("scripts.windows_worker.daemon.upload_pending_artifacts", return_value="READY"), \
         patch("scripts.windows_worker.daemon.http_post_result", return_value="DELIVERED"), \
         patch("time.sleep", side_effect=KeyboardInterrupt):
         
         mock_resp = MagicMock()
         mock_resp.read.return_value = b'{"task": {"task_id": "t1"}}'
         mock_resp.__enter__.return_value = mock_resp
         mock_urlopen.return_value = mock_resp
         
         try:
             daemon.loop()
         except KeyboardInterrupt:
             pass
         
         mock_run.assert_called_once()
