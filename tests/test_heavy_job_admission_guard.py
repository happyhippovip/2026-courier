"""Test Heavy Job Admission Guard (Antigravity 024).

Verifies that Courier's HostGuardian correctly evaluates host capacity and
prevents starting heavy jobs when resources are insufficient.

Validates the 6 distinct canonical states:
1. HEALTHY (Admitted: True)
2. LOW_MEMORY (Admitted: False)
3. LOW_DISK (Admitted: False)
4. RESOURCE_PAUSED (Admitted: False)
5. HEAVY_JOB_ALREADY_ACTIVE (Admitted: False)
6. UNKNOWN_CAPACITY (Admitted: False - fails closed)

Only Test A (HEALTHY) admits a new heavy job. Tests B, C, D, E all fail closed.
"""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from scripts.host_guardian import (
    HostGuardian,
    CapacityState,
    HeavyAdmissionDecision,
    AdmissionState,
    HostState,
)


def test_state_a_healthy_no_heavy_job():
    """Test A: Resources healthy, no heavy job active -> Admitted (HEALTHY)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    telemetry = {
        "memory_percent": 45.0,
        "disk_free_gb": 50.0,
        "swap_used": 0,
    }

    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry)
    assert decision.admitted is True
    assert decision.state == CapacityState.HEALTHY
    assert decision.state == "HEALTHY"

    # Request lease successfully
    leased = guardian.request_heavy_lease(telemetry=telemetry)
    assert leased is True
    assert guardian.admitted_heavy == 1


def test_state_b_healthy_but_heavy_job_already_active():
    """Test B: Resources healthy, but heavy job already active -> Rejected (HEAVY_JOB_ALREADY_ACTIVE)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    telemetry = {
        "memory_percent": 45.0,
        "disk_free_gb": 50.0,
        "swap_used": 0,
    }

    # First job admitted
    assert guardian.request_heavy_lease(telemetry=telemetry) is True
    assert guardian.admitted_heavy == 1

    # Second job evaluated: must be rejected with HEAVY_JOB_ALREADY_ACTIVE
    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry)
    assert decision.admitted is False
    assert decision.state == CapacityState.HEAVY_JOB_ALREADY_ACTIVE
    assert decision.state == "HEAVY_JOB_ALREADY_ACTIVE"
    assert "active heavy jobs 1 >= limit 1" in decision.reason

    # Request lease must fail
    assert guardian.request_heavy_lease(telemetry=telemetry) is False
    assert guardian.admitted_heavy == 1  # Still capped at 1


def test_state_c_low_memory():
    """Test C1: Memory utilization exceeds threshold (> 80%) -> Rejected (LOW_MEMORY)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    telemetry = {
        "memory_percent": 88.5,
        "disk_free_gb": 50.0,
        "swap_used": 0,
    }

    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry)
    assert decision.admitted is False
    assert decision.state == CapacityState.LOW_MEMORY
    assert decision.state == "LOW_MEMORY"
    assert "exceeds 80.0% threshold" in decision.reason

    assert guardian.request_heavy_lease(telemetry=telemetry) is False
    assert guardian.admitted_heavy == 0


def test_state_c_low_disk():
    """Test C2: Disk free space below safety floor (< 2.0 GB) -> Rejected (LOW_DISK)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    telemetry = {
        "memory_percent": 30.0,
        "disk_free_gb": 1.25,
        "swap_used": 0,
    }

    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry)
    assert decision.admitted is False
    assert decision.state == CapacityState.LOW_DISK
    assert decision.state == "LOW_DISK"
    assert "below 2.0 GB safety floor" in decision.reason

    assert guardian.request_heavy_lease(telemetry=telemetry) is False
    assert guardian.admitted_heavy == 0


