import pytest
from courier_runtime.continuity import (
    ACTIVITY,
    SATURATION_SIGNALS,
    SNAPSHOT_EVERY_S,
    HEALTH_TICK_S,
    OPEN, CLAIMED, DONE, BLOCKED, FAILED_FINAL,
    WORKING, IDLE, WAKE_PENDING, WAITING_FOR_USER, RECOVERING, RETIRED,
    Workkey,
)

def test_continuity_constants():
    assert SNAPSHOT_EVERY_S == 900
    assert HEALTH_TICK_S == 45
    assert "interactive" in ACTIVITY
    assert "build" in ACTIVITY
    assert "long_quiet" in ACTIVITY
    
    # Grace times must be strictly positive and progress windows > grace
    for act, (grace, progress) in ACTIVITY.items():
        assert grace > 0
        assert progress > grace

def test_saturation_signals_tuple():
    assert "hard_threshold_failed" in SATURATION_SIGNALS
    assert "turn-submit backlog full" in SATURATION_SIGNALS
    assert "context window exceeded" in SATURATION_SIGNALS

def test_workkey_initial_state():
    wk = Workkey(key="W-TEST-01")
    assert wk.key == "W-TEST-01"
    assert wk.state == OPEN
    assert wk.owner == ""
