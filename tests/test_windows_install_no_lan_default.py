"""The Windows installer must not invent a private LAN server or a 72-hour stop.

An empty prompt used to save http://192.168.178.162:8080. A missing server
URL or API key now stops the install. The scheduled task has no execution
time limit, restarts after a failure, and does not start a second copy.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLERS = (
    ROOT / "scripts" / "windows_worker" / "install.ps1",
    ROOT / "scripts" / "windows_worker" / "dist" / "install.ps1",
)
DAEMON = ROOT / "scripts" / "windows_worker" / "daemon.py"


def test_install_requires_a_server_and_a_key():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert "192.168.178.162" not in text
        assert "Pass -ServerArg." in text
        assert "Pass -ApiKeyArg." in text
        assert "exit 1" in text


def test_install_task_survives_and_restarts():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"-ExecutionTimeLimit\s+\(\[TimeSpan\]::Zero\)", text)
        assert re.search(r"-RestartCount\s+3", text)
        assert re.search(r"-RestartInterval\s+\(New-TimeSpan\s+-Minutes\s+1\)", text)
        assert re.search(r"-MultipleInstances\s+IgnoreNew", text)
        assert re.search(r"Register-ScheduledTask\b[^\n]*-Settings\s+\$settings", text)


def test_unattended_install_does_not_prompt():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert "IsInputRedirected" in text
        assert "at least 32 characters" in text
        prompt = text.index("function Test-CanPrompt")
        worker_prompt = text.index("Enter a unique Worker ID")
        assert prompt < worker_prompt
        assert "if (Test-CanPrompt)" in text[worker_prompt - 80:worker_prompt]


def test_install_task_runs_as_the_installing_user():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        assert 'UserId "SYSTEM"' not in text
        assert "ServiceAccount" not in text
        assert "installed successfully" not in text
        assert "must be run as Administrator." in text
        assert "-AtLogOn" in text
        assert "GetCurrent().Name" in text


def test_daemon_default_server_is_loopback():
    text = DAEMON.read_text(encoding="utf-8")
    assert 'DEFAULT_SERVER = "http://127.0.0.1:8080"' in text
    assert "192.168.178.162" not in text
