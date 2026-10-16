"""Deterministic and isolated tests for Windows Hostname Verification (FRZ-01 / SEED 151).

Tests both synthetic positive/negative edge cases and live Windows host verification.
"""
import os
import platform
import socket
import subprocess
import sys
import pytest

from scripts.host_guardian import (
    HostGuardian,
    HostState,
    AdmissionState,
    verify_windows_hostname,
    AUTHORIZED_WINDOWS_HOSTNAMES,
)


def test_positive_real_windows_hostname():
    """Verify that the actual execution host matches DESKTOP-JDPRUGR on Windows."""
    if platform.system() != "Windows":
        pytest.skip("Test must run on Windows host")
    
    valid, details = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is True
    assert details.upper() == "DESKTOP-JDPRUGR"


def test_positive_case_insensitive_matching(monkeypatch):
    """Windows hostnames must match case-insensitively."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(socket, "gethostname", lambda: "desktop-jdprugr")
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-JDPRUGR")

    valid, details = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is True
    assert details == "desktop-jdprugr"


def test_negative_foreign_hostname_rejected(monkeypatch):
    """Foreign, cloud, or unauthorized hostnames must fail closed."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(socket, "gethostname", lambda: "ROGUE-CLOUD-WORKER")
    monkeypatch.setenv("COMPUTERNAME", "ROGUE-CLOUD-WORKER")

    valid, reason = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is False
    assert "HOSTNAME_MISMATCH" in reason
    assert "rogue-cloud-worker" in reason.lower()


def test_negative_empty_hostname_rejected(monkeypatch):
    """Empty or whitespace hostname must fail closed."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(socket, "gethostname", lambda: "   ")
    monkeypatch.delenv("COMPUTERNAME", raising=False)

    valid, reason = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is False
    assert "HOSTNAME_EMPTY" in reason


def test_negative_inconsistent_env_computername_rejected(monkeypatch):
    """If COMPUTERNAME does not match socket.gethostname, fail closed (spoofing guard)."""
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(socket, "gethostname", lambda: "DESKTOP-JDPRUGR")
    monkeypatch.setenv("COMPUTERNAME", "ATTACKER-FORGED-PC")

    valid, reason = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is False
    assert "HOSTNAME_INCONSISTENT" in reason


def test_negative_non_windows_rejected_when_required(monkeypatch):
    """Mac/Linux hosts attempting Windows tasks must fail closed."""
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(socket, "gethostname", lambda: "DESKTOP-JDPRUGR")

    valid, reason = verify_windows_hostname(expected_hostname="DESKTOP-JDPRUGR", require_windows=True)
    assert valid is False
    assert "OS_MISMATCH" in reason


def test_host_guardian_integration_mismatch_locks_admission(monkeypatch):
    """HostGuardian.verify_host_identity fails closed and forces STABILIZING state on mismatch."""
    guardian = HostGuardian(max_heavy_local_jobs=1)
    assert guardian.state == HostState.NORMAL

    # Simulate mismatch
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(socket, "gethostname", lambda: "UNAUTHORIZED-MACHINE")
    monkeypatch.setenv("COMPUTERNAME", "UNAUTHORIZED-MACHINE")

    valid, reason = guardian.verify_host_identity(expected_hostname="DESKTOP-JDPRUGR")
    assert valid is False
    assert guardian.state == HostState.STABILIZING
    assert guardian.evaluate_admission() == AdmissionState.CLOSED
    assert guardian.request_heavy_lease() is False


def test_cli_verify_windows_hostname_subprocess():
    """Verify standalone script process execution and exit codes."""
    py = sys.executable
    script = os.path.join("scripts", "verify_windows_hostname.py")

    # 1. Successful execution
    proc_ok = subprocess.run([py, script], capture_output=True, text=True)
    assert proc_ok.returncode == 0
    assert "WINDOWS HOSTNAME VALID" in proc_ok.stdout

    # 2. Rejected execution with foreign expected host
    proc_fail = subprocess.run([py, script, "--expected-host", "FOREIGN-NODE-99"], capture_output=True, text=True)
    assert proc_fail.returncode == 1
    assert "WINDOWS HOSTNAME FAILED" in proc_fail.stdout
