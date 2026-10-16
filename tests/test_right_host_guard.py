"""Unit tests for scripts/right_host_guard.py (Right-Host Guard, FRZ-01)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.right_host_guard import (
    HostIdentity,
    WrongHostError,
    assert_right_host,
    get_current_host_identity,
    get_device_id,
    is_cloud_vm,
    verify_right_host,
)


def test_current_host_identity_structure(tmp_path):
    ident = get_current_host_identity(tmp_path)
    assert isinstance(ident, HostIdentity)
    assert ident.hostname
    assert ident.os_platform in ("win32", "darwin", "linux")
    assert ident.device_id.startswith("DEV-") or len(ident.device_id) > 8
    assert isinstance(ident.is_cloud_vm, bool)
    assert ident.user


def test_verify_right_host_success(tmp_path):
    ident = get_current_host_identity(tmp_path)
    ok, msg = verify_right_host(
        expected_host=ident.hostname,
        expected_os=ident.os_platform,
        expected_device_id=ident.device_id,
        app_data_dir=tmp_path,
    )
    assert ok is True
    assert "verified" in msg.lower()


def test_verify_right_host_refusal_os_mismatch(tmp_path):
    wrong_os = "win32" if sys.platform != "win32" else "linux"
    ok, msg = verify_right_host(expected_os=wrong_os, app_data_dir=tmp_path)
    assert ok is False
    assert "os mismatch" in msg.lower()


def test_verify_right_host_refusal_hostname_mismatch(tmp_path):
    ok, msg = verify_right_host(expected_host="nonexistent-target-machine", app_data_dir=tmp_path)
    assert ok is False
    assert "hostname mismatch" in msg.lower()


def test_assert_right_host_raises_wrong_host_error(tmp_path):
    with pytest.raises(WrongHostError) as exc_info:
        assert_right_host(expected_host="alien-machine", app_data_dir=tmp_path)
    assert "alien-machine" in str(exc_info.value)
    assert "RIGHT-HOST GUARD REFUSAL" in str(exc_info.value)


def test_device_id_persistence(tmp_path):
    dev1 = get_device_id(tmp_path)
    assert dev1
    device_file = tmp_path / "device_id"
    assert device_file.is_file()

    dev2 = get_device_id(tmp_path)
    assert dev1 == dev2


def test_cloud_vm_rejection(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert is_cloud_vm() is True

    ok, msg = verify_right_host(disallow_cloud=True, app_data_dir=tmp_path)
    assert ok is False
    assert "cloud vm detected" in msg.lower()


def test_cli_execution():
    script = Path(__file__).resolve().parent.parent / "scripts" / "right_host_guard.py"

    # Test --json
    proc = subprocess.run([sys.executable, str(script), "--json"], capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["os_platform"] == sys.platform

    # Matching OS exits 0
    proc_ok = subprocess.run([sys.executable, str(script), "--require-os", sys.platform], capture_output=True, text=True, check=False)
    assert proc_ok.returncode == 0

    # Mismatched OS exits 1
    wrong_os = "win32" if sys.platform != "win32" else "linux"
    proc_bad = subprocess.run([sys.executable, str(script), "--require-os", wrong_os], capture_output=True, text=True, check=False)
    assert proc_bad.returncode == 1
    assert "OS mismatch" in proc_bad.stdout
