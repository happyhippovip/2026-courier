"""stop_daemon.sh must not report a live process as stopped.

A pid file is not permission to signal. The recorded start time has to
match the live process. A failed or skipped signal stays unproven.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "scripts" / "stop_daemon.sh"
START = ROOT / "scripts" / "start_daemon.sh"


def lstart(pid):
    text = subprocess.check_output(["ps", "-p", str(pid), "-o", "lstart="], text=True)
    return " ".join(text.split())


def run_stop(tmp):
    return subprocess.run(["bash", str(STOP)], cwd=tmp, text=True, capture_output=True)


def test_live_pid_without_identity_is_not_stopped(tmp_path):
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "courier_daemon.pid").write_text(f"{proc.pid}\n")
        result = run_stop(tmp_path)
        assert proc.poll() is None
        assert result.returncode != 0
        assert "Courier Server stopped." not in result.stdout
        assert (logs / "courier_daemon.pid").read_text() == f"{proc.pid}\n"
    finally:
        if proc.poll() is None:
            os.kill(proc.pid, 9)
        proc.wait(timeout=5)


def test_mismatched_identity_is_not_signaled(tmp_path):
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "courier_daemon.pid").write_text(f"{proc.pid}\tThu Jan  1 00:00:00 1970\n")
        result = run_stop(tmp_path)
        assert proc.poll() is None
        assert result.returncode != 0
        assert "Courier Server stopped." not in result.stdout
    finally:
        if proc.poll() is None:
            os.kill(proc.pid, 9)
        proc.wait(timeout=5)


def test_matching_identity_stops_that_process(tmp_path):
    proc = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "courier_daemon.pid").write_text(f"{proc.pid}\t{lstart(proc.pid)}\n")
        result = run_stop(tmp_path)
        proc.wait(timeout=5)
        assert result.returncode == 0
        assert "Courier Server stopped." in result.stdout
        assert not (logs / "courier_daemon.pid").exists()
    finally:
        if proc.poll() is None:
            os.kill(proc.pid, 9)
            proc.wait(timeout=5)


def test_ignored_signal_stays_unproven(tmp_path):
    ready = tmp_path / "ready"
    script = tmp_path / "ignore_term.py"
    script.write_text(
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"open({str(ready)!r}, 'w').write('ready')\n"
        "while True:\n"
        "    time.sleep(0.2)\n"
    )
    proc = subprocess.Popen([sys.executable, str(script)], start_new_session=True)
    try:
        for _ in range(50):
            if ready.exists():
                break
            if proc.poll() is not None:
                break
            time.sleep(0.02)
        assert ready.exists()
        logs = tmp_path / "logs"
        logs.mkdir()
        (logs / "courier_daemon.pid").write_text(f"{proc.pid}\t{lstart(proc.pid)}\n")
        result = run_stop(tmp_path)
        assert proc.poll() is None
        assert result.returncode != 0
        assert "Courier Server stopped." not in result.stdout
        assert "not proven" in result.stderr
    finally:
        if proc.poll() is None:
            os.kill(proc.pid, 9)
        proc.wait(timeout=5)


def test_dead_pid_is_not_reported_as_a_live_stop(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "courier_daemon.pid").write_text("999999\n")
    result = run_stop(tmp_path)
    assert result.returncode == 0
    assert "Courier Server stopped." not in result.stdout
    assert "not running" in result.stdout
    assert not (logs / "courier_daemon.pid").exists()


def test_start_records_identity_and_stop_uses_it(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "python3"
    fake.write_text("#!/bin/sh\nexec sleep 30\n")
    fake.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["COURIER_API_KEY"] = "worker-key"
    env["COURIER_VERIFIER_API_KEY"] = "verifier-key"
    started = subprocess.run(["bash", str(START)], cwd=tmp_path, text=True, capture_output=True, env=env)
    pids = []
    for path in (tmp_path / "logs").glob("*.pid"):
        token = path.read_text().split("\t", 1)[0].strip()
        if token.isdigit():
            pids.append(int(token))
    try:
        assert started.returncode == 0, started.stderr
        for name in (
            "courier_daemon.pid",
            "courier_verifier.pid",
            "courier_github_dispatcher.pid",
            "courier_watchdog.pid",
        ):
            line = (tmp_path / "logs" / name).read_text().rstrip("\n")
            pid_text, ident = line.split("\t", 1)
            pid = int(pid_text)
            pids.append(pid)
            assert ident == lstart(pid)
            os.kill(pid, 0)
        stopped = run_stop(tmp_path)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        assert "Courier Server stopped." in stopped.stdout
        for pid in pids:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            raise AssertionError(f"pid {pid} still alive")
    finally:
        for pid in pids:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
