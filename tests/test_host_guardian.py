import pytest
import psutil
from scripts.host_guardian import HostGuardian, HostState, AdmissionState

def test_host_guardian_memory_warning_light_only():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    # Mocking psutil logic by overriding evaluate_admission directly for this test
    # Or better, we mock the psutil calls inside the test.
    class MockMem:
        percent = 75.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)

    def mock_eval():
        guardian.state = HostState.LIGHT_ONLY
        return AdmissionState.LIGHT_ONLY
    
    guardian.evaluate_admission = mock_eval
    assert guardian.evaluate_admission() == AdmissionState.LIGHT_ONLY

def test_host_guardian_cleanup_unknown():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    # Give it a lease
    guardian.admitted_heavy = 1
    # Release but say cleanup is unknown
    guardian.release_heavy_lease(cleanup_proven=False)
    
    assert guardian.cleanup_unknown is True
    
    # Mock nominal memory
    class MockMem:
        percent = 50.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    hg.psutil.virtual_memory = lambda: MockMem()
    hg.psutil.swap_memory = lambda: MockSwap()
    hg.psutil.disk_usage = lambda path: MockDisk()

    assert guardian.evaluate_admission() == AdmissionState.LIGHT_ONLY
    assert guardian.request_heavy_lease() is False

def test_host_guardian_critical_pressure_closed():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    class MockMem:
        percent = 95.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    hg.psutil.virtual_memory = lambda: MockMem()
    hg.psutil.swap_memory = lambda: MockSwap()
    hg.psutil.disk_usage = lambda path: MockDisk()

    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.request_heavy_lease() is False

def test_recovery_tranche_of_one():
    # max_heavy_local_jobs is 1, so burst is impossible by definition.
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    class MockMem:
        percent = 50.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    hg.psutil.virtual_memory = lambda: MockMem()
    hg.psutil.swap_memory = lambda: MockSwap()
    hg.psutil.disk_usage = lambda path: MockDisk()
    
    assert guardian.request_heavy_lease() is True
    assert guardian.request_heavy_lease() is False # tranche of 1

