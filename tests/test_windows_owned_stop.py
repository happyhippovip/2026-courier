"""User-facing stop may end only the Courier process this install recorded.

`taskkill /IM Courier.exe` also killed a second checkout, a decoy, and any
other user's Courier. The stop script refuses a pid whose image is not
Courier or whose start time does not match the record.
"""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP_PS1 = ROOT / "scripts" / "windows_worker" / "stop.ps1"
STOP_BAT = ROOT / "scripts" / "windows_worker" / "stop.bat"
UNINSTALL = ROOT / "scripts" / "windows_worker" / "uninstall.ps1"
LAUNCHER = ROOT / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"
BOOTSTRAP = ROOT / "scripts" / "windows_worker" / "bootstrap.ps1"


def test_stop_bat_does_not_kill_by_image_name():
    text = STOP_BAT.read_text(encoding="utf-8")
    assert "/IM" not in text
    assert "taskkill" not in text.lower()
    assert "stop.ps1" in text
    assert "exit /b %ERRORLEVEL%" in text


def test_stop_script_targets_recorded_pid_only():
    text = STOP_PS1.read_text(encoding="utf-8")
    assert "Stop-Process -Id $processId" in text
    assert "ProcessName -ne \"Courier\"" in text
    assert "/IM" not in text
    assert "Stop-Process -Name" not in text
    assert "exit 1" in text
    assert "exit 2" in text
    assert "ToUniversalTime" in text


def test_launcher_records_its_own_pid_and_start_time():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "launcher.pid" in text
    assert "GetCurrentProcess()" in text
    assert "StartTime.ToUniversalTime()" in text
    # A second instance only opens the hub. It must not overwrite the owner's pid.
    owner = text.index("GetCurrentProcess()")
    second = text.index("if (!createdNew)")
    assert second < owner


def test_bootstrap_records_pid_and_start_time():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "worker.pid" in text
    assert "StartTime.ToUniversalTime()" in text


def test_uninstall_stops_owned_processes_before_deleting_files():
    text = UNINSTALL.read_text(encoding="utf-8")
    stop_at = text.index("stop.ps1")
    remove_at = text.index("Remove-Item -Recurse -Force $InstallDir")
    assert stop_at < remove_at
    assert "LASTEXITCODE -eq 1" in text
    assert "-AllProfiles" in text


def _powershell():
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _run_stop(tmp_path, pid_text):
    shell = _powershell()
    if shell is None:
        return None
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(exist_ok=True)
    shutil.copy(STOP_PS1, script_dir / "stop.ps1")
    (script_dir / "worker.pid").write_text(pid_text, encoding="utf-8")
    local = tmp_path / "local"
    home = tmp_path / "home"
    local.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local)
    env["COURIER_HOME"] = str(home)
    env["SystemDrive"] = str(tmp_path / "nodrive")
    completed = subprocess.run(
        [shell, "-NoProfile", "-File", str(script_dir / "stop.ps1")],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return completed


def test_stop_refuses_a_process_that_is_not_courier(tmp_path):
    completed = _run_stop(tmp_path, f"{os.getpid()}\n")
    if completed is None:
        return
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "Refusing" in completed.stdout
    assert (tmp_path / "scripts" / "worker.pid").exists()


def test_stop_with_no_record_exits_without_killing(tmp_path):
    shell = _powershell()
    if shell is None:
        return
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(exist_ok=True)
    shutil.copy(STOP_PS1, script_dir / "stop.ps1")
    local = tmp_path / "local"
    home = tmp_path / "home"
    local.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["LOCALAPPDATA"] = str(local)
    env["COURIER_HOME"] = str(home)
    before = os.getpid()
    completed = subprocess.run(
        [shell, "-NoProfile", "-File", str(script_dir / "stop.ps1")],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert os.getpid() == before


def test_stop_kills_only_a_courier_process_with_matching_start(tmp_path):
    shell = _powershell()
    sleep = shutil.which("sleep")
    if shell is None or sleep is None:
        return
    courier = tmp_path / "Courier"
    shutil.copy(sleep, courier)
    courier.chmod(0o755)
    proc = subprocess.Popen([str(courier), "30"])
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
        if name != "Courier" or not stamp:
            return
        wrong = _run_stop(tmp_path, f"{proc.pid}\n1970-01-01T00:00:00.0000000Z\n")
        assert wrong is not None
        assert wrong.returncode == 1, wrong.stdout + wrong.stderr
        assert proc.poll() is None
        ok = _run_stop(tmp_path, f"{proc.pid}\n{stamp}\n")
        # Windows clears the process and the script exits 0. PowerShell on Linux
        # sometimes reports that process until the shell itself exits.
        if ok.returncode != 0 and proc.poll() is None:
            assert ok.returncode == 0, ok.stdout + ok.stderr
        if proc.poll() is None:
            proc.wait(timeout=5)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
