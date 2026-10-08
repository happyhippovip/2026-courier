import pytest
from unittest.mock import MagicMock
from scripts.host_guardian import HostGuardian, HostState, AdmissionState, HostMetrics


def test_host_guardian_calm_streak_recovery(monkeypatch):
    import scripts.host_guardian as hg
    
    guardian = HostGuardian(max_heavy_local_jobs=1)
    
    # 1. Simulate high memory pressure -> STABILIZING / CLOSED
    fake_mem = MagicMock(percent=85.0)
    fake_swap = MagicMock(used=100, percent=10.0)
    fake_disk = MagicMock(free=10 * (1024 ** 3))
    
    monkeypatch.setattr(hg.psutil, "virtual_memory", lambda: fake_mem)
    monkeypatch.setattr(hg.psutil, "swap_memory", lambda: fake_swap)
    monkeypatch.setattr(hg.psutil, "disk_usage", lambda p: fake_disk)
    
    state = guardian.evaluate_admission()
    assert state == AdmissionState.CLOSED
    assert guardian.state == HostState.STABILIZING

    # 2. Return to calm conditions (percent=40.0)
    fake_mem.percent = 40.0
    # Step 1: moves to RECOVERING
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.state == HostState.RECOVERING
    assert guardian._calm_streak == 1

    # Step 2: stays RECOVERING
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.state == HostState.RECOVERING
    assert guardian._calm_streak == 2

    # Step 3: calm streak reaches 3 -> recovers to NORMAL / OPEN
    assert guardian.evaluate_admission() == AdmissionState.OPEN
    assert guardian.state == HostState.NORMAL
    assert guardian._calm_streak >= 3


def test_host_guardian_metrics_generation():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    metrics = guardian.get_metrics()
    assert isinstance(metrics, HostMetrics)
    assert metrics.desired_agent_slots == 64
    assert metrics.heavy_job_lease == 1
    assert metrics.cleanup_unknown is False


def test_host_guardian_release_heavy_lease_cleanup_proven():
    guardian = HostGuardian(max_heavy_local_jobs=1)
    guardian.admitted_heavy = 1

    # Release with cleanup_proven=False sets cleanup_unknown=True
    guardian.release_heavy_lease(cleanup_proven=False)
    assert guardian.admitted_heavy == 0
    assert guardian.cleanup_unknown is True

    # Reacquire and release with cleanup_proven=True resets cleanup_unknown=False
    guardian.admitted_heavy = 1
    guardian.release_heavy_lease(cleanup_proven=True)
    assert guardian.admitted_heavy == 0
    assert guardian.cleanup_unknown is False
