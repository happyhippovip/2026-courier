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


def test_daemon_default_server_is_loopback():
    text = DAEMON.read_text(encoding="utf-8")
    assert 'DEFAULT_SERVER = "http://127.0.0.1:8080"' in text
    assert "192.168.178.162" not in text
