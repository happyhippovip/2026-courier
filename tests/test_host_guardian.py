import pytest
import psutil
from scripts.windows_worker.host_guardian import HostGuardian, HostState

def test_host_guardian_lease():
    guardian = HostGuardian(max_heavy_local_jobs=2)
    
    # We don't want to actually rely on system memory for a deterministic test
    # Let's mock evaluate_pressure
    original_eval = guardian.evaluate_pressure
    
    guardian.state = HostState.NOMINAL
    guardian.evaluate_pressure = lambda: guardian.state
    
    # First lease
    assert guardian.request_heavy_lease() is True
    assert guardian.admitted_heavy == 1
    
    # Second lease
    assert guardian.request_heavy_lease() is True
    assert guardian.admitted_heavy == 2
    
    # Third lease (refused)
    assert guardian.request_heavy_lease() is False
    assert guardian.admitted_heavy == 2
    
    # Release one
    guardian.release_heavy_lease()
    assert guardian.admitted_heavy == 1
    
    # Emergency state
    guardian.state = HostState.EMERGENCY
    assert guardian.request_heavy_lease() is False
    assert guardian.admitted_heavy == 1

