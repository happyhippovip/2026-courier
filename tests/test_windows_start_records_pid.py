"""start.bat must record the Courier process it starts.

An unrecorded Courier.exe cannot be stopped without killing every process
of that name. A second start leaves the live record alone.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
START_BAT = ROOT / "scripts" / "windows_worker" / "start.bat"
START_PS1 = ROOT / "scripts" / "windows_worker" / "start.ps1"


def test_start_bat_records_a_pid_instead_of_detaching():
    bat = START_BAT.read_text(encoding="utf-8")
    ps1 = START_PS1.read_text(encoding="utf-8")
    assert "start.ps1" in bat
    assert 'start ""' not in bat
    assert "worker.pid" in ps1
    assert "Courier.exe was not found" in ps1
    assert "already running" in ps1


def _pwsh():
    for candidate in ("/tmp/pwsh/pwsh", "pwsh", "powershell"):
        if candidate.startswith("/") and Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    pytest.skip("powershell is not installed")


def _run(script):
    result = subprocess.run(
        [_pwsh(), "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result


def test_missing_executable_does_not_write_a_pid(tmp_path):
    pidfile = tmp_path / "worker.pid"
    result = _run(
        f". '{START_PS1}'\n"
        f"$out = @(Start-CourierWorker -ExePath '{tmp_path / 'Courier.exe'}' -PidFile '{pidfile}')\n"
        "$out | Select-Object -SkipLast 1 | Write-Output\n"
        "exit $out[-1]\n"
    )
    assert result.returncode == 1
    assert "Courier.exe was not found" in result.stdout
    assert not pidfile.exists()


def test_start_records_the_live_process_once(tmp_path):
    py = shutil.which("python3") or shutil.which("python")
    if not py:
        pytest.skip("python is not installed")
    name = Path(py).stem
    pidfile = tmp_path / "worker.pid"
    hold = tmp_path / "hold.py"
    hold.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    result = _run(
        f". '{START_PS1}'\n"
        f"$out = @(Start-CourierWorker -ExePath '{py}' -PidFile '{pidfile}' "
        f"-ExpectedName '{name}' -ArgumentList '{hold}')\n"
        "if ($out[-1] -ne 0) { $out | Write-Output; exit 1 }\n"
        f"$lines = @(Get-Content -LiteralPath '{pidfile}')\n"
        "if (-not $lines[1].Trim()) { exit 1 }\n"
        "$procId = [int]$lines[0].Trim()\n"
        "$alive = Get-Process -Id $procId -ErrorAction SilentlyContinue\n"
        "if (-not $alive) { Write-Output 'started process was already gone'; exit 1 }\n"
        f"$again = @(Start-CourierWorker -ExePath '{py}' -PidFile '{pidfile}' "
        f"-ExpectedName '{name}' -ArgumentList '{hold}')\n"
        "if ($again[-1] -ne 0) { exit 1 }\n"
        "$again | Select-Object -SkipLast 1 | Write-Output\n"
        f"$still = [int]((Get-Content -LiteralPath '{pidfile}')[0].Trim())\n"
        "if ($still -ne $procId) { Write-Output 'pid file was replaced'; exit 1 }\n"
        "Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue\n"
        "exit 0\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already running" in result.stdout
