import pytest
from scripts.artifact_store import is_safe_artifact_name, artifact_id_for

def test_m198_case_sensitivity():
    # 1. Names are treated securely
    assert is_safe_artifact_name("Result.json")
    assert is_safe_artifact_name("result.json")
    
    # 2. Case variations produce distinct artifact IDs
    binding = {
        "goal_id": "g1",
        "task_id": "t1",
        "attempt_id": "a1",
        "dispatch_id": "d1",
        "worker_id": "w1"
    }
    
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" # empty
    
    id1 = artifact_id_for(binding, "Result.json", sha256)
    id2 = artifact_id_for(binding, "result.json", sha256)
    
    assert id1 != id2, "Case variations must yield distinct artifact IDs"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