def test_state_d_resource_pause_file_active(tmp_path):
    """Test D1: RESOURCE_PAUSE file exists -> Rejected (RESOURCE_PAUSED)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    pause_file = tmp_path / "RESOURCE_PAUSE"
    pause_file.write_text("PAUSED: host thermal maintenance\n", encoding="utf-8")

    telemetry = {
        "memory_percent": 30.0,
        "disk_free_gb": 50.0,
    }

    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry, pause_file=str(pause_file))
    assert decision.admitted is False
    assert decision.state == CapacityState.RESOURCE_PAUSED
    assert decision.state == "RESOURCE_PAUSED"

    assert guardian.request_heavy_lease(telemetry=telemetry, pause_file=str(pause_file)) is False
    assert guardian.admitted_heavy == 0


def test_state_d_resource_pause_env_active(monkeypatch):
    """Test D2: COURIER_ADMISSION_STATE set to RESOURCE_PAUSE -> Rejected (RESOURCE_PAUSED)."""
    monkeypatch.setenv("COURIER_ADMISSION_STATE", "RESOURCE_PAUSE")
    guardian = HostGuardian(max_heavy_local_jobs=1)

    telemetry = {
        "memory_percent": 30.0,
        "disk_free_gb": 50.0,
    }

    decision = guardian.evaluate_heavy_job_admission(telemetry=telemetry)
    assert decision.admitted is False
    assert decision.state == CapacityState.RESOURCE_PAUSED
    assert decision.state == "RESOURCE_PAUSED"


def test_state_e_unknown_capacity_fails_closed():
    """Test E: Telemetry is corrupted, None, or unmeasurable -> Rejected (UNKNOWN_CAPACITY)."""
    guardian = HostGuardian(max_heavy_local_jobs=1)

    # Sub-case 1: Explicitly unknown
    decision_unknown = guardian.evaluate_heavy_job_admission(telemetry={"unknown": True})
    assert decision_unknown.admitted is False
    assert decision_unknown.state == CapacityState.UNKNOWN_CAPACITY
    assert decision_unknown.state == "UNKNOWN_CAPACITY"

    # Sub-case 2: Corrupted non-numeric values
    decision_corrupt = guardian.evaluate_heavy_job_admission(telemetry={"memory_percent": "N/A", "disk_free_gb": None})
    assert decision_corrupt.admitted is False
    assert decision_corrupt.state == CapacityState.UNKNOWN_CAPACITY

    # Sub-case 3: Missing disk metric
    decision_missing = guardian.evaluate_heavy_job_admission(telemetry={"memory_percent": 40.0})
    assert decision_missing.admitted is False
    assert decision_missing.state == CapacityState.UNKNOWN_CAPACITY

    # Sub-case 4: Exception during probe fails closed
    class ExplodingObject:
        @property
        def memory_percent(self):
            raise RuntimeError("Hardware sensor failure")

    decision_ex = guardian.evaluate_heavy_job_admission(telemetry=ExplodingObject())
    assert decision_ex.admitted is False
    assert decision_ex.state == CapacityState.UNKNOWN_CAPACITY

    assert guardian.admitted_heavy == 0


def test_recovery_to_healthy():
    """Recovery Test: Transitions from pressured or heavy-active back to HEALTHY once cleared."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    telemetry_healthy = {
        "memory_percent": 40.0,
        "disk_free_gb": 40.0,
    }

    # Step 1: Admit heavy job
    assert guardian.request_heavy_lease(telemetry=telemetry_healthy) is True
    assert guardian.admitted_heavy == 1

    # Step 2: Second job rejected because heavy is active
    d_active = guardian.evaluate_heavy_job_admission(telemetry=telemetry_healthy)
    assert d_active.admitted is False
    assert d_active.state == CapacityState.HEAVY_JOB_ALREADY_ACTIVE

    # Step 3: Heavy job completes and releases lease with proven cleanup
    guardian.release_heavy_lease(cleanup_proven=True)
    assert guardian.admitted_heavy == 0
    assert guardian.cleanup_unknown is False

    # Step 4: System recovers to HEALTHY and admits next heavy job
    d_recovered = guardian.evaluate_heavy_job_admission(telemetry=telemetry_healthy)
    assert d_recovered.admitted is True
    assert d_recovered.state == CapacityState.HEALTHY

    assert guardian.request_heavy_lease(telemetry=telemetry_healthy) is True
    assert guardian.admitted_heavy == 1


def test_only_state_a_admits_new_heavy_job():
    """Invariant: ONLY State A admits a new heavy job. States B, C, D, E strictly reject."""
    guardian = HostGuardian(max_heavy_local_jobs=1)

    cases = [
        ("Test A (Healthy, 0 active)", {"memory_percent": 50.0, "disk_free_gb": 30.0}, 0, False, True, CapacityState.HEALTHY),
        ("Test B (Heavy active)", {"memory_percent": 50.0, "disk_free_gb": 30.0}, 1, False, False, CapacityState.HEAVY_JOB_ALREADY_ACTIVE),
        ("Test C1 (Low RAM)", {"memory_percent": 90.0, "disk_free_gb": 30.0}, 0, False, False, CapacityState.LOW_MEMORY),
        ("Test C2 (Low Disk)", {"memory_percent": 50.0, "disk_free_gb": 0.8}, 0, False, False, CapacityState.LOW_DISK),
        ("Test D (Resource Paused)", {"memory_percent": 50.0, "disk_free_gb": 30.0}, 0, True, False, CapacityState.RESOURCE_PAUSED),
        ("Test E (Unknown Capacity)", {"unknown": True}, 0, False, False, CapacityState.UNKNOWN_CAPACITY),
    ]

    for label, tel, active_heavy, paused, expected_admit, expected_state in cases:
        guardian.admitted_heavy = active_heavy
        pause_flag = "RESOURCE_PAUSE" if paused else None
        if paused:
            os.environ["COURIER_ADMISSION_STATE"] = "RESOURCE_PAUSE"
        else:
            os.environ.pop("COURIER_ADMISSION_STATE", None)

        dec = guardian.evaluate_heavy_job_admission(telemetry=tel)
        assert dec.admitted is expected_admit, f"{label} expected admitted={expected_admit}, got {dec.admitted}"
        assert dec.state == expected_state, f"{label} expected state={expected_state}, got {dec.state}"

    os.environ.pop("COURIER_ADMISSION_STATE", None)
