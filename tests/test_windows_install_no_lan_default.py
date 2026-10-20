"""The Windows installer must not invent a private LAN server or a 72-hour stop.

An empty prompt used to save http://192.168.178.162:8080. A missing server
URL or API key now stops the install. The scheduled task has no execution
time limit, restarts after a failure, and does not start a second copy.
"""
import re
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

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
        assert "must be run as Administrator." not in text
        assert 'Join-Path $env:LOCALAPPDATA "Courier\\app"' in text
        assert "$env:ProgramFiles" not in text
        assert "-AtLogOn" in text
        assert "GetCurrent().Name" in text


def test_install_does_not_call_a_queued_task_ready():
    for path in INSTALLERS:
        text = path.read_text(encoding="utf-8")
        health = text.index("Test-CourierInstallHealth -Token $ApiKey")
        claimed = text.index("Courier installed and started for $userId.")
        assert health < claimed
        assert "http://127.0.0.1:" in text
        assert "it is not ready yet" in text
        assert "The token was removed." in text
        assert "$Server" not in text[text.index("function Test-CourierInstallHealth"):text.index("# end Test-CourierInstallHealth")]


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok = self.headers.get("X-Courier-Token") == "install-health-token"
        self.send_response(200 if ok else 401)
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def _pwsh():
    for candidate in ("/tmp/pwsh/pwsh", "pwsh", "powershell"):
        if candidate.startswith("/") and Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    pytest.skip("powershell is not installed")


def test_install_health_accepts_only_the_local_token():
    text = INSTALLERS[0].read_text(encoding="utf-8")
    function = text[text.index("function Test-CourierInstallHealth"):text.index("# end Test-CourierInstallHealth")]
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        ready = subprocess.run(
            [_pwsh(), "-NoProfile", "-Command",
             function + "\n"
             f"$ok = Test-CourierInstallHealth -Token 'install-health-token' -Port {port} -TimeoutSeconds 4\n"
             "if (-not $ok) { exit 1 }\n"],
            capture_output=True, text=True, check=False,
        )
        assert ready.returncode == 0, ready.stderr
        refused = subprocess.run(
            [_pwsh(), "-NoProfile", "-Command",
             function + "\n"
             f"$ok = Test-CourierInstallHealth -Token 'wrong-token' -Port {port} -TimeoutSeconds 2\n"
             "if ($ok) { exit 0 } else { exit 1 }\n"],
            capture_output=True, text=True, check=False,
        )
        assert refused.returncode == 1, refused.stderr
    finally:
        server.shutdown()
        server.server_close()


def test_daemon_default_server_is_loopback():
    text = DAEMON.read_text(encoding="utf-8")
    assert 'DEFAULT_SERVER = "http://127.0.0.1:8080"' in text
    assert "192.168.178.162" not in text
