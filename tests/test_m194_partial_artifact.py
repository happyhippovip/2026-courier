import pytest
import json
import hashlib
from io import BytesIO
from scripts.artifact_store import ArtifactStore, ArtifactError

def test_m194_partial_truncated_upload(tmp_path):
    store = ArtifactStore(tmp_path)
    
    task_binding = {
        "goal_id": "g1",
        "task_id": "t1",
        "attempt_id": "t1:attempt:1",
        "dispatch_id": "t1:dispatch:1",
        "worker_id": "w1"
    }
    
    full_data = b"This is the complete result data."
    actual_sha = hashlib.sha256(full_data).hexdigest()
    actual_size = len(full_data)
    
    # 1. Simulate a truncated read (e.g. connection dropped)
    truncated_data = full_data[:10]
    
    with pytest.raises(ArtifactError, match="uploaded bytes do not match the claimed sha256"):
        store.put(
            truncated_data,
            name="result.json",
            binding=task_binding,
            claimed_sha256=actual_sha,  # Claimed hash of the full data
            claimed_size=actual_size
        )
        
    # 2. Simulate size matching but hash mismatch (corruption)
    corrupted_data = b"This is the compLete result data."  # Same length, one byte diff
    with pytest.raises(ArtifactError, match="uploaded bytes do not match the claimed sha256"):
        store.put(
            corrupted_data,
            name="result.json",
            binding=task_binding,
            claimed_sha256=actual_sha,
            claimed_size=actual_size
        )

    # 3. Simulate size mismatch alone
    with pytest.raises(ArtifactError, match="uploaded bytes do not match the claimed size"):
        store.put(
            truncated_data,
            name="result.json",
            binding=task_binding,
            claimed_size=actual_size  # No sha provided, just size
        )

    # 4. Successful full upload
    record = store.put(
        full_data,
        name="result.json",
        binding=task_binding,
        claimed_sha256=actual_sha,
        claimed_size=actual_size
    )
    assert record["sha256"] == actual_sha
    assert record["size"] == actual_size

if __name__ == "__main__":
    pytest.main(["-v", __file__])
