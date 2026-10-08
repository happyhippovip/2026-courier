"""The packaged installer must not report success when its files were not copied.

pwsh runs scripts/windows_worker/dist/install.ps1. ProgramFiles points at a
temp path. This is not a Windows machine and not a clean-machine install.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_worker" / "dist" / "install.ps1"
SUCCESS = "Courier installed successfully!"


def _pwsh():
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    pytest.skip("pwsh is not installed, so the packaged installer was not executed")


def _run(pkg: Path, program_files: Path, data: Path):
    env = os.environ.copy()
    env["ProgramFiles"] = str(program_files)
    env["LOCALAPPDATA"] = str(data)
    return subprocess.run(
        [
            _pwsh(),
            "-NoProfile",
            "-File",
            str(pkg / "install.ps1"),
            "-ServerArg",
            "http://127.0.0.1:9",
            "-ApiKeyArg",
            "dummy-not-a-secret",
            "-WorkerIdArg",
            "probe",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_failed_copy_is_not_installed(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    shutil.copy(SCRIPT, pkg / "install.ps1")
    (pkg / "marker.txt").write_text("marker", encoding="utf-8")
    blocked = tmp_path / "ProgramFiles"
    blocked.write_text("blocked", encoding="utf-8")
    proc = _run(pkg, blocked, tmp_path / "data")
    assert proc.returncode != 0
    assert SUCCESS not in proc.stdout
    assert not (tmp_path / "ProgramFiles" / "CourierWorker").exists()


def test_copied_files_report_installed(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    shutil.copy(SCRIPT, pkg / "install.ps1")
    (pkg / "marker.txt").write_text("marker", encoding="utf-8")
    program_files = tmp_path / "ProgramFiles"
    program_files.mkdir()
    proc = _run(pkg, program_files, tmp_path / "data")
    assert proc.returncode == 0, proc.stderr
    assert SUCCESS in proc.stdout
    assert (program_files / "CourierWorker" / "marker.txt").read_text(encoding="utf-8") == "marker"
