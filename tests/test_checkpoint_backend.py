import sys
import os
import shutil
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from checkpoint_backend import CheckpointManager, TaskCheckpoint, CheckpointState, determine_recovery_action

@pytest.fixture
def manager(tmp_path):
    storage = tmp_path / "checkpoints"
    yield CheckpointManager(str(storage))
    if storage.exists():
        shutil.rmtree(storage)

def test_checkpoint_roundtrip(manager):
    checkpoint = TaskCheckpoint(
        workkey="H1",
        state=CheckpointState.STARTED,
        context={"pid": "1234"}
    )
    
    manager.save_checkpoint(checkpoint)
    loaded = manager.load_checkpoint("H1")
    
    assert loaded is not None
    assert loaded.workkey == "H1"
    assert loaded.state == CheckpointState.STARTED
    assert loaded.context["pid"] == "1234"

def test_missing_checkpoint(manager):
    loaded = manager.load_checkpoint("NONEXISTENT")
    assert loaded is None

def test_state_transitions(manager):
    # Progress through states
    states = [
        CheckpointState.PLANNED,
        CheckpointState.STARTED,
        CheckpointState.MODIFIED,
        CheckpointState.TESTED,
        CheckpointState.VERIFIED,
        CheckpointState.COMMITTED,
        CheckpointState.PUSHED,
        CheckpointState.LANDED
    ]
    
    for state in states:
        checkpoint = TaskCheckpoint(workkey="H2", state=state, context={})
        manager.save_checkpoint(checkpoint)
        loaded = manager.load_checkpoint("H2")
        assert loaded.state == state

def test_recovery_action_does_not_treat_started_as_completed():
    checkpoint = TaskCheckpoint(workkey="H3", state=CheckpointState.STARTED, context={})
    action = determine_recovery_action(checkpoint)
    assert "restart from the beginning" in action.lower() or "clean up" in action.lower()
    assert "completed" not in action.lower()

def test_recovery_action_verified():
    checkpoint = TaskCheckpoint(workkey="H4", state=CheckpointState.VERIFIED, context={})
    action = determine_recovery_action(checkpoint)
    assert "commit" in action.lower()
