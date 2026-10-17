import pytest
from scripts.host_guardian import HostGuardian, HostState, AdmissionState

class MockResource:
    def __init__(self, alive=True, idle=True, safe=False, raises=False):
        self._alive = alive
        self._idle = idle
        self._safe = safe
        self._raises = raises
        self.terminated = False
        self.unknown = False
        
    def is_alive(self): return self._alive
    def is_idle(self): return self._idle
    def safe_to_retire(self): return self._safe
    def terminate(self):
        if self._raises:
            raise Exception("broken terminate")
        self.terminated = True

def test_cleanup_unknown_recovery():
    hg = HostGuardian()
    hg.release_heavy_lease(cleanup_proven=False)
    assert hg.cleanup_unknown is True
    
    # Should not recover instantly
    hg.release_heavy_lease(cleanup_proven=True)
    assert hg.cleanup_unknown is False

def test_broken_resource_does_not_abort_stabilize():
    hg = HostGuardian()
    hg.state = HostState.STABILIZING
    
    # Broken resource and healthy resource
    bad_res = MockResource(alive=False, raises=True)
    good_res = MockResource(alive=False, raises=False)
    
    hg.stabilize([bad_res, good_res])
    
    assert bad_res.terminated is False
    assert hg.cleanup_unknown is True  # Recorded UNKNOWN
    
    assert good_res.terminated is True # Handled safely

def test_still_running_process_is_not_a_proven_cleanup():
    """terminate() returning is not proof. A live process stays cleanup-unknown."""
    import subprocess
    import sys

    import psutil

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        class Resource:
            def is_alive(self):
                return child.poll() is None

            def safe_to_retire(self):
                return True

            def terminate(self):
                return None

        hg = HostGuardian()
        hg.state = HostState.STABILIZING
        hg.stabilize([Resource()])
        assert hg.cleanup_unknown is True
        assert psutil.Process(child.pid).is_running()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


def test_idle_bit_alone_cannot_kill():
    hg = HostGuardian()
    hg.state = HostState.STABILIZING
    
    # Idle but not safe
    res1 = MockResource(alive=True, idle=True, safe=False)
    # Safe to retire
    res2 = MockResource(alive=True, idle=False, safe=True)
    
    hg.stabilize([res1, res2])
    
    assert res1.terminated is False
    assert res2.terminated is True

def test_hysteresis_calm_streak(monkeypatch):
    hg = HostGuardian()
    
    # Mock evaluate pressure to always be clean
    hg.evaluate_admission = hg.__class__.evaluate_admission.__get__(hg, hg.__class__)
    
    # Fake pressure to get to STABILIZING
    hg.state = HostState.STABILIZING
    hg._calm_streak = 0
    hg.cleanup_unknown = False
    
    class MockMem: percent = 10.0
    class MockSwap: used = 0
    class MockDisk: free = 100 * (1024**3)
    
    import psutil
    monkeypatch.setattr(psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(psutil, "disk_usage", lambda path: MockDisk())
    
    # Clears once -> RECOVERING
    hg.evaluate_admission()
    assert hg.state == HostState.RECOVERING
    
    # Not NORMAL yet!
    hg.evaluate_admission()
    assert hg.state == HostState.RECOVERING
    
    # After N times -> NORMAL
    hg.evaluate_admission()
    assert hg.state == HostState.NORMAL

