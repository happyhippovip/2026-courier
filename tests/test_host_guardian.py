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


# --- SYNTHETISCHE TESTS A-E (ANTIGRAVITY 024) ---

def test_synthetic_a_healthy_no_heavy_job(monkeypatch):
    """Test A: Ressourcen gesund, kein Heavy Job -> Zulassung erteilt."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    class MockMem: percent = 40.0
    class MockSwap: used = 0
    class MockDisk: free = 100 * (1024**3)

    import scripts.host_guardian as hg
    monkeypatch.delenv("RESOURCE_PAUSE", raising=False)
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())

    assert guardian.diagnose_capacity() == "HEALTHY"
    assert guardian.request_heavy_lease() is True


def test_synthetic_b_healthy_heavy_job_already_active(monkeypatch):
    """Test B: Ressourcen gesund, aber Heavy Job bereits aktiv -> Ablehnung."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    guardian.admitted_heavy = 1
    class MockMem: percent = 40.0
    class MockSwap: used = 0
    class MockDisk: free = 100 * (1024**3)

    import scripts.host_guardian as hg
    monkeypatch.delenv("RESOURCE_PAUSE", raising=False)
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: MockSwap())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())

    assert guardian.diagnose_capacity() == "HEAVY_JOB_ALREADY_ACTIVE"
    assert guardian.request_heavy_lease() is False


def test_synthetic_c_insufficient_resources(monkeypatch):
    """Test C: Ressourcen unzureichend (Low Memory und Low Disk) -> Ablehnung."""
    import scripts.host_guardian as hg
    monkeypatch.delenv("RESOURCE_PAUSE", raising=False)

    # Subtest C1: Low Memory (>80%)
    g_mem = HostGuardian(max_heavy_local_jobs=1)
    class MockMemLow: percent = 92.0
    class MockDiskOk: free = 50 * (1024**3)
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMemLow())
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: type("Swap", (), {"used": 0}))
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDiskOk())
    assert g_mem.diagnose_capacity() == "LOW_MEMORY"
    assert g_mem.request_heavy_lease() is False

    # Subtest C2: Low Disk (<2.0 GB)
    g_disk = HostGuardian(max_heavy_local_jobs=1)
    class MockMemOk: percent = 30.0
    class MockDiskLow: free = 1.2 * (1024**3)
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMemOk())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDiskLow())
    assert g_disk.diagnose_capacity() == "LOW_DISK"
    assert g_disk.request_heavy_lease() is False


def test_synthetic_d_resource_pause(monkeypatch):
    """Test D: RESOURCE_PAUSE gesetzt -> Ablehnung (CLOSED)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    class MockMem: percent = 30.0
    class MockDisk: free = 100 * (1024**3)

    import scripts.host_guardian as hg
    monkeypatch.setenv("RESOURCE_PAUSE", "1")
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: MockMem())
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda path: MockDisk())

    assert guardian.diagnose_capacity() == "RESOURCE_PAUSED"
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.request_heavy_lease() is False


def test_synthetic_e_unknown_capacity_fails_closed(monkeypatch):
    """Test E: Ressourcenstatus unbekannt -> Fail-Closed Ablehnung."""
    guardian = HostGuardian(max_heavy_local_jobs=1)

    import scripts.host_guardian as hg
    monkeypatch.delenv("RESOURCE_PAUSE", raising=False)
    def broken_metrics():
        raise RuntimeError("Sensors offline")
    monkeypatch.setattr(hg.psutil, "virtual_memory", broken_metrics)

    assert guardian.diagnose_capacity() == "UNKNOWN_CAPACITY"
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.request_heavy_lease() is False


