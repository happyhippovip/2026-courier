"""Status may report only the Courier process this install recorded.

Scanning every Courier.exe made a second checkout look like this worker
was running. A missing record is not a running service.
"""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_PS1 = ROOT / "scripts" / "windows_worker" / "status.ps1"
STATUS_BAT = ROOT / "scripts" / "windows_worker" / "status.bat"


def test_status_bat_does_not_scan_every_courier_exe():
    text = STATUS_BAT.read_text(encoding="utf-8")
    assert "tasklist" not in text.lower()
    assert "findstr" not in text.lower()
    assert "status.ps1" in text
    assert "exit /b %ERRORLEVEL%" in text


def test_status_script_checks_the_recorded_process():
    text = STATUS_PS1.read_text(encoding="utf-8")
    assert 'Test-CourierProcessName -Actual $proc.ProcessName -Expected "Courier"' in text
    assert "tasklist" not in text.lower()
    assert "/IM" not in text
    assert "Stop-Process" not in text
    assert "exit 0" in text
    assert "exit 2" in text


def _powershell():
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _run_status(tmp_path, pid_text=None):
    shell = _powershell()
    if shell is None:
        return None
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(exist_ok=True)
    shutil.copy(STATUS_PS1, script_dir / "status.ps1")
    if pid_text is None:
        pid_file = script_dir / "worker.pid"
        if pid_file.exists():
            pid_file.unlink()
    else:
        (script_dir / "worker.pid").write_text(pid_text, encoding="utf-8")
    local = tmp_path / "local"
    home = tmp_path / "home"
    local.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local)
    env["COURIER_HOME"] = str(home)
    return subprocess.run(
        [shell, "-NoProfile", "-File", str(script_dir / "status.ps1")],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_windows_instance_suffix_is_still_courier():
    shell = _powershell()
    if shell is None:
        return
    script = (
        f". '{STATUS_PS1}' -Library\n"
        "if (-not (Test-CourierProcessName -Actual 'Courier#1' -Expected 'Courier')) { exit 1 }\n"
        "if (-not (Test-CourierProcessName -Actual 'Courier.exe' -Expected 'Courier')) { exit 1 }\n"
        "if (Test-CourierProcessName -Actual 'notepad' -Expected 'Courier') { exit 1 }\n"
        "if (Test-CourierProcessName -Actual 'CourierHelper' -Expected 'Courier') { exit 1 }\n"
        "exit 0\n"
    )
    completed = subprocess.run(
        [shell, "-NoProfile", "-Command", script],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_status_with_no_record_is_not_running(tmp_path):
    completed = _run_status(tmp_path)
    if completed is None:
        return
    text = completed.stdout + completed.stderr
    assert completed.returncode == 2, text
    assert "No owned Courier process was recorded." in text


def test_status_does_not_call_a_foreign_process_running(tmp_path):
    completed = _run_status(tmp_path, f"{os.getpid()}\n")
    if completed is None:
        return
    text = completed.stdout + completed.stderr
    assert completed.returncode == 2, text
    assert "not Courier" in text
    assert os.getpid() > 0


def test_status_reports_a_matching_courier_process(tmp_path):
    shell = _powershell()
    sleep = shutil.which("sleep")
    if shell is None or sleep is None:
        return
    courier = tmp_path / ("Courier.exe" if os.name == "nt" else "Courier")
    shutil.copy(sleep, courier)
    courier.chmod(0o755)
    try:
        proc = subprocess.Popen([str(courier), "30"])
    except OSError:
        return
    try:
        identity = subprocess.run(
            [
                shell, "-NoProfile", "-Command",
                f"(Get-Process -Id {proc.pid}).ProcessName + '|' + "
                f"(Get-Process -Id {proc.pid}).StartTime.ToUniversalTime().ToString('o')",
            ],
            text=True,
            capture_output=True,
            timeout=20,
        )
        name, _, stamp = identity.stdout.strip().partition("|")
        if name.split("#", 1)[0].lower().removesuffix(".exe") != "courier" or not stamp:
            return
        wrong = _run_status(tmp_path, f"{proc.pid}\n1970-01-01T00:00:00.0000000Z\n")
        assert wrong.returncode == 2, wrong.stdout + wrong.stderr
        assert proc.poll() is None
        ok = _run_status(tmp_path, f"{proc.pid}\n{stamp}\n")
        text = ok.stdout + ok.stderr
        assert ok.returncode == 0, text
        assert f"PID {proc.pid}" in text
        assert proc.poll() is None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
