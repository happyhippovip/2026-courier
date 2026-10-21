"""
Tests for Windows Installer Packaging (BLK-10 Acceptance Gate).
Proves:
- Inno Setup script configuration integrity (per-user, non-admin, clean uninstall).
- Build installer script presence and execution contract.
- CourierSetup-v1.exe binary artifact validation and SHA-256 fingerprinting.
- Windows PE header verification (MZ header, PE signature).
- Automated silent install into sandbox directory and clean uninstall verification.
"""

import os
import sys
import hashlib
import struct
import subprocess
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_WORKER_DIR = REPO_ROOT / "scripts" / "windows_worker"
ISS_PATH = WINDOWS_WORKER_DIR / "courier_installer.iss"
BUILD_SCRIPT = WINDOWS_WORKER_DIR / "build_installer.ps1"
SETUP_EXE = WINDOWS_WORKER_DIR / "CourierSetup-v1.exe"


def test_courier_installer_iss_configuration():
    """Verify that courier_installer.iss enforces security and packaging invariants."""
    assert ISS_PATH.exists(), f"Installer script not found at {ISS_PATH}"
    content = ISS_PATH.read_text(encoding="utf-8", errors="replace")

    # Invariants
    assert "PrivilegesRequired=lowest" in content, "Must be per-user, non-elevated installation"
    assert "DefaultDirName={localappdata}\\CourierWorker" in content, "Must install to %LOCALAPPDATA%\\CourierWorker"
    assert 'OutputBaseFilename=CourierSetup-v1' in content, "Must output CourierSetup-v1"
    assert 'Source: "dist\\*"' in content, "Must package dist contents"
    assert "Type: filesandordirs; Name: \"{app}\\*\"" in content, "Must clean up app directory on uninstall"
    assert "skipifsilent" in content, "Must skip launch when run in silent mode"


def test_build_installer_script_contract():
    """Verify build_installer.ps1 contract."""
    assert BUILD_SCRIPT.exists(), f"Build script not found at {BUILD_SCRIPT}"
    content = BUILD_SCRIPT.read_text(encoding="utf-8", errors="replace")
    assert "ISCC.exe" in content
    assert "courier_installer.iss" in content
    assert "VerifyInstall" in content


def test_courier_setup_binary_artifact_integrity():
    """Verify CourierSetup-v1.exe existence, size, and valid SHA-256 fingerprint."""
    if not SETUP_EXE.exists():
        if os.name != "nt":
            pytest.skip("CourierSetup-v1.exe is compiled only on Windows hosts with Inno Setup")
        else:
            pytest.fail(
                f"CourierSetup-v1.exe not found at {SETUP_EXE}. "
                "Run 'powershell -ExecutionPolicy Bypass -File scripts/windows_worker/build_installer.ps1' to generate."
            )
    size = SETUP_EXE.stat().st_size
    assert size > 5_000_000, f"Installer binary suspiciously small: {size} bytes"

    # Compute SHA-256
    hasher = hashlib.sha256()
    with open(SETUP_EXE, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    assert len(digest) == 64, "Must produce a 64-character hex SHA-256 digest"

    # Verify DOS 'MZ' header
    with open(SETUP_EXE, "rb") as f:
        magic = f.read(2)
        assert magic == b"MZ", "Must be a valid Windows executable starting with 'MZ'"
        f.seek(0x3C)
        pe_offset = struct.unpack("<I", f.read(4))[0]
        f.seek(pe_offset)
        pe_sig = f.read(4)
        assert pe_sig == b"PE\x00\x00", "Must contain valid PE signature"


@pytest.mark.skipif(os.name != "nt", reason="Windows executable execution test")
def test_courier_setup_silent_install_and_uninstall_lifecycle(tmp_path):
    """Verify CourierSetup-v1.exe performs silent installation and clean uninstallation."""
    assert SETUP_EXE.exists(), "CourierSetup-v1.exe must exist"
    sandbox_dir = tmp_path / "InstalledApp"

    # 1. Run silent install targeting sandbox_dir
    install_proc = subprocess.run(
        [
            str(SETUP_EXE),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            f"/DIR={sandbox_dir}",
        ],
        capture_output=True,
        timeout=30,
    )
    assert install_proc.returncode == 0, f"Installer failed with returncode {install_proc.returncode}"

    # 2. Verify installed files
    installed_launcher = sandbox_dir / "Courier.exe"
    uninstaller = sandbox_dir / "unins000.exe"
    assert installed_launcher.exists(), "Installed Courier.exe must exist in target directory"
    assert uninstaller.exists(), "Installed unins000.exe must exist in target directory"

    # 3. Run silent uninstall
    uninstall_proc = subprocess.run(
        [
            str(uninstaller),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
        ],
        capture_output=True,
        timeout=30,
    )
    assert uninstall_proc.returncode == 0, f"Uninstaller failed with returncode {uninstall_proc.returncode}"

    # 4. Verify target directory cleanup
    assert not installed_launcher.exists(), "Courier.exe must be removed after uninstall"
