import pytest
from scripts.provider_hibernation import LaneHibernator, ContinuationCheckpoint, LaneState

def test_hibernate_checkpoint_before_release_and_hook_failure_retained():
    released_log = []
    
    def crash_hook(name):
        raise RuntimeError("Crash")
        
    lane = LaneHibernator()
    lane.register_resource("provider:muse", "provider", release_hook=lambda n: released_log.append(n))
    lane.register_resource("ui:hub", "ui", release_hook=crash_hook)
    lane.register_resource("watcher:local", "watcher") # No hook
    
    checkpoint = ContinuationCheckpoint(task_id="t-check")
    
    # In old code, this would crash or misreport.
    # In old code, checkpoint was set AFTER loop.
    report = lane.hibernate(checkpoint)
    
    assert lane.state == LaneState.HIBERNATED
    assert lane.checkpoint == checkpoint # checkpoint must be saved even if something crashed (though we catch it now)
    
    # provider:muse should be released (hook succeeded)
    # ui:hub should be retained (hook failed)
    # watcher:local should be retained (no hook)
    assert "provider:muse" in report["released"]
    assert "ui:hub" in report["retained"]
    assert "watcher:local" in report["retained"]
    
def test_hibernate_is_idempotent():
    released_log = []
    lane = LaneHibernator()
    lane.register_resource("provider:muse", "provider", release_hook=lambda n: released_log.append(n))
    
    checkpoint = ContinuationCheckpoint(task_id="t-check")
    report1 = lane.hibernate(checkpoint)
    report2 = lane.hibernate(checkpoint) # Should not raise RuntimeError
    
    assert report1 == report2
    assert len(released_log) == 1 # Hook only called once
