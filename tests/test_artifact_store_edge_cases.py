import hashlib
import os
import pytest
from scripts.artifact_store import ArtifactStore, ArtifactError

BINDING = {"goal_id": "g", "task_id": "t", "attempt_id": "t:attempt:1",
           "dispatch_id": "dispatch-1", "worker_id": "WINDOWS-01"}

def test_from_env(monkeypatch):
    monkeypatch.setenv("COURIER_ARTIFACT_DIR", "/tmp/mock-dir")
    monkeypatch.setenv("COURIER_ARTIFACT_MAX_BYTES", "42")
    store = ArtifactStore.from_env()
    assert str(store.root) == os.path.normpath("/tmp/mock-dir")
    assert store.max_bytes == 42

def test_put_corrupted_blob(tmp_path):
    store = ArtifactStore(tmp_path)
    data = b"mydata"
    record = store.put(data, name="x.txt", binding=BINDING)
    
    # Corrupt the blob directly on disk
    blob_path = store._blob_path(record["sha256"])
    blob_path.write_bytes(b"corrupted")
    
    # Try to put the same data again
    with pytest.raises(ArtifactError, match="stored blob is corrupt"):
        store.put(data, name="x.txt", binding=BINDING)

def test_put_record_conflict(tmp_path):
    store = ArtifactStore(tmp_path)
    data = b"mydata"
    record = store.put(data, name="x.txt", binding=BINDING)
    
    # Corrupt the record on disk
    record_path = store._record_path(record["artifact_id"])
    record_path.write_text('{"bad": "json"}')
    
    with pytest.raises(ArtifactError, match="artifact record conflict"):
        store.put(data, name="x.txt", binding=BINDING)

def test_read_bytes_missing_blob(tmp_path):
    store = ArtifactStore(tmp_path)
    data = b"mydata"
    record = store.put(data, name="x.txt", binding=BINDING)
    
    # Delete the blob
    blob_path = store._blob_path(record["sha256"])
    blob_path.unlink()
    
    with pytest.raises(ArtifactError, match="artifact bytes missing"):
        store.read_bytes(record["artifact_id"])
