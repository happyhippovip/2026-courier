import json
import pytest
from unittest.mock import patch, MagicMock

@patch("subprocess.check_output")
@patch("urllib.request.urlopen")
def test_revenue_worker_result_format(mock_urlopen, mock_check_output, monkeypatch, tmp_path):
    import scripts.revenue_worker_adapter as adapter
    
    # Mock config
    monkeypatch.setattr(adapter, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(adapter, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(adapter, "LOGS_DIR", tmp_path / "logs"); (tmp_path / "logs").mkdir(); (tmp_path / "state").mkdir()
    
    # Mock subprocess output for revenue_v1_safety_baseline.py
    mock_check_output.return_value = json.dumps({"findings": []}).encode("utf-8")
    
    # Track HTTP posts
    posts = []
    def mock_http_post(config, endpoint, data=None):
        posts.append((endpoint, data))
        if endpoint == "/workers/register":
            return {"status": "ok"}
        if endpoint == "/tasks/claim":
            return {
                "task_id": "t1", 
                "attempt_id": "a1",
                "goal_id": "g1",
                "dispatch_id": "d1"
            }
        if endpoint == "/tasks/result":
            return {"status": "ok"}
        return None
    
    monkeypatch.setattr(adapter, "http_post", mock_http_post)
    
    # Mock urllib.request for /artifacts upload
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"artifact_id": "art-1234", "size": 100}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp
    
    # Run one iteration of the loop by replacing True with a counter
    counter = [1]
    def mock_sleep(s):
        if counter[0] <= 0:
            raise KeyboardInterrupt()
        counter[0] -= 1
        
    monkeypatch.setattr(adapter.time, "sleep", mock_sleep)
    
    # Run
    try:
        adapter.main()
    except KeyboardInterrupt:
        pass
        
    # Verify result format
    result_posts = [d for e, d in posts if e == "/tasks/result"]
    assert len(result_posts) >= 1
    res = result_posts[0]
    
    # Check DurableResult shape
    assert res["status"] == "SUCCESS"
    assert res["goal_id"] == "g1"
    assert res["task_id"] == "t1"
    assert res["attempt_id"] == "a1"
    assert res["dispatch_id"] == "d1"
    assert "worker_id" in res
    assert res["run_id"].startswith("run-")
    assert res["result_id"].startswith("result-")
    
    # Check artifacts array
    assert isinstance(res["artifacts"], list)
    assert len(res["artifacts"]) == 1
    art = res["artifacts"][0]
    assert art["path"] == "revenue_artifacts.zip"
    assert "sha256" in art
    assert "size" in art
    assert art["artifact_id"] == "art-1234"
    
    # Check that artifact upload was called
    assert mock_urlopen.called
    req = mock_urlopen.call_args[0][0]
    assert req.full_url.endswith("/artifacts")
