"""uninstall.ps1 must verify removal instead of printing success.

The static contract runs on every platform and fails on the trunk script,
which prints "Uninstall complete" even when a scheduled task is still
registered. The native tests run only on Windows: they register a throwaway
current-user task and never touch the real CourierWindowsWorker task.
"""

import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_worker" / "uninstall.ps1"
INSTALL = ROOT / "scripts" / "windows_worker" / "install.ps1"
INSTALL_SERVICE = ROOT / "scripts" / "windows_worker" / "install_service.ps1"
TASK_NAME = "CourierWindowsWorker"


def _script_text():
    return SCRIPT.read_text(encoding="utf-8")


def _assigned_task_names(*paths):
    names = set()
    pattern = re.compile(r'\$(?:TaskName|taskName)\s*=\s*"([^"]+)"')
    for path in paths:
        names.update(pattern.findall(path.read_text(encoding="utf-8")))
    return names


def test_uninstall_verifies_removal_instead_of_printing_success():
    """Trunk prints Uninstall complete with no re-query and requires an admin."""
    text = _script_text()
    failures = []

    if "Uninstall complete" in text:
        failures.append("prints Uninstall complete")
    if "nothing installed" not in text:
        failures.append("does not say nothing installed when there is nothing to remove")
    if "IsInRole" in text or "Run as Administrator" in text:
        failures.append("requires elevation before the user-task path can run")
    if "C:\\Users" in text:
        failures.append("sweeps every user profile instead of the targeted Courier paths")

    unregister_at = text.find("Unregister-ScheduledTask")
    requery_at = text.find("Get-ScheduledTask", unregister_at + 1 if unregister_at >= 0 else 0)
    if unregister_at < 0 or requery_at < 0:
        failures.append("does not re-query Get-ScheduledTask after Unregister-ScheduledTask")
    if "still registered" not in text:
        failures.append("a remaining task has no precise still-registered message")
    if "exit 1" not in text:
        failures.append("a remaining task does not exit nonzero")

    names = _assigned_task_names(INSTALL, INSTALL_SERVICE)
    if names != {TASK_NAME}:
        failures.append(f"install scripts register unexpected task names: {sorted(names)}")
    for name in names:
        if f'@("{name}")' not in text and f"@('{name}')" not in text:
            failures.append(f"default task list does not include {name}, including the legacy SYSTEM registration")
    if "SYSTEM" not in INSTALL.read_text(encoding="utf-8"):
        failures.append("install.ps1 no longer shows the legacy SYSTEM principal this uninstall must remove")
    if re.search(r"UserId.*SYSTEM|skip.*SYSTEM", text, re.I):
        failures.append("uninstall filters out the legacy SYSTEM task instead of removing it by name")

    if "[string[]]$TaskName" not in text and "[string]$TaskName" not in text:
        failures.append("no TaskName parameter, so a test cannot target a throwaway task")
    if "SimulateRemovalFailure" not in text:
        failures.append("no parameter to simulate a removal that does not stick")

    if "taskkill" in text.lower() or re.search(r"Stop-Process\s+-Name", text):
        failures.append("kills processes by name")
    if "ExecutablePath" not in text or "-ieq" not in text or "Courier.exe" not in text:
        failures.append("does not match a worker process by the exact Courier.exe path")
    if "Stop-Process -Id" not in text:
        failures.append("does not stop an attributable process by pid")

    for banned in ("Set-Acl", "icacls", "Defender", "HKLM:", "HKCU:", "Registry::"):
        if banned in text:
            failures.append(f"touches forbidden surface {banned}")

    assert not failures, "uninstall.ps1 contract failed:\n- " + "\n- ".join(failures)


def _powershell(args):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def _unregister(task_name):
    _powershell([
        "-Command",
        f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false -ErrorAction SilentlyContinue",
    ])


def _task_exists(task_name):
    query = _powershell([
        "-Command",
        (
            "$name = '{name}'; "
            "try {{ $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop }} catch {{ $task = $null }}; "
            "if ($null -eq $task) {{ 'absent' }} else {{ 'present' }}"
        ).format(name=task_name),
    ])
    assert query.returncode == 0, query.stdout + query.stderr
    return "present" in query.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Scheduled task registration is Windows only")
def test_native_uninstall_removes_throwaway_task_and_is_idempotent(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "Courier.exe").write_bytes(b"")
    (install_dir / "readme.txt").write_text("program", encoding="utf-8")
    data_dir = tmp_path / "data"
    (data_dir / "run").mkdir(parents=True)
    (data_dir / "run" / "pid.txt").write_text("1", encoding="utf-8")
    (data_dir / "config.json").write_text("{}\n", encoding="utf-8")
    (data_dir / "daemon.log").write_text("keep\n", encoding="utf-8")
    task_name = "CourierUninstall" + uuid.uuid4().hex[:12]
    try:
        registered = _powershell([
            "-Command",
            (
                "$taskName = '{name}'; "
                "$installDir = '{install}'; "
                "$exe = Join-Path $installDir 'Courier.exe'; "
                "$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
                "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user; "
                "$action = New-ScheduledTaskAction -Execute $exe -WorkingDirectory $installDir; "
                "$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited; "
                "Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action "
                "-Principal $principal | Out-Null; "
                "'registered'"
            ).format(name=task_name, install=str(install_dir)),
        ])
        assert registered.returncode == 0, registered.stdout + registered.stderr
        assert _task_exists(task_name)

        removed = _powershell([
            "-File", str(SCRIPT),
            "-TaskName", task_name,
            "-InstallDir", str(install_dir),
            "-DataDir", str(data_dir),
        ])
        combined = removed.stdout + removed.stderr
        assert removed.returncode == 0, combined
        assert "Uninstall complete" not in combined
        assert not _task_exists(task_name)
        assert not install_dir.exists()
        assert not (data_dir / "config.json").exists()
        assert not (data_dir / "run").exists()
        assert (data_dir / "daemon.log").read_text(encoding="utf-8") == "keep\n"

        again = _powershell([
            "-File", str(SCRIPT),
            "-TaskName", task_name,
            "-InstallDir", str(install_dir),
            "-DataDir", str(data_dir),
        ])
        assert again.returncode == 0, again.stdout + again.stderr
        assert "nothing installed" in (again.stdout + again.stderr).lower()
    finally:
        _unregister(task_name)


@pytest.mark.skipif(sys.platform != "win32", reason="Scheduled task registration is Windows only")
def test_native_uninstall_reports_a_removal_that_does_not_stick(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "Courier.exe").write_bytes(b"")
    task_name = "CourierUninstallFail" + uuid.uuid4().hex[:12]
    try:
        registered = _powershell([
            "-Command",
            (
                "$taskName = '{name}'; "
                "$exe = '{exe}'; "
                "$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
                "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user; "
                "$action = New-ScheduledTaskAction -Execute $exe; "
                "$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited; "
                "Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action "
                "-Principal $principal | Out-Null"
            ).format(name=task_name, exe=str(install_dir / "Courier.exe")),
        ])
        assert registered.returncode == 0, registered.stdout + registered.stderr

        failed = _powershell([
            "-File", str(SCRIPT),
            "-TaskName", task_name,
            "-InstallDir", str(install_dir),
            "-DataDir", str(tmp_path / "unused-data"),
            "-SimulateRemovalFailure",
        ])
        combined = failed.stdout + failed.stderr
        assert failed.returncode != 0, combined
        assert "still registered" in combined.lower()
        assert "uninstall complete" not in combined.lower()
        assert "nothing installed" not in combined.lower()
        assert _task_exists(task_name)
        assert install_dir.exists()
    finally:
        _unregister(task_name)
