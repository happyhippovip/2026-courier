import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.provider_hibernation import (
    LaneState,
    ContinuationCheckpoint,
    should_hibernate,
    LaneHibernator,
    Resource
)

def test_should_hibernate():
    # Should not hibernate if there are local units
    assert not should_hibernate(["unit1"], ["provider1"], True, False)
    
    # Should not hibernate if no provider units
    assert not should_hibernate([], [], True, False)
    
    # Should not hibernate if circuits not open
    assert not should_hibernate([], ["provider1"], False, False)
    
    # Should not hibernate if fallback available
    assert not should_hibernate([], ["provider1"], True, True)
    
    # Should hibernate if idle/blocked: no local, has provider, circuits open, no fallback
    assert should_hibernate([], ["provider1"], True, False)

def test_lane_hibernator_register_resource():
    hibernator = LaneHibernator()
    hibernator.register_resource("watch_1", "watcher", essential=False)
    assert "watch_1" in hibernator.resources
    assert hibernator.resources["watch_1"].kind == "watcher"
    assert not hibernator.resources["watch_1"].essential

def test_lane_hibernator_hibernate_and_resume():
    hibernator = LaneHibernator()
    
    released_list = []
    def mock_release_hook(name):
        released_list.append(name)
        
    hibernator.register_resource("watch_1", "watcher", essential=False, release_hook=mock_release_hook)
    hibernator.register_resource("desk_1", "human_desk", essential=True, release_hook=mock_release_hook)
    
    checkpoint = ContinuationCheckpoint(task_id="T-123")
    
    report = hibernator.hibernate(checkpoint)
    
    assert hibernator.state == LaneState.HIBERNATED
    assert "watch_1" in report["released"]
    assert "desk_1" in report["retained"]
    assert "watch_1" in released_list
    assert "desk_1" not in released_list
    
    # Attempting to hibernate again should raise error
    with pytest.raises(RuntimeError):
        hibernator.hibernate(checkpoint)
        
    # Resume
    resumed_checkpoint = hibernator.resume()
    assert resumed_checkpoint.task_id == "T-123"
    assert hibernator.state == LaneState.ACTIVE
    
    # Attempting to resume when active should raise error
    with pytest.raises(RuntimeError):
        hibernator.resume()

def test_serialization():
    hibernator = LaneHibernator()
    hibernator.register_resource("pty_1", "pty", essential=False)
    
    checkpoint = ContinuationCheckpoint(task_id="T-456")
    hibernator.hibernate(checkpoint)
    
    data = hibernator.to_dict()
    assert data["state"] == "HIBERNATED"
    assert data["checkpoint"]["task_id"] == "T-456"
    assert "pty_1" in data["resources"]
    
    new_hibernator = LaneHibernator.from_dict(data)
    assert new_hibernator.state == LaneState.HIBERNATED
    assert new_hibernator.checkpoint.task_id == "T-456"
    assert "pty_1" in new_hibernator.resources
    assert new_hibernator.resources["pty_1"].kind == "pty"
