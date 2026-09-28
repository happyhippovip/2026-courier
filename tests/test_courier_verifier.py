import pytest
from unittest.mock import MagicMock

def test_verify_artifacts_success():
    import scripts.courier_verifier as verifier
    
    task = {
        "task_id": "t1",
        "goal_id": "g1",
        "attempt_id": "a1",
        "dispatch_id": "d1",
        "worker_id": "w1"
    }
    result = {
        "status": "SUCCESS",
        "artifacts": [{"artifact_id": "art-1", "path": "out.txt", "sha256": "abc"}]
    }
    
    import hashlib
    res_hash = hashlib.sha256(b"hello").hexdigest()
    result["artifacts"][0]["sha256"] = res_hash
    result["artifacts"][0]["size"] = 5
    
    record = {
        "sha256": res_hash, 
        "size": 5,
        "name": "out.txt",
        "artifact_id": "art-1",
        "task_id": "t1",
        "goal_id": "g1",
        "attempt_id": "a1",
        "dispatch_id": "d1",
        "worker_id": "w1"
    }
    
    fetch = MagicMock(return_value=(record, b"hello"))
    
    res = verifier.verify_artifacts(task, result, fetch=fetch)
    assert res == "PASS"
    
def test_verify_artifacts_missing_id():
    import scripts.courier_verifier as verifier
    task = {"task_id": "t1", "target_agent": "mac"}
    result = {
        "status": "SUCCESS",
        "artifacts": [{"path": "out.txt", "sha256": "abc"}] # no artifact_id
    }
    
    res = verifier.verify_artifacts(task, result, fetch=MagicMock())
    assert res == "FAIL"
