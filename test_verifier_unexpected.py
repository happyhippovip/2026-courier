import pytest
from scripts.courier_verifier import verify_artifacts

def test_verify_artifacts_rejects_unexpected():
    task = {"artifacts": ["expected.txt"], "target_agent": "linux"}
    
    result = {
        "provider": "github",
        "artifacts": [
            {"path": "expected.txt", "sha256": "x"},
            {"path": "unexpected.txt", "sha256": "x"},
        ]
    }
    
    assert verify_artifacts(task, result, fetch=lambda x: ({}, b""), local_verify=lambda p, s: True) == "FAIL"

test_verify_artifacts_rejects_unexpected()
print("Passed!")
