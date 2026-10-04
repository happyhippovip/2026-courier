import sys
import os
import json
import shutil
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from checkpoint_backend import CheckpointManager, TaskCheckpoint, CheckpointState

@pytest.fixture
def manager(tmp_path):
    storage = tmp_path / "checkpoints"
    yield CheckpointManager(str(storage))
    if storage.exists():
        shutil.rmtree(storage)

def test_interruption_before_write(manager):
    checkpoint1 = TaskCheckpoint("H1", CheckpointState.STARTED, {})
    manager.save_checkpoint(checkpoint1)
    
    # Simulate a crash before a new write begins by literally doing nothing 
    # to the file system, asserting the state remains as the last known good.
    loaded = manager.load_checkpoint("H1")
    assert loaded.state == CheckpointState.STARTED

def test_interruption_during_write(manager, monkeypatch):
    checkpoint1 = TaskCheckpoint("H2", CheckpointState.STARTED, {})
    manager.save_checkpoint(checkpoint1)
    
    checkpoint2 = TaskCheckpoint("H2", CheckpointState.MODIFIED, {})
    
    # Mock json.dump to fail halfway through writing
    original_dump = json.dump
    def faulty_dump(data, fp, **kwargs):
        fp.write('{"partial": "jso') # Write garbage
        raise RuntimeError("Crash during write!")
        
    monkeypatch.setattr(json, "dump", faulty_dump)
    
    with pytest.raises(RuntimeError):
        manager.save_checkpoint(checkpoint2)
        
    # The last known good checkpoint MUST survive
    loaded = manager.load_checkpoint("H2")
    assert loaded.state == CheckpointState.STARTED
    
    # The temp file might exist with garbage, but the main file is untouched
    temp_path = manager.storage_dir / "H2.checkpoint.tmp"
    assert temp_path.exists()
    assert temp_path.read_text() == '{"partial": "jso'

def test_interruption_after_temporary_write_before_replace(manager, monkeypatch):
    checkpoint1 = TaskCheckpoint("H3", CheckpointState.STARTED, {})
    manager.save_checkpoint(checkpoint1)
    
    checkpoint2 = TaskCheckpoint("H3", CheckpointState.MODIFIED, {})
    
    # Mock Path.replace to simulate a crash right after the temp file is written
    # but BEFORE the atomic replace happens
    def faulty_replace(self, target):
        raise RuntimeError("Crash before atomic replace!")
        
    monkeypatch.setattr(Path, "replace", faulty_replace)
    
    with pytest.raises(RuntimeError):
        manager.save_checkpoint(checkpoint2)
        
    # The last known good checkpoint MUST survive
    loaded = manager.load_checkpoint("H3")
    assert loaded.state == CheckpointState.STARTED
    
    # The temp file exists and has the full JSON, but hasn't replaced the real file
    temp_path = manager.storage_dir / "H3.checkpoint.tmp"
    assert temp_path.exists()
    
def test_interruption_after_final_commit(manager):
    checkpoint1 = TaskCheckpoint("H4", CheckpointState.STARTED, {})
    manager.save_checkpoint(checkpoint1)
    
    checkpoint2 = TaskCheckpoint("H4", CheckpointState.MODIFIED, {})
    manager.save_checkpoint(checkpoint2)
    
    # "Crash" after successful save
    loaded = manager.load_checkpoint("H4")
    assert loaded.state == CheckpointState.MODIFIED
    
    # Temp file should be gone
    temp_path = manager.storage_dir / "H4.checkpoint.tmp"
    assert not temp_path.exists()
