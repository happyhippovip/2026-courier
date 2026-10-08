"""install_service.ps1 must register the current user's logon task, not SYSTEM.

The static contract runs on every platform and fails on the trunk script.
The native registration test runs only on Windows and removes its throwaway
task afterwards.
"""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows_worker" / "install_service.ps1"
TASK_NAME = "CourierWindowsWorker"


def _script_text():
    return SCRIPT.read_text(encoding="utf-8")


def _register_invocation(text):
    start = text.find("Register-ScheduledTask")
    if start < 0:
        return ""
    end = text.find("\n", start)
    return text[start:] if end < 0 else text[start:end]


def test_install_service_contract_rejects_system_startup_task():
    """Trunk registers SYSTEM at startup and prints registered with no check."""
    text = _script_text()
    failures = []

    if "ServiceAccount" in text:
        failures.append("principal uses LogonType ServiceAccount")
    if "SYSTEM" in text:
        failures.append("script still names SYSTEM")
    if "AtStartup" in text:
        failures.append("trigger is AtStartup")
    if "Highest" in text:
        failures.append("RunLevel is Highest")
    if "-AtLogOn -User $principalUser" not in text:
        failures.append("trigger is not AtLogOn for the current user")
    if "-LogonType Interactive" not in text:
        failures.append("LogonType is not Interactive")
    if "-RunLevel Limited" not in text:
        failures.append("RunLevel is not Limited")
    if "-UserId $principalUser" not in text:
        failures.append("principal UserId is not the current user")
    if "WindowsIdentity]::GetCurrent()" not in text:
        failures.append("current user is not read from WindowsIdentity")
    if "-WorkingDirectory $InstallDir" not in text:
        failures.append("action has no WorkingDirectory set to the install dir")
    if "$InstallDir = $PSScriptRoot" not in text:
        failures.append("install dir does not default to the script directory")
    invocation = _register_invocation(text)
    if "-ErrorAction Stop" not in invocation:
        failures.append("Register-ScheduledTask does not use -ErrorAction Stop")
    verify_at = text.find(".Principal.UserId")
    exit_at = text.find("exit 1", verify_at if verify_at >= 0 else 0)
    registered_at = text.lower().find("registered")
    if verify_at < 0 or exit_at < 0 or registered_at < 0 or not (verify_at < exit_at < registered_at):
        failures.append(
            "registration is not verified with Get-ScheduledTask before "
            "printing registered; mismatch must exit nonzero with no registered print"
        )
    if f'[string]$TaskName = "{TASK_NAME}"' not in text:
        failures.append(f"default task name is not {TASK_NAME}")
    if "Unregister-ScheduledTask" not in text:
        failures.append("re-run does not replace an existing task")
    other_names = {
        name for name in ("CourierWindowsWorkerService", "CourierWorkerTask", "CourierSystemTask")
        if name in text
    }
    if other_names:
        failures.append(f"second task name would compete with {TASK_NAME}: {sorted(other_names)}")

    assert not failures, "install_service.ps1 contract failed:\n- " + "\n- ".join(failures)


def _powershell(args, check=False):
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if check and completed.returncode != 0:
        raise AssertionError(completed.stdout + completed.stderr)
    return completed


def _unregister(task_name):
    _powershell([
        "-Command",
        f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false -ErrorAction SilentlyContinue",
    ])


@pytest.mark.skipif(sys.platform != "win32", reason="Scheduled task registration is Windows only")
def test_native_install_service_registers_current_user_and_replaces(tmp_path):
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "Courier.exe").write_bytes(b"")
    task_name = "CourierUserTask" + uuid.uuid4().hex[:12]
    try:
        first = _powershell([
            "-File", str(SCRIPT),
            "-TaskName", task_name,
            "-InstallDir", str(install_dir),
        ])
        assert first.returncode == 0, first.stdout + first.stderr
        assert "registered" in first.stdout.lower()

        second = _powershell([
            "-File", str(SCRIPT),
            "-TaskName", task_name,
            "-InstallDir", str(install_dir),
        ])
        assert second.returncode == 0, second.stdout + second.stderr

        query = _powershell([
            "-Command",
            (
                "$taskName = '{name}'; "
                "$task = Get-ScheduledTask -TaskName $taskName; "
                "$count = @(Get-ScheduledTask -TaskName $taskName).Count; "
                "$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name; "
                "$payload = [ordered]@{{ "
                "UserId = [string]$task.Principal.UserId; "
                "LogonType = [string]$task.Principal.LogonType; "
                "RunLevel = [string]$task.Principal.RunLevel; "
                "Trigger = [string]$task.Triggers[0].CimClass.CimClassName; "
                "WorkingDirectory = [string]$task.Actions[0].WorkingDirectory; "
                "Count = $count; "
                "Identity = [string]$identity "
                "}}; "
                "$payload | ConvertTo-Json -Compress"
            ).format(name=task_name),
        ])
        assert query.returncode == 0, query.stdout + query.stderr
        payload = json.loads(query.stdout.strip())
        assert payload["UserId"].upper() != "SYSTEM"
        assert payload["UserId"].casefold() == payload["Identity"].casefold()
        assert payload["LogonType"] == "Interactive"
        assert payload["RunLevel"] == "Limited"
        assert "Logon" in payload["Trigger"]
        assert "Boot" not in payload["Trigger"]
        assert os.path.normcase(payload["WorkingDirectory"]) == os.path.normcase(str(install_dir))
        assert payload["Count"] == 1
    finally:
        _unregister(task_name)


@pytest.mark.skipif(sys.platform != "win32", reason="Scheduled task registration is Windows only")
def test_native_install_service_failure_does_not_print_registered():
    task_name = "Courier\\Bad" + uuid.uuid4().hex[:8]
    completed = _powershell([
        "-File", str(SCRIPT),
        "-TaskName", task_name,
        "-InstallDir", r"C:\CourierInstallServiceContract",
    ])
    combined = (completed.stdout + completed.stderr).lower()
    assert completed.returncode != 0
    assert "registered" not in combined
