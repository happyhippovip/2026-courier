"""Parse-level contract for scripts/windows_worker/install.ps1.

The launcher starts a local controller and keeps user data under
%LOCALAPPDATA%\\Courier. The installer must be able to finish with no
prompts, must not invent a remote server or write the controller credential,
and must register CourierWindowsWorker for the installing user so that home
matches the launcher. uninstall.ps1 removes that same task name and
%ProgramFiles%\\CourierWorker; this module only reads those scripts.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
INSTALL = REPO / "scripts" / "windows_worker" / "install.ps1"
UNINSTALL = REPO / "scripts" / "windows_worker" / "uninstall.ps1"
LAUNCHER = REPO / "scripts" / "windows_worker" / "launcher" / "CourierLauncher.cs"

_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _install_text() -> str:
    return INSTALL.read_text(encoding="utf-8")


def test_install_ps1_has_no_interactive_prompts_or_remote_address():
    text = _install_text()
    lowered = text.lower()
    assert "read-host" not in lowered
    assert "courier_server" not in lowered
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert _IPV4.search(text) is None


def test_install_ps1_does_not_write_a_credential():
    text = _install_text()
    lowered = text.lower()
    assert "controller.token" not in lowered
    assert "apikey" not in lowered
    assert "api_key" not in lowered
    assert "set-content" not in lowered
    assert "out-file" not in lowered
    assert "add-content" not in lowered
    assert "remove-item" not in lowered


def test_install_ps1_logon_task_runs_as_the_installing_user():
    text = _install_text()
    assert "SYSTEM" not in text
    assert "ServiceAccount" not in text
    assert "Start-ScheduledTask" not in text
    assert "WindowsIdentity" in text
    assert "AtLogOn" in text
    assert "LogonType Interactive" in text
    assert "-UserId $principalUser" in text
    assert "CourierWindowsWorker" in text
    no_task = text.index("if ($NoTask)")
    register = text.index("Register-ScheduledTask")
    assert "exit 0" in text[no_task:register]
    assert text.index("Unregister-ScheduledTask") < register


def _program_files_courier_worker(text: str) -> bool:
    return (
        r"$env:ProgramFiles\CourierWorker" in text
        or 'Join-Path $env:ProgramFiles "CourierWorker"' in text
    )


def _localappdata_courier(text: str) -> bool:
    return (
        r"$env:LOCALAPPDATA\Courier" in text
        or 'Join-Path $env:LOCALAPPDATA "Courier"' in text
    )


def test_install_paths_match_uninstall_and_launcher_home():
    install = _install_text()
    uninstall = UNINSTALL.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")
    assert "CourierWindowsWorker" in install
    assert "CourierWindowsWorker" in uninstall
    assert _program_files_courier_worker(install)
    assert r"$env:ProgramFiles\CourierWorker" in uninstall
    assert _localappdata_courier(install)
    assert r"%LOCALAPPDATA%\Courier" in launcher
    assert r"AppData\Local\Courier" in uninstall


def test_install_ps1_declares_clear_exit_codes():
    text = _install_text()
    for code in (0, 1, 2, 3):
        assert f"exit {code}" in text
    assert "[switch]$NoTask" in text
    assert "[string]$InstallRoot" in text
    assert "[string]$DataRoot" in text


def _powershell(args, cwd):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALL),
            *args,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 runs on Windows")
def test_install_ps1_temp_root_is_idempotent_and_writes_no_credential(tmp_path):
    install_root = tmp_path / "CourierWorker"
    data_root = tmp_path / "Courier"
    data_root.mkdir()
    (data_root / "courier.db").write_text("keep-db", encoding="utf-8")
    log_dir = data_root / "logs"
    log_dir.mkdir()
    (log_dir / "controller.log").write_text("keep-log", encoding="utf-8")
    run_dir = data_root / "run"
    run_dir.mkdir()
    token = run_dir / "controller.token"
    token.write_text("preserved-by-controller\n", encoding="utf-8")
    config = data_root / "config.json"
    config.write_text('{"COURIER_CONTROLLER_PORT": 8800}', encoding="utf-8")

    args = [
        "-InstallRoot",
        str(install_root),
        "-DataRoot",
        str(data_root),
        "-NoTask",
    ]
    first = _powershell(args, tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    second = _powershell(args, tmp_path)
    assert second.returncode == 0, second.stdout + second.stderr

    installed = (install_root / "install.ps1").read_text(encoding="utf-8")
    assert "Read-Host" not in installed
    assert (data_root / "courier.db").read_text(encoding="utf-8") == "keep-db"
    assert (log_dir / "controller.log").read_text(encoding="utf-8") == "keep-log"
    assert token.read_text(encoding="utf-8") == "preserved-by-controller\n"
    assert config.read_text(encoding="utf-8") == '{"COURIER_CONTROLLER_PORT": 8800}'

    fresh = tmp_path / "fresh-home"
    fresh_install = tmp_path / "fresh-install"
    fresh_run = _powershell(
        ["-InstallRoot", str(fresh_install), "-DataRoot", str(fresh), "-NoTask"],
        tmp_path,
    )
    assert fresh_run.returncode == 0, fresh_run.stdout + fresh_run.stderr
    assert fresh.is_dir()
    assert not (fresh / "config.json").exists()
    assert not (fresh / "run" / "controller.token").exists()
    assert list(fresh.rglob("controller.token")) == []

    nested = REPO / "scripts" / "windows_worker" / "_install_contract_probe"
    try:
        rejected = _powershell(
            ["-InstallRoot", str(nested), "-DataRoot", str(tmp_path / "unused-data"), "-NoTask"],
            tmp_path,
        )
        assert rejected.returncode == 1
        assert "InstallRoot must be outside" in rejected.stdout + rejected.stderr
        assert not nested.exists()
    finally:
        if nested.exists():
            shutil.rmtree(nested)


def _task_info():
    script = r"""
