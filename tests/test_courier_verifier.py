import pytest
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from scripts.courier_verifier import verify_artifact, fetch_artifact, verify_artifacts, run_loop

def test_verify_artifact_missing():
    with patch("os.path.exists", return_value=False):
        assert verify_artifact("missing.txt", "abc") == False

def test_verify_artifact_match(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    # sha256 of "hello" is 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert verify_artifact(str(f), expected) == True

def test_verify_artifact_mismatch(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello2")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert verify_artifact(str(f), expected) == False

def test_verify_artifact_exception(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello")
    with patch("builtins.open", side_effect=PermissionError("no access")):
        assert verify_artifact(str(f), "abc") == False

def test_fetch_artifact_success():
    with patch("scripts.courier_verifier.requests.get") as mock_get:
        mock_meta = MagicMock()
        mock_meta.json.return_value = {"id": "art-123"}
        
        mock_blob = MagicMock()
        mock_blob.content = b"hello"
        
        mock_get.side_effect = [mock_meta, mock_blob]
        
        with patch("scripts.courier_verifier.MAX_ARTIFACT_BYTES", 100):
            meta, data = fetch_artifact("art-123")
            assert meta == {"id": "art-123"}
            assert data == b"hello"

def test_fetch_artifact_too_large():
    with patch("scripts.courier_verifier.requests.get") as mock_get:
        mock_meta = MagicMock()
        mock_meta.json.return_value = {"id": "art-123"}
        
        mock_blob = MagicMock()
        mock_blob.content = b"hello"
        
        mock_get.side_effect = [mock_meta, mock_blob]
        
        with patch("scripts.courier_verifier.MAX_ARTIFACT_BYTES", 2): # less than "hello"
            with pytest.raises(ValueError, match="exceeds size limit"):
                fetch_artifact("art-123")

def test_verify_artifacts_missing_expected():
    task = {"artifacts": ["output.txt"]}
    result = {"artifacts": [{"path": "other.txt"}]}
    assert verify_artifacts(task, result)[0] == "FAIL"

def test_verify_artifacts_no_artifacts():
    task = {}
    result = {"artifacts": []}
    assert verify_artifacts(task, result)[0] == "FAIL"

def test_verify_artifacts_remote_target_not_uploaded():
    task = {"target_agent": "mac-worker"}
    result = {"artifacts": [{"path": "local.txt", "sha256": "abc"}]}
    assert verify_artifacts(task, result)[0] == "FAIL"

def test_verify_artifacts_local_verify_success():
    task = {"target_agent": "linux-worker"}
    result = {"artifacts": [{"path": "local.txt", "sha256": "abc"}]}
    
    with patch("scripts.courier_verifier.is_safe_artifact_name", return_value=True):
        assert verify_artifacts(task, result, local_verify=lambda p, s: True)[0] == "PASS"

def test_verify_artifacts_local_verify_unsafe():
    task = {"target_agent": "linux-worker"}
    result = {"artifacts": [{"path": "/etc/passwd", "sha256": "abc"}]}
    
    with patch("scripts.courier_verifier.is_safe_artifact_name", return_value=False):
        assert verify_artifacts(task, result, local_verify=lambda p, s: True)[0] == "FAIL"

def test_verify_artifacts_remote_uploaded_success():
    task = {"target_agent": "mac-worker"}
    result = {"artifacts": [{"path": "remote.txt", "artifact_id": "art-123"}]}
    
    def fake_fetch(aid):
        return {"id": aid}, b"hello"
        
    with patch("scripts.courier_verifier.verify_uploaded_artifact", return_value=(True, "")):
        assert verify_artifacts(task, result, fetch=fake_fetch)[0] == "PASS"

def test_verify_artifacts_remote_uploaded_hash_mismatch():
    task = {"target_agent": "mac-worker", "expected_artifacts": {"remote.txt": "wronghash"}}
    result = {"artifacts": [{"path": "remote.txt", "artifact_id": "art-123"}]}
    
    def fake_fetch(aid):
        return {"id": aid}, b"hello"
        
    with patch("scripts.courier_verifier.verify_uploaded_artifact", return_value=(True, "")):
        assert verify_artifacts(task, result, fetch=fake_fetch)[0] == "FAIL"

def test_verify_artifacts_remote_uploaded_rejected():
    task = {"target_agent": "mac-worker"}
    result = {"artifacts": [{"path": "remote.txt", "artifact_id": "art-123"}]}
    
    def fake_fetch(aid):
        return {"id": aid}, b"hello"
        
    with patch("scripts.courier_verifier.verify_uploaded_artifact", return_value=(False, "bad file")):
        assert verify_artifacts(task, result, fetch=fake_fetch)[0] == "FAIL"

def test_verify_artifacts_fetch_fails():
    task = {"target_agent": "mac-worker"}
    result = {"artifacts": [{"path": "remote.txt", "artifact_id": "art-123"}]}
    
    def fake_fetch(aid):
        raise Exception("net down")
        
    assert verify_artifacts(task, result, fetch=fake_fetch)[0] == "FAIL"

def test_run_loop_missing_key():
    with patch("scripts.courier_verifier.API_KEY", None):
        with pytest.raises(SystemExit):
            run_loop()

def test_run_loop_success():
    with patch("scripts.courier_verifier.API_KEY", "test"), \
         patch("scripts.courier_verifier.HEADERS", {}), \
         patch("scripts.courier_verifier.requests.get") as mock_get, \
         patch("scripts.courier_verifier.requests.post") as mock_post, \
         patch("scripts.courier_verifier.verify_artifacts", return_value=("PASS", None)), \
         patch("scripts.courier_verifier.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [
                {"task_id": "t1", "result": {"result_id": "r1", "artifacts": []}}
            ]
        }
        mock_get.return_value = mock_resp
        
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post.return_value = mock_post_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["task_id"] == "t1"
        assert kwargs["json"]["verdict"] == "PASS"

def test_run_loop_revenue_audit_pass():
    with patch("scripts.courier_verifier.API_KEY", "test"), \
         patch("scripts.courier_verifier.requests.get") as mock_get, \
         patch("scripts.courier_verifier.requests.post") as mock_post, \
         patch("subprocess.check_output") as mock_sub, \
         patch("scripts.courier_verifier.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [
                {
                    "task_id": "t1", 
                    "capabilities": ["revenue_safety_audit"],
                    "result": {"result_id": "r1", "artifacts": []}
                }
            ]
        }
        mock_get.return_value = mock_resp
        
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post.return_value = mock_post_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        mock_sub.assert_called_once()
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["verdict"] == "PASS"

def test_run_loop_revenue_audit_fail():
    import subprocess
    with patch("scripts.courier_verifier.API_KEY", "test"), \
         patch("scripts.courier_verifier.requests.get") as mock_get, \
         patch("scripts.courier_verifier.requests.post") as mock_post, \
         patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "cmd", output=b"err")), \
         patch("scripts.courier_verifier.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [
                {
                    "task_id": "t1", 
                    "capabilities": ["revenue_safety_audit"],
                    "result": {"result_id": "r1", "artifacts": []}
                }
            ]
        }
        mock_get.return_value = mock_resp
        
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post.return_value = mock_post_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
            
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["verdict"] == "FAIL"

def test_run_loop_task_processing_exception():
    with patch("scripts.courier_verifier.API_KEY", "test"), \
         patch("scripts.courier_verifier.requests.get") as mock_get, \
         patch("scripts.courier_verifier.verify_artifacts", side_effect=Exception("boom")), \
         patch("scripts.courier_verifier.time.sleep", side_effect=KeyboardInterrupt):
         
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tasks": [
                {"task_id": "t1", "result": {"result_id": "r1", "artifacts": []}}
            ]
        }
        mock_get.return_value = mock_resp
        
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
        
def test_run_loop_poll_exception():
    with patch("scripts.courier_verifier.API_KEY", "test"), \
         patch("scripts.courier_verifier.requests.get", side_effect=Exception("network down")), \
         patch("scripts.courier_verifier.time.sleep", side_effect=KeyboardInterrupt):
         
        try:
            run_loop()
        except KeyboardInterrupt:
            pass
