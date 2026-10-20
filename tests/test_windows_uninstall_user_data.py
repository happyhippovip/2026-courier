"""Uninstall keeps the ledger unless the user asks for it to be removed.

Rule 0 step 12: program files go away, user data stays, and an explicit
choice can remove that data too. A hardcoded C:\\Users walk misses a
profile that is not on that drive.
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "scripts" / "windows_worker" / "uninstall_user_data.ps1"
UNINSTALL = ROOT / "scripts" / "windows_worker" / "uninstall.ps1"


def test_uninstall_asks_before_removing_user_data():
    text = UNINSTALL.read_text(encoding="utf-8")
    assert "[switch]$RemoveUserData" in text
    assert "uninstall_user_data.ps1" in text
    assert 'Join-Path $env:SystemDrive "Users"' in text
    assert '$usersDir = "C:\\Users"' not in text
    cleanup = text.index("uninstall_user_data.ps1")
    remove_install = text.index("Remove-Item -Recurse -Force $InstallDir")
    assert cleanup < remove_install
    remove_line = next(line for line in text.splitlines() if "Remove-Item -Recurse -Force $InstallDir" in line)
    assert "-ErrorAction Stop" in remove_line
    assert "the installation is still present" in text
    assert "Database and logs" in text
    assert "was removed" in text
    unregister = text.index("Unregister-ScheduledTask")
    still_there = text.index("the scheduled task is still present")
    claimed_gone = text.index("Unregistered and stopped")
    assert unregister < still_there < claimed_gone < cleanup
    assert "Get-ScheduledTask" in text[unregister:still_there]
    assert "exit 1" in text[still_there:claimed_gone]


def _powershell():
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _profile(root, name):
    courier = root / name / "AppData" / "Local" / "Courier"
    (courier / "run").mkdir(parents=True)
    (courier / "logs").mkdir()
    (courier / "config.json").write_text('{"COURIER_API_KEY":"secret"}', encoding="utf-8")
    (courier / "run" / "controller.token").write_text("secret-token", encoding="utf-8")
    (courier / "logs" / "host.log").write_text("log", encoding="utf-8")
    (courier / "courier.db").write_text("ledger", encoding="utf-8")
    return courier


def _run(users, remove):
    shell = _powershell()
    if shell is None:
        return None
    command = [
        shell, "-NoProfile", "-File", str(CLEAN),
        "-UsersRoot", str(users),
    ]
    if remove:
        command.append("-RemoveUserData")
    return subprocess.run(command, text=True, capture_output=True, timeout=30)


def test_default_uninstall_keeps_the_ledger_and_logs(tmp_path):
    courier = _profile(tmp_path, "alice")
    completed = _run(tmp_path, remove=False)
    if completed is None:
        return
    text = completed.stdout + completed.stderr
    assert completed.returncode == 0, text
    assert not (courier / "config.json").exists()
    assert not (courier / "run").exists()
    assert (courier / "courier.db").read_text(encoding="utf-8") == "ledger"
    assert (courier / "logs" / "host.log").read_text(encoding="utf-8") == "log"
    assert "preserved" in text


def test_remove_user_data_deletes_the_courier_directory(tmp_path):
    courier = _profile(tmp_path, "alice")
    other = tmp_path / "alice" / "Documents" / "keep.txt"
    other.parent.mkdir(parents=True)
    other.write_text("keep", encoding="utf-8")
    completed = _run(tmp_path, remove=True)
    if completed is None:
        return
    text = completed.stdout + completed.stderr
    assert completed.returncode == 0, text
    assert not courier.exists()
    assert other.read_text(encoding="utf-8") == "keep"
    assert "Removed user data" in text
