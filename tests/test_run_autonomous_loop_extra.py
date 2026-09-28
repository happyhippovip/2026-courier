import pytest
from pathlib import Path

def test_workflow_locks(tmp_path):
    import scripts.run_autonomous_loop as script
    
    events_dir = tmp_path / "events/locks"
    events_dir.mkdir(parents=True)
    
    class MockTracker:
        def update_visual_state(self, *args, **kwargs):
            pass
            
    runner = script.AutonomousLevel6Loop(
        repo_dir=tmp_path
    )
    runner.state_tracker = MockTracker()
    
    # acquire the lock
    acquired = runner.acquire_workflow_lock("wf_test")
    assert Path(acquired).exists()
    
    # release lock
    runner.release_workflow_lock("wf_test")
    assert not Path(acquired).exists()

