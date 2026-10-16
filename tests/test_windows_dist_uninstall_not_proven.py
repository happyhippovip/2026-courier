"""The packaged uninstaller must not report removal while the install directory remains.

pwsh runs scripts/windows_worker/dist/uninstall.ps1.
Scheduled tasks are not registered in unit test environment.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_worker" / "dist" / "uninstall.ps1"
COMPLETE = "Uninstall complete."


def _pwsh():
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    pytest.skip("pwsh is not installed, so the packaged uninstaller was not executed")


def _run(program_files: Path):
    env = os.environ.copy()
    env["ProgramFiles"] = str(program_files)
    return subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_failed_removal_is_not_complete(tmp_path):
    if getattr(os, "geteuid", None) == 0:
        pytest.skip("root bypasses mode 000, so this host cannot show the removal failure")
    program_files = tmp_path / "pf"
    install_dir = program_files / "CourierWorker"
    install_dir.mkdir(parents=True)
    locked_file = install_dir / "keep.txt"
    locked_file.write_text("keep", encoding="utf-8")

    f = None
    if os.name == "nt":
        # On Windows, keep an open write handle so Remove-Item fails with access violation
        try:
            f = open(locked_file, "r+")
        except OSError:
            pass
    else:
        os.chmod(install_dir, 0)

    try:
        proc = _run(program_files)
    finally:
        if f is not None:
            f.close()
        elif os.name != "nt":
            os.chmod(install_dir, 0o755)

    assert proc.returncode != 0
    assert COMPLETE not in proc.stdout
    assert "Removed installation directory:" not in proc.stdout
    assert (install_dir / "keep.txt").is_file()


def test_removed_directory_is_complete(tmp_path):
    program_files = tmp_path / "pf"
    install_dir = program_files / "CourierWorker"
    install_dir.mkdir(parents=True)
    (install_dir / "gone.txt").write_text("gone", encoding="utf-8")
    proc = _run(program_files)
    assert proc.returncode == 0, proc.stderr
    assert COMPLETE in proc.stdout
    assert not install_dir.exists()


def test_uninstaller_script_preserves_user_data_contract():
    """Verify uninstall.ps1 and dist/uninstall.ps1 preserve user database and logs."""
    root_uninstall = ROOT / "scripts" / "windows_worker" / "uninstall.ps1"
    dist_uninstall = ROOT / "scripts" / "windows_worker" / "dist" / "uninstall.ps1"
    
    assert root_uninstall.is_file()
    assert dist_uninstall.is_file()
    
    root_text = root_uninstall.read_text(encoding="utf-8")
    dist_text = dist_uninstall.read_text(encoding="utf-8")
    
    # Contract: uninstall removes binaries in InstallDir, but never purges courier.db or logs
    assert "Database and logs in %LOCALAPPDATA%\\Courier were preserved." in root_text
    assert "User data in %LOCALAPPDATA%\\Courier was preserved." in dist_text
    assert "Remove-Item -LiteralPath $InstallDir" in root_text
    assert "Remove-Item -LiteralPath $InstallDir" in dist_text

