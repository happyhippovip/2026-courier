import hashlib
def test_upload_rejection_converts_to_failed_result(tmp_path, monkeypatch):
    import scripts.windows_worker.daemon as daemon
    import urllib.error
    
    sha256 = hashlib.sha256(b"x").hexdigest()
    task = {
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
    
    def mock_urlopen(req, data=None, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 413, "Payload Too Large", {}, None)
        
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    
    outcome = daemon.upload_pending_artifacts(task, tmp_path / "state.json")
    print("Outcome:", outcome)

