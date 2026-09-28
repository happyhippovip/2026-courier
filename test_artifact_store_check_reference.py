import pytest
import pathlib
from scripts.artifact_store import ArtifactStore

def test_check_reference_binding(tmp_path):
    store = ArtifactStore(tmp_path)
    binding = {"goal_id": "g1", "task_id": "t1", "attempt_id": "a1", "dispatch_id": "d1", "worker_id": "w1"}
    record = store.put(b"hello", name="test.txt", binding=binding)
    
    ref = {"artifact_id": record["artifact_id"], "path": "test.txt", "sha256": record["sha256"]}
    store.check_reference(ref, binding)

test_check_reference_binding(pathlib.Path("test_art_store2"))
print("Passed!")
