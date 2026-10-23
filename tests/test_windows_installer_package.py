"""Static contract for the per-user Windows installer.

Linux can prove the script, the payload names and the release matrix.
It cannot compile Inno Setup or install Courier. Those rows stay UNPROVEN.
"""

import hashlib
import os
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_WORKER_DIR = REPO_ROOT / "scripts" / "windows_worker"
ISS_PATH = WINDOWS_WORKER_DIR / "courier_installer.iss"
BUILD_SCRIPT = WINDOWS_WORKER_DIR / "build_installer.ps1"
INSTALL_SCRIPT = WINDOWS_WORKER_DIR / "install.ps1"
SETUP_EXE = WINDOWS_WORKER_DIR / "CourierSetup-v1.exe"
MATRIX_PATH = REPO_ROOT / "docs" / "v1" / "WINDOWS_INSTALLER_RC_MATRIX.md"
DIST_DIR = WINDOWS_WORKER_DIR / "dist"

SECRET_NAME_MARKERS = ("token", "credential")
SECRET_SUFFIXES = (".env", ".pem", ".key")


def _read(path):
    return path.read_text(encoding="utf-8")


def _section(content, name):
    marker = f"[{name}]"
    start = content.index(marker) + len(marker)
    rest = content[start:]
    next_header = rest.find("\n[")
    if next_header == -1:
        return rest
    return rest[:next_header]


def _sha256(path):
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


def test_courier_installer_matches_per_user_contract():
    content = _read(ISS_PATH)
    assert "PrivilegesRequired=lowest" in content
    assert r"DefaultDirName={localappdata}\Programs\Courier" in content
    assert "UsePreviousAppDir=yes" in content
    assert "SetupLogging=yes" in content
    assert "OutputBaseFilename=CourierSetup-v1" in content
    assert 'Source: "dist\\*"' in content
    assert "skipifsilent" in content
    assert r"CloseApplicationsFilter=Courier.exe,python.exe,pythonw.exe" in content
    excludes = content.split("Excludes:", 1)[1].split("\n", 1)[0]
    for pattern in ("config.json", "*.env", "*.pem", "*.key", "*token*", "*credential*", "id_rsa*"):
        assert pattern in excludes
    for forbidden in ("CourierWorker", "ProgramFiles", "192.168", "COURIER_API_KEY", "Read-Host"):
        assert forbidden not in content
    icons = _section(content, "Icons")
    assert r'Filename: "{app}\{#MyAppExeName}"' in icons
    assert 'WorkingDir: "{app}"' in icons
    assert "startupicon" in content
    assert "Flags: unchecked" in content.split("startupicon", 1)[1].split("\n", 1)[0]
    uninstall = _section(content, "UninstallDelete")
    assert r'Name: "{app}\*"' in uninstall
    assert "{localappdata}" not in uninstall


def test_installer_directory_matches_install_ps1():
    install = _read(INSTALL_SCRIPT)
    assert 'Join-Path $env:LOCALAPPDATA "Programs\\Courier"' in install
    assert 'Join-Path $env:LOCALAPPDATA "Courier"' in install


def test_build_installer_script_contract():
    content = _read(BUILD_SCRIPT)
    assert "ISCC.exe" in content
    assert "courier_installer.iss" in content
    assert "[switch]$VerifyInstall = $false" in content
    assert 'Join-Path $env:LOCALAPPDATA "Programs\\Courier"' in content
    assert "Inno Setup 6" in content
    assert "Get-Command iscc.exe" in content
    assert "data directory was removed" in content
    assert "CourierWorker" not in content
    assert "Antigravity" not in content
    assert "SHA256" in content


def test_dist_filenames_are_not_secrets():
    assert DIST_DIR.is_dir()
    offenders = []
    for path in DIST_DIR.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name == "config.json" or name.startswith("id_rsa"):
            offenders.append(str(path))
            continue
        if name.endswith(SECRET_SUFFIXES) or any(marker in name for marker in SECRET_NAME_MARKERS):
            offenders.append(str(path))
    assert offenders == []


def _bare_marker(data, marker):
    start = 0
    while True:
        found = data.find(marker, start)
        if found < 0:
            return False
        previous = data[found - 1:found]
        if not previous.isalnum():
            return True
        start = found + len(marker)


def test_dist_bytes_have_no_credential_markers():
    markers = (b"BEGIN PRIVATE KEY", b"BEGIN RSA PRIVATE KEY", b"AKIA", b"ghp_", b"github_pat_", b"xoxb-", b"xoxp-", b"sk-")
    offenders = []
    for path in DIST_DIR.rglob("*"):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        data = path.read_bytes()
        for marker in markers:
            if _bare_marker(data, marker):
                offenders.append(f"{path}:{marker.decode()}")
                break
    assert offenders == []


def test_stale_dist_files_are_overwritten_by_current_sources():
    content = _read(ISS_PATH)
    files = _section(content, "Files")
    dist_at = files.index('Source: "dist\\*"')
    for name in ("install.ps1", "Courier.exe"):
        source = WINDOWS_WORKER_DIR / name
        packaged = DIST_DIR / name
        assert source.read_bytes() != packaged.read_bytes()
        entry = f'Source: "{name}"'
        assert entry in files
        assert files.index(entry) > dist_at
    assert 'Source: "start.bat"' not in files


def test_release_matrix_records_source_hashes_and_blocks():
    text = _read(MATRIX_PATH)
    assert _sha256(ISS_PATH) in text
    assert _sha256(BUILD_SCRIPT) in text
    assert "UNPROVEN" in text
    assert "BLOCKED" in text
    assert "HTTP 404" in text
    for line in text.splitlines():
        if any(label in line for label in ("Clean-Machine", "Stiller Install", "Setup.exe", "Rollback", "ISCC")):
            assert "PASS" not in line


def test_setup_exe_is_gitignored():
    gitignore = _read(REPO_ROOT / ".gitignore")
    assert "scripts/windows_worker/CourierSetup-v1.exe" in gitignore


def test_courier_setup_binary_artifact_integrity():
    """Absence of the EXE is UNPROVEN on every host. A skip is not a pass."""
    if not SETUP_EXE.exists():
        pytest.skip("UNPROVEN: CourierSetup-v1.exe is not in this tree")
    size = SETUP_EXE.stat().st_size
    assert size > 5_000_000, f"Installer binary suspiciously small: {size} bytes"
    assert len(_sha256(SETUP_EXE)) == 64
    with open(SETUP_EXE, "rb") as handle:
        assert handle.read(2) == b"MZ"
        handle.seek(0x3C)
        pe_offset = struct.unpack("<I", handle.read(4))[0]
        handle.seek(pe_offset)
        assert handle.read(4) == b"PE\x00\x00"


def test_courier_setup_silent_install_and_uninstall_lifecycle():
    if os.environ.get("COURIER_INSTALLER_VERIFY") != "1":
        pytest.skip("UNPROVEN: silent install is not authorized in this session")
    pytest.fail("COURIER_INSTALLER_VERIFY=1 requires a disposable Windows profile; this session does not install")
