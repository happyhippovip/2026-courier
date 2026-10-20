"""Bootstrap must see the daemon start. An old log line and a missing toolchain are not health."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "windows_worker" / "bootstrap.ps1"
CONFIRM = ROOT / "scripts" / "windows_worker" / "confirm_daemon.ps1"


def test_bootstrap_does_not_treat_silence_as_health():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "uv is not installed" not in text
    assert "host.log" not in text
    assert "appears healthy" not in text
    assert "daemon.log" in text
    assert "confirm_daemon.ps1" in text
    assert "Courier did not start" in text
    assert "exit 1" in text
    assert "-ServerArg" in text
    assert "RunAs" not in text
    assert "Administrator" not in text
    assert "Starting Courier for this sign-in only." in text


def _pwsh():
    for candidate in ("/tmp/pwsh/pwsh", "pwsh", "powershell"):
        if candidate.startswith("/") and Path(candidate).is_file():
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    pytest.skip("powershell is not installed")


def _run(script):
    result = subprocess.run(
        [_pwsh(), "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in (0, 1), result.stderr
    return result.returncode


def test_new_started_line_counts(tmp_path):
    log = tmp_path / "daemon.log"
    log.write_text("Windows Worker HTTP Daemon started. PID=4\n", encoding="utf-8")
    code = _run(
        f". '{CONFIRM}'\n"
        f"$ok = Wait-CourierDaemon -LogFile '{log}' -LogStart 0 -TimeoutSeconds 2\n"
        "if (-not $ok) { exit 1 }\n"
    )
    assert code == 0


def test_old_started_line_does_not_count(tmp_path):
    log = tmp_path / "daemon.log"
    log.write_text("Windows Worker HTTP Daemon started. PID=4\n", encoding="utf-8")
    code = _run(
        f". '{CONFIRM}'\n"
        f"$ok = Wait-CourierDaemon -LogFile '{log}' -LogStart {log.stat().st_size} -TimeoutSeconds 1\n"
        "if ($ok) { exit 0 } else { exit 1 }\n"
    )
    assert code == 1


def test_fatal_line_is_not_a_start(tmp_path):
    log = tmp_path / "daemon.log"
    log.write_text("FATAL: COURIER_API_KEY is not set\n", encoding="utf-8")
    code = _run(
        f". '{CONFIRM}'\n"
        f"$ok = Wait-CourierDaemon -LogFile '{log}' -LogStart 0 -TimeoutSeconds 2\n"
        "if ($ok) { exit 0 } else { exit 1 }\n"
    )
    assert code == 1


def test_exited_process_is_not_a_start(tmp_path):
    py = shutil.which("python3") or shutil.which("python")
    if not py:
        pytest.skip("python is not installed")
    log = tmp_path / "daemon.log"
    code = _run(
        f". '{CONFIRM}'\n"
        f"$proc = Start-Process -FilePath '{py}' -ArgumentList '-c','raise SystemExit' -PassThru -Wait\n"
        f"$ok = Wait-CourierDaemon -LogFile '{log}' -LogStart 0 -Process $proc -TimeoutSeconds 3\n"
        "if ($ok) { exit 0 } else { exit 1 }\n"
    )
    assert code == 1
