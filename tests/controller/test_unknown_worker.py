import pytest
import requests
from ctrl_helpers import LiveService, task_body

def test_unknown_worker_rejected(tmp_path):
    srv = LiveService(tmp_path / "home")
    
    # Create a task
    res = srv.session.post(f"{srv.base}/v1/tasks", json=task_body(max_attempts=1))
    assert res.status_code in (200, 201)
    
    # Try to claim with unknown worker
    claim_res = srv.session.post(f"{srv.base}/v1/claim", json={"worker_id": "UNKNOWN_WORKER"})
    assert claim_res.status_code == 400
    assert claim_res.json()["error"] == "invalid_worker_id"

    srv.stop()
