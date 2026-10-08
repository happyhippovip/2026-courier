"""build_launcher.ps1 must not report success when Courier.exe was not built.

pwsh runs the script. csc.exe is a stub. This is not a Windows machine and
not a clean-machine install. A windows-latest run would be CI only.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_worker" / "launcher" / "build_launcher.ps1"


def _pwsh():
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    pytest.skip("pwsh is not installed, so the launcher build script was not executed")


def _layout(tmp_path: Path, csc_body: str | None):
    windir = tmp_path / "windir"
    launcher = tmp_path / "launcher"
    launcher.mkdir()
    shutil.copy(SCRIPT, launcher / "build_launcher.ps1")
    (launcher / "CourierLauncher.cs").write_text("class C {}\n", encoding="utf-8")
    if csc_body is not None:
        csc = windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
        csc.parent.mkdir(parents=True)
        csc.write_text(csc_body, encoding="utf-8")
        csc.chmod(0o755)
    else:
        windir.mkdir()
    return windir, launcher / "build_launcher.ps1"


def _run(windir: Path, script: Path):
    env = os.environ.copy()
    env["windir"] = str(windir)
    env["CSC_LOG"] = str(script.parent.parent / "csc.log")
    return subprocess.run(
        [_pwsh(), "-NoProfile", "-File", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_compiler_exit_is_not_success(tmp_path):
    body = "#!/bin/sh\necho csc-fail\nexit 1\n"
    windir, script = _layout(tmp_path, body)
    proc = _run(windir, script)
    assert proc.returncode != 0
    assert "Success:" not in proc.stdout
    assert not (tmp_path / "Courier.exe").exists()


def test_missing_output_is_not_success(tmp_path):
    body = "#!/bin/sh\necho csc-ok\nexit 0\n"
    windir, script = _layout(tmp_path, body)
    proc = _run(windir, script)
    assert proc.returncode != 0
    assert "Success:" not in proc.stdout
    assert not (tmp_path / "Courier.exe").exists()


def test_missing_compiler_is_not_success(tmp_path):
    windir, script = _layout(tmp_path, None)
    proc = _run(windir, script)
    assert proc.returncode != 0
    assert "Success:" not in proc.stdout


def test_written_exe_reports_success(tmp_path):
    body = """#!/bin/sh
out=
for arg in "$@"; do
  case "$arg" in
    /out:*) out=${arg#/out:} ;;
  esac
done
out=$(printf '%s' "$out" | tr -d '"')
printf 'exe\\n' > "$out"
exit 0
"""
    windir, script = _layout(tmp_path, body)
    proc = _run(windir, script)
    assert proc.returncode == 0, proc.stderr
    assert "Success: Courier.exe built." in proc.stdout
    assert (tmp_path / "Courier.exe").is_file()
