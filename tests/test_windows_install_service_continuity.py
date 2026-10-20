"""The Windows worker task must survive long runs and crashes.

Task Scheduler defaults stop a task after 72 hours and never restart it after a
failure. install_service.ps1 therefore has to pass explicit settings. This is a
static contract check; it does not run PowerShell.
"""
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "windows_worker" / "install_service.ps1"


def _text():
    return SCRIPT.read_text(encoding="utf-8")


def test_task_is_registered_with_explicit_settings():
    text = _text()
    assert re.search(r"Register-ScheduledTask\b[^\n]*-Settings\s+\$settings", text)
    assert "New-ScheduledTaskSettingsSet" in text


def test_no_72_hour_execution_limit():
    assert re.search(r"-ExecutionTimeLimit\s+\(\[TimeSpan\]::Zero\)", _text())


def test_restarts_after_failure():
    text = _text()
    assert re.search(r"-RestartCount\s+\d+", text)
    assert re.search(r"-RestartInterval\s+\(New-TimeSpan\s+-Minutes\s+\d+\)", text)


def test_single_instance_only():
    assert re.search(r"-MultipleInstances\s+IgnoreNew", _text())
