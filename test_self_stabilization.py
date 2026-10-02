import pytest
from scripts.host_guardian import HostGuardian, HostState, AdmissionState

class MockResource:
    def __init__(self, alive, idle, safe=False):
        self._alive = alive
        self._idle = idle
        self._safe = safe
        self.terminated = False
    def is_alive(self): return self._alive
    def is_idle(self): return self._idle
    def safe_to_retire(self): return self._safe
    def terminate(self): self.terminated = True

def mock_psutil(mem_pct):
    import scripts.host_guardian as hg
    class MockMem: percent = mem_pct
    class MockSwap: used = 0; percent = 0
    class MockDisk: free = 100 * (1024**3)
    hg.psutil.virtual_memory = lambda: MockMem()
    hg.psutil.swap_memory = lambda: MockSwap()
    hg.psutil.disk_usage = lambda path: MockDisk()

def test_pressure_to_stabilizing():
    guardian = HostGuardian()
    mock_psutil(85.0) # > 0.80 -> STABILIZING
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.state == HostState.STABILIZING
    
    # New heavy work blocked during stabilization
    assert guardian.request_heavy_lease() is False

def test_quiet_healthy_work_preserved():
    guardian = HostGuardian()
    guardian.state = HostState.STABILIZING
    
    quiet_healthy = MockResource(alive=True, idle=False, safe=False)
    idle_dead = MockResource(alive=False, idle=True, safe=False)
    idle_alive = MockResource(alive=True, idle=True, safe=True)
    
    mock_psutil(75.0) # Safe envelope restored (LIGHT_ONLY)
    
    guardian.stabilize([quiet_healthy, idle_dead, idle_alive])
    
    assert quiet_healthy.terminated is False # Preserved!
    assert idle_dead.terminated is True
    assert idle_alive.terminated is True

def test_successful_cleanup_light_only():
    guardian = HostGuardian()
    guardian.state = HostState.STABILIZING
    
    mock_psutil(75.0) # Safe envelope restored (LIGHT_ONLY)
    state = guardian.stabilize([])
    
    assert state == HostState.LIGHT_ONLY
    assert guardian.state == HostState.LIGHT_ONLY

def test_failed_recovery_restart_recommended():
    guardian = HostGuardian()
    guardian.state = HostState.STABILIZING
    
    mock_psutil(85.0) # Still pressured
    state = guardian.stabilize([])
    
    assert state == HostState.RESTART_RECOMMENDED
    assert guardian.state == HostState.RESTART_RECOMMENDED

def test_restart_recommendation_clears_after_recovery():
    guardian = HostGuardian()
    guardian.state = HostState.RESTART_RECOMMENDED
    
    # Let's say user manually frees memory
    mock_psutil(65.0) # NORMAL
    assert guardian.evaluate_admission() == AdmissionState.CLOSED # RECOVERING
    assert guardian.evaluate_admission() == AdmissionState.CLOSED # RECOVERING
    assert guardian.evaluate_admission() == AdmissionState.OPEN # NORMAL
    assert guardian.state == HostState.NORMAL
