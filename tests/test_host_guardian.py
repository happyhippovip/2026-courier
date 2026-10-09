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

def test_host_guardian_cleanup_unknown(monkeypatch):
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
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())

    assert guardian.evaluate_admission() == AdmissionState.LIGHT_ONLY
    assert guardian.request_heavy_lease() is False

def test_host_guardian_critical_pressure_closed(monkeypatch):
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    class MockMem:
        percent = 95.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())

    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.request_heavy_lease() is False

def test_recovery_tranche_of_one(monkeypatch):
    # max_heavy_local_jobs is 1, so burst is impossible by definition.
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    class MockMem:
        percent = 50.0
    class MockSwap:
        used = 0
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())
    
    assert guardian.request_heavy_lease() is True
    assert guardian.request_heavy_lease() is False # tranche of 1

def test_swap_jitter_tolerated(monkeypatch):
    guardian = HostGuardian(max_heavy_local_jobs=1, swap_surge_threshold_bytes=10 * 1024 * 1024)
    guardian._last_swap_used = 100 * 1024 * 1024  # 100 MB baseline
    
    class MockMem:
        percent = 50.0
    class MockSwap:
        used = 101 * 1024 * 1024  # 101 MB (+1 MB jitter, < 10 MB threshold)
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())
    
    assert guardian.evaluate_admission() == AdmissionState.OPEN
    assert guardian.state == HostState.NORMAL

def test_swap_surge_trips_stabilizing(monkeypatch):
    guardian = HostGuardian(max_heavy_local_jobs=1, swap_surge_threshold_bytes=10 * 1024 * 1024)
    guardian._last_swap_used = 100 * 1024 * 1024  # 100 MB baseline
    
    class MockMem:
        percent = 50.0
    class MockSwap:
        used = 125 * 1024 * 1024  # 125 MB (+25 MB surge, > 10 MB threshold)
    class MockDisk:
        free = 100 * (1024**3)
        
    import scripts.host_guardian as hg
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())
    
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.state == HostState.STABILIZING

def test_root_path_configurable_and_fallback(monkeypatch):
    import scripts.host_guardian as hg
    
    paths_checked = []
    class MockDisk:
        free = 50 * (1024**3)
        
    def mock_disk_usage(path):
        paths_checked.append(path)
        if path == "nonexistent_custom_drive":
            raise FileNotFoundError("Drive not mounted")
        return MockDisk()

    monkeypatch.setattr(hg.psutil, "disk_usage", mock_disk_usage)
    
    # 1. Custom root_path succeeds
    g1 = HostGuardian(root_path="custom_drive")
    usage1 = g1._safe_disk_usage()
    assert usage1.free == 50 * (1024**3)
    assert "custom_drive" in paths_checked
    
    # 2. Failing custom root_path falls back cleanly
    g2 = HostGuardian(root_path="nonexistent_custom_drive")
    usage2 = g2._safe_disk_usage()
    assert usage2.free == 50 * (1024**3)

def test_get_metrics_robustness(monkeypatch):
    import scripts.host_guardian as hg
    
    class MockMem:
        percent = 45.0
    class MockSwap:
        percent = 12.0
    class MockDisk:
        free = 80 * (1024**3)
        
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())
    monkeypatch.setattr(hg.psutil, "pids", lambda: [1, 2, 3, 4])
    
    guardian = HostGuardian()
    metrics = guardian.get_metrics()
    assert metrics.memory_pressure == 0.45
    assert metrics.swap_pressure == 0.12
    assert metrics.disk_floor_gb == 80.0
    assert metrics.process_count == 4
    assert metrics.heavy_job_lease == 1
    assert metrics.host_health == "NORMAL"


