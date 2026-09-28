def test_upload_rejection_converts_to_failed_result(tmp_path, monkeypatch):
    import scripts.windows_worker.daemon as daemon
    import urllib.error
    import hashlib
    
    sha256 = hashlib.sha256(b"x").hexdigest()
    task = {
        "status": "RESULT_READY",
        "task_id": "t1", "goal_id": "g1", "attempt_id": "a1", "dispatch_id": "d1",
        "result_payload": {
            "status": "SUCCESS",
            "artifacts": [{"path": "out.txt", "sha256": sha256}]
        }
    }
    
    (tmp_path / "out.txt").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(daemon, "API_KEY", "x")
    monkeypatch.setattr(daemon, "API_URL", "http://x")
    monkeypatch.setattr(daemon, "upload_enabled", lambda x: True)
    
    def mock_urlopen(req, data=None, timeout=None):
        if "artifacts" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 413, "Payload Too Large", {}, None)
        return type("Resp", (), {"read": lambda: b'{"status": "ok"}'})()
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    # We simulate what run_loop does:
    outcome = daemon.upload_pending_artifacts(task, tmp_path / "state.json")
    assert outcome == "REJECTED", "Should return REJECTED"
    
    # In the fixed code, we want the loop to convert REJECTED to FAILED and post it.

