"""Validation suite for the Courier Symphony Inno Setup installer script.

Guarantees conformance with docs/V1_RULE_0.md:
- Per-user installation (PrivilegesRequired=lowest)
- Clean-machine execution without administrator elevation
- Desktop and start menu shortcut declarations
- Clean uninstall preserving user ledger/data
"""
import re
from pathlib import Path

import pytest

ISS_PATH = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "courier_installer.iss"


def test_inno_setup_script_exists():
    assert ISS_PATH.is_file(), f"Expected Inno Setup script at {ISS_PATH}"


def test_inno_setup_per_user_privileges():
    content = ISS_PATH.read_text(encoding="utf-8")
    match = re.search(r"PrivilegesRequired\s*=\s*(\w+)", content)
    assert match is not None, "PrivilegesRequired directive missing from Inno Setup script"
    assert match.group(1).lower() == "lowest", (
        f"Expected PrivilegesRequired=lowest for per-user clean-machine install, got {match.group(1)}"
    )


def test_inno_setup_target_directory_per_user():
    content = ISS_PATH.read_text(encoding="utf-8")
    match = re.search(r"DefaultDirName\s*=\s*(.+)", content)
    assert match is not None, "DefaultDirName directive missing"
    dest = match.group(1).strip()
    assert "{localappdata}" in dest or "{userappdata}" in dest, (
        f"DefaultDirName must target per-user appdata, found: {dest}"
    )


def test_inno_setup_executable_name():
    content = ISS_PATH.read_text(encoding="utf-8")
    assert '#define MyAppExeName "Courier.exe"' in content, "MyAppExeName must define Courier.exe"


def test_inno_setup_shortcuts_and_tasks():
    content = ISS_PATH.read_text(encoding="utf-8")
    assert "{userprograms}" in content, "Start Menu shortcut required"
    assert "{userdesktop}" in content, "Desktop shortcut required"
    assert "{userstartup}" in content, "Optional Windows startup shortcut required"


def test_inno_setup_preserves_user_data_on_uninstall():
    content = ISS_PATH.read_text(encoding="utf-8")
    assert "[UninstallDelete]" in content
    # Ensure it only cleans {app} and does not delete the persistent journal at %LOCALAPPDATA%\Courier
    assert "{localappdata}\\Courier\\*" not in content, "Uninstall must NOT delete %LOCALAPPDATA%\\Courier data"


def test_build_package_integrates_inno_setup():
    build_script = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "build_package.ps1"
    assert build_script.is_file(), "build_package.ps1 must exist"
    content = build_script.read_text(encoding="utf-8")
    assert "courier_installer.iss" in content, "build_package.ps1 must reference courier_installer.iss"
    assert "ISCC.exe" in content, "build_package.ps1 must invoke Inno Setup compiler ISCC.exe"
    assert "CourierSetup-v1.exe" in content, "build_package.ps1 must target CourierSetup-v1.exe"


def test_install_service_scheduled_task_contract():
    """Verify install_service.ps1 scheduled task definition and per-user non-admin support."""
    service_script = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "install_service.ps1"
    assert service_script.is_file(), "install_service.ps1 must exist"
    content = service_script.read_text(encoding="utf-8")
    assert "$taskName = \"CourierWindowsWorker\"" in content
    assert "Unregister-ScheduledTask" in content
    assert "Register-ScheduledTask" in content
    assert "$PerUser" in content
    assert "New-ScheduledTaskTrigger -AtLogOn" in content
    assert "New-ScheduledTaskTrigger -AtStartup" in content
    assert "RunLevel Limited" in content


def test_packaging_contains_full_runtime_without_developer_checkout():
    """Verify build_package.ps1 stages complete runtime packages for standalone execution."""
    build_script = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "build_package.ps1"
    content = build_script.read_text(encoding="utf-8")
    
    # Required application runtime packages
    required_packages = [
        "courier_core",
        "courier_hub",
        "courier_worker",
        "adapters",
        "courier_runtime",
        "courier_overlay",
    ]
    for pkg in required_packages:
        assert f'"{pkg}"' in content, f"build_package.ps1 must stage runtime package {pkg}"
    
    # Python 3.12 embeddable support matching pyproject.toml
    assert 'PythonVersion = "3.12.10"' in content or '3.12' in content
    assert "python312._pth" in content
    assert "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3" in content
    
    # Inno Setup packages the dist payload into {app}
    iss_content = ISS_PATH.read_text(encoding="utf-8")
    assert 'Source: "dist\\*"' in iss_content
    assert 'DestDir: "{app}"' in iss_content


def test_user_data_separated_from_program_files():
    """Verify program files ({app}) are isolated from user data (%LOCALAPPDATA%\\Courier)."""
    iss_content = ISS_PATH.read_text(encoding="utf-8")
    # App binaries target CourierWorker
    assert "{localappdata}\\CourierWorker" in iss_content
    # User database and logs remain under %LOCALAPPDATA%\Courier
    assert "{localappdata}\\Courier\\*" not in iss_content


def test_inno_setup_no_writing_to_foreign_user_directories():
    """Verify installer operates strictly per-user and touches no foreign user directories."""
    iss_content = ISS_PATH.read_text(encoding="utf-8")
    assert "PrivilegesRequired=lowest" in iss_content
    assert "{commonappdata}" not in iss_content
    assert "{commondesktop}" not in iss_content
    assert "{commonprograms}" not in iss_content
    assert "{commonstartup}" not in iss_content



