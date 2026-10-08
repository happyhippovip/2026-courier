"""Contract for scripts/windows_worker/bootstrap.ps1.

The API key must land in %LOCALAPPDATA%\\Courier\\config.json, merged with
keys already there, and never in the checkout. The health wait may only
trust a marker that daemon.py actually writes; otherwise it says the worker
was not verified and does not claim success.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "scripts" / "windows_worker" / "bootstrap.ps1"
DAEMON = REPO / "scripts" / "windows_worker" / "daemon.py"


def _bootstrap() -> str:
    return BOOTSTRAP.read_text(encoding="utf-8")


def _daemon() -> str:
    return DAEMON.read_text(encoding="utf-8")


def _health_section(text: str) -> str:
    marker = "Waiting for"
    assert marker in text
    return text[text.index(marker):]


def test_bootstrap_never_writes_the_api_key_under_the_script_directory():
    text = _bootstrap()
    config_assign = re.search(r"(?m)^\$configPath\s*=\s*(.+)$", text)
    assert config_assign, "bootstrap must assign $configPath"
    target = config_assign.group(1)
    assert "workerDir" not in target
    assert "PSScriptRoot" not in target
    assert 'Join-Path $workerDir "config.json"' not in text
    assert 'Join-Path $PSScriptRoot "config.json"' not in text
    assert "Set-Content" not in text


def test_bootstrap_merges_localappdata_courier_config():
    text = _bootstrap()
    assert 'Join-Path $env:LOCALAPPDATA "Courier"' in text
    assert 'Join-Path $dataDir "config.json"' in text
    config_at = text.index("$configPath")
    load_at = text.index("ConvertFrom-Json")
    write_at = text.index("WriteAllText")
    assert load_at < write_at
    assert "PSObject.Properties" in text[load_at:write_at]
    assert text.index("COURIER_API_KEY") < write_at
    assert config_at < write_at


def test_bootstrap_names_the_config_location_without_a_secure_claim():
    text = _bootstrap()
    assert "securely" not in text.lower()
    saved = [
        line for line in text.splitlines()
        if "Write-Host" in line and "Configuration saved" in line
    ]
    assert saved, "bootstrap must say where it saved configuration"
    for line in saved:
        assert "$configPath" in line
        assert "$apiKey" not in line
        assert "COURIER_API_KEY" not in line


def test_bootstrap_health_wait_is_truthful():
    bootstrap = _bootstrap()
    daemon = _daemon()
    assert 'LOG_DIR / "daemon.log"' in daemon
    assert "LOCALAPPDATA" in daemon
    health = _health_section(bootstrap)
    assert "daemon.log" in health
    assert "LOCALAPPDATA" in health
    assert "worker.log" not in bootstrap
    for marker in re.findall(r'-match\s+"([^"]+)"', health):
        assert marker in daemon, marker
    assert "Registered successfully" not in bootstrap
    assert "[SUCCESS]" not in bootstrap
    assert "not verified" in health.lower()
    assert "WARNING" in health
    warning_at = health.lower().index("not verified")
    assert re.search(r"exit\s+2", health[warning_at:warning_at + 500])
    assert re.search(r"\[int\]\$HealthTimeoutSec\s*=\s*30", bootstrap)


@pytest.mark.skipif(os.name != "nt", reason="bootstrap.ps1 runs on Windows")
def test_bootstrap_user_config_merge_and_no_success_claim(tmp_path):
    script_dir = tmp_path / "worker"
    script_dir.mkdir()
    shutil.copy(BOOTSTRAP, script_dir / "bootstrap.ps1")
    (script_dir / "daemon.py").write_text("print('stub daemon')\n", encoding="utf-8")
    (script_dir / "install_service.ps1").write_text(
        'Write-Output "Access is denied"\r\nexit 1\r\n',
        encoding="utf-8",
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uv.cmd").write_text(
        "@echo off\r\n"
        "echo %*>> \"%~dp0uv-calls.txt\"\r\n"
        "echo Python 3.12.0\r\n"
        "exit /b 0\r\n",
        encoding="utf-8",
    )
    local_app = tmp_path / "localapp"
    courier = local_app / "Courier"
    courier.mkdir(parents=True)
    (courier / "config.json").write_text(
        json.dumps({
            "COURIER_SERVER": "http://keep.invalid",
            "COURIER_WORKER_ID": "keep-worker",
            "COURIER_CONTROLLER_PORT": 8800,
        }),
        encoding="utf-8",
    )
    key = secrets.token_hex(16)
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["LOCALAPPDATA"] = str(local_app)
    env["COURIER_API_KEY"] = ""
    before = _scheduled_task_snapshot()
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_dir / "bootstrap.ps1"),
            "-ServerArg",
            "http://127.0.0.1:9",
            "-ApiKeyArg",
            key,
            "-HealthTimeoutSec",
            "1",
        ],
        cwd=script_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert key not in combined
    assert "[SUCCESS]" not in combined
    assert proc.returncode == 2, combined
    script_config = script_dir / "config.json"
    if script_config.exists():
        assert key not in script_config.read_text(encoding="utf-8")
    for path in script_dir.rglob("*"):
        if path.is_file():
            assert key.encode() not in path.read_bytes()
    saved = json.loads((courier / "config.json").read_text(encoding="utf-8-sig"))
    assert saved["COURIER_API_KEY"] == key
    assert saved["COURIER_SERVER"] == "http://127.0.0.1:9"
    assert saved["COURIER_WORKER_ID"] == "keep-worker"
    assert saved["COURIER_CONTROLLER_PORT"] == 8800
    calls = (bin_dir / "uv-calls.txt").read_text(encoding="utf-8", errors="replace")
    assert "daemon.py" in calls
    assert _scheduled_task_snapshot() == before
    lingering = _process_ids_containing(str(bin_dir))
    assert lingering == "", lingering


def _process_ids_containing(fragment: str) -> str:
    safe = fragment.replace("'", "''")
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like '*"
            + safe
            + "*' } | Select-Object -ExpandProperty ProcessId",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout.strip()


def _scheduled_task_snapshot() -> str:
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$t = Get-ScheduledTask -TaskName 'CourierWindowsWorker' -ErrorAction SilentlyContinue; "
            "if (-not $t) { 'absent' } else { $t.TaskPath + $t.TaskName }",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""
