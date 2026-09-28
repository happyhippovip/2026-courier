import pytest
from scripts.courier_verifier import verify_artifacts

def test_verify_artifacts_rejects_duplicates():
    task = {"artifacts": ["out1.txt", "out2.txt"]}
    
    result = {
        "provider": "github",  # so it bypasses fetch check
        "artifacts": [
            {"path": "out1.txt", "sha256": "x"},
            {"path": "out1.txt", "sha256": "x"},
        ]
    }
    
    v = verify_artifacts(task, result)
    print("VERDICT:", v)

test_verify_artifacts_rejects_duplicates()
