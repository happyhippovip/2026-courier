import pytest
import os
from courier_core.checkpoint_store import CheckpointStore
from courier_core.idempotency import IdempotencyCore

def test_checkpoint_store(tmp_path):
    store = CheckpointStore(str(tmp_path / "checkpoints"))
    data = {"state": "EXECUTING", "progress": 50}
    store.save_checkpoint("cp-1", data)
    loaded = store.load_checkpoint("cp-1")
    assert loaded == data

def test_idempotency_core():
    core = IdempotencyCore()
    assert not core.is_executed("tx-1")
    
    core.store_result("tx-1", {"status": "success"})
    assert core.is_executed("tx-1")
    assert core.get_result("tx-1") == {"status": "success"}
    
    with pytest.raises(ValueError):
        core.store_result("tx-1", {"status": "duplicate"})
