"""The packaged uninstaller must not report removal while the install directory remains.

pwsh runs scripts/windows_worker/dist/uninstall.ps1. This is not a Windows
machine and not a clean-machine uninstall. Scheduled tasks are not registered.
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
    if os.geteuid() == 0:
        pytest.skip("root bypasses mode 000, so this host cannot show the removal failure")
    program_files = tmp_path / "pf"
    install_dir = program_files / "CourierWorker"
    install_dir.mkdir(parents=True)
    (install_dir / "keep.txt").write_text("keep", encoding="utf-8")
    os.chmod(install_dir, 0)
    try:
        proc = _run(program_files)
    finally:
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
