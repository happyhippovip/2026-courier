import pytest
from courier_core.recovery_state_machine import RecoveryStateMachine, RecoveryState, TransitionRequest

def test_initial_state():
    sm = RecoveryStateMachine()
    assert sm.state == RecoveryState.IDLE_READY

def test_terminal_host_failed_requires_hard_reset():
    sm = RecoveryStateMachine()
    sm.transition(TransitionRequest("CRASH", RecoveryState.TERMINAL_HOST_FAILED, "exit -1"))
    assert sm.state == RecoveryState.TERMINAL_HOST_FAILED
    
    # Try soft transition
    res = sm.transition(TransitionRequest("SOFT_RESET", RecoveryState.IDLE_READY, "restart"))
    assert not res
    assert sm.state == RecoveryState.TERMINAL_HOST_FAILED
    
    # Hard reset works
    res = sm.transition(TransitionRequest("HARD_RESET", RecoveryState.IDLE_READY, "system recovered"))
    assert res
    assert sm.state == RecoveryState.IDLE_READY

def test_surface_corrupted_transitions():
    sm = RecoveryStateMachine()
    sm.transition(TransitionRequest("PIXEL_FAIL", RecoveryState.SURFACE_CORRUPTED, "screen blank"))
    assert sm.state == RecoveryState.SURFACE_CORRUPTED
    
    # Invalid transition back to IDLE_READY without RECOVERING
    res = sm.transition(TransitionRequest("CONTINUE", RecoveryState.IDLE_READY, "resume"))
    assert not res
    assert sm.state == RecoveryState.SURFACE_CORRUPTED
    
    # Valid transition to RECOVERING
    res = sm.transition(TransitionRequest("START_REPAIR", RecoveryState.RECOVERING, "restarting ui"))
    assert res
    assert sm.state == RecoveryState.RECOVERING