$t = Get-ScheduledTask -TaskName 'CourierWindowsWorker' -ErrorAction SilentlyContinue
if (-not $t) { '{"found":false}'; exit 0 }
$trigger = @($t.Triggers)[0].CimClass.CimClassName
@{
  found = $true
  user = [string]$t.Principal.UserId
  logon = [string]$t.Principal.LogonType
  trigger = [string]$trigger
  execute = [string]@($t.Actions)[0].Execute
} | ConvertTo-Json -Compress
"""
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, proc.stdout + proc.stderr
    return json.loads(lines[-1])


def _unregister_task():
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Unregister-ScheduledTask -TaskName 'CourierWindowsWorker' -Confirm:$false -ErrorAction SilentlyContinue",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.skipif(
    not (sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") == "true"),
    reason="registers CourierWindowsWorker only on GitHub Actions Windows, then removes it",
)
def test_install_ps1_registers_per_user_logon_task_on_ci(tmp_path):
    install_root = tmp_path / "CourierWorker"
    data_root = tmp_path / "Courier"
    args = ["-InstallRoot", str(install_root), "-DataRoot", str(data_root)]
    try:
        first = _powershell(args, tmp_path)
        assert first.returncode == 0, first.stdout + first.stderr
        info = _task_info()
        assert info["found"] is True
        assert "SYSTEM" not in info["user"].upper()
        assert info["user"].strip()
        assert info["logon"] in ("Interactive", "3")
        assert "Logon" in info["trigger"]
        assert os.path.normcase(info["execute"]) == os.path.normcase(str(install_root / "Courier.exe"))

        second = _powershell(args, tmp_path)
        assert second.returncode == 0, second.stdout + second.stderr
        again = _task_info()
        assert again["found"] is True
        assert again["logon"] in ("Interactive", "3")
        assert "SYSTEM" not in again["user"].upper()
    finally:
        _unregister_task()
