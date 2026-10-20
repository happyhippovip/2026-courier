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


def test_registration_is_checked_before_it_is_announced():
    text = _text()
    still_there = text.index("the previous scheduled task is still present")
    missing = text.index("the scheduled task could not be registered")
    announced = text.index("scheduled task registered for $userId at logon.")
    assert still_there < missing < announced
    assert "$registeredTask.Principal.UserId -ne $userId" in text
    assert "exit 1" in text[still_there:announced]


def test_task_runs_as_the_installing_user_at_logon():
    text = _text()
    assert 'UserId "SYSTEM"' not in text
    assert "ServiceAccount" not in text
    assert "-AtLogOn" in text
    assert "GetCurrent().Name" in text
