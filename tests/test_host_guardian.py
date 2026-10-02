import pytest
import psutil
from scripts.host_guardian import HostGuardian, HostState

def test_host_guardian_lease():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    original_eval = guardian.evaluate_pressure
    
    guardian.state = HostState.NOMINAL
    guardian.evaluate_pressure = lambda: guardian.state
    
    # First lease
    assert guardian.request_heavy_lease() is True
    assert guardian.admitted_heavy == 1
    
    # Second lease
    assert guardian.request_heavy_lease() is False
    assert guardian.admitted_heavy == 1
    
    # Release one
    guardian.release_heavy_lease()
    assert guardian.admitted_heavy == 0
    
    # Emergency state
    guardian.state = HostState.EMERGENCY
    assert guardian.request_heavy_lease() is False
    assert guardian.admitted_heavy == 0
