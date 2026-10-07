"""run_native timeout + interruption reap (M2 mac reliability lane).

Proves: a hung native child is group-killed on timeout (FAILED/TIMEOUT, no
surviving process) instead of blocking the daemon forever; a daemon
interruption (WorkerShutdown, a BaseException) during execution still reaps
the child and propagates; fast echo/git_status behavior is unchanged.
"""
import importlib.util
import subprocess
import time
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mac_worker" / "daemon.py"


def load_daemon(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("mac_worker_daemon_native_reap", DAEMON_PATH)
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    (tmp_path / "state").mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(daemon, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(daemon, "LOGS_DIR", tmp_path / "logs")
    return daemon


def stray_sleep(seconds):
    """PIDs of system-wide `sleep <seconds>` processes (distinctive duration)."""
    try:
        out = subprocess.check_output(["pgrep", "-f", f"^sleep {seconds}$"], text=True)
    except subprocess.CalledProcessError:
        return set()
    return {int(p) for p in out.split()}


def hang_sleep_63_instead(daemon, monkeypatch):
    """Echo no longer spawns a shell, so task text cannot hang a child. Tests
    needing a hung native child simulate one here: the timeout machinery, not
    task text, is what they exercise."""
    real_popen = daemon.subprocess.Popen

    def hang_instead(*args, **kwargs):
        assert kwargs.get("shell") in (None, False)  # no shell anywhere
        if not kwargs.get("start_new_session"):
            # ps probes (process_identity) and friends run untouched: only the
            # daemon's session-leader child spawn becomes the hung sleep.
            return real_popen(*args, **kwargs)
        return real_popen(["sleep", "63"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=True)

    monkeypatch.setattr(daemon.subprocess, "Popen", hang_instead)


def test_native_timeout_kills_group_and_reaps(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    assert stray_sleep(63) == set()  # distinctive duration: no foreign process
    hang_sleep_63_instead(daemon, monkeypatch)
    task = {"task_id": "task-native-1", "action": "echo", "instruction": "echo go"}
    started = time.monotonic()
    result = daemon.run_native(task, {"NATIVE_TIMEOUT_SECONDS": 2})
    elapsed = time.monotonic() - started
    assert result["status"] == "FAILED"
    assert result["reason"] == "TIMEOUT"
    assert result["execution_mode"] == "NATIVE"
    assert "TIMEOUT" in result["stderr"]
    assert elapsed < 30  # timeout + grace, not the 63s sleep
    assert stray_sleep(63) == set()  # group incl. shell grandchild dead


def test_native_fast_paths_unaffected(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    echo = daemon.run_native({"task_id": "t-e", "action": "echo", "instruction": "echo hi"},
                             {"WORKER_ID": "MAC-01"})
    assert echo["status"] == "SUCCESS"
    assert echo["stdout"] == "hi\n"
    assert echo["exit_code"] == 0
    assert echo["execution_mode"] == "NATIVE"
    assert "reason" not in echo
    git = daemon.run_native({"task_id": "t-g", "action": "git_status", "instruction": ""},
                            {"WORKER_ID": "MAC-01"})
    assert git["execution_mode"] == "NATIVE"
    assert git["exit_code"] == 0
    assert git["status"] == "SUCCESS"


def test_native_interruption_reaps_and_propagates(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    real_popen = subprocess.Popen
    instances = []

    class RaiseOnce(real_popen):
        def __init__(self, *args, **kwargs):
            assert kwargs.get("shell") in (None, False)  # no shell anywhere
            if kwargs.get("start_new_session"):
                # A hung child without shell semantics: the interruption path,
                # not task text, is what this test exercises.
                super().__init__(["sleep", "64"], stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True,
                                 start_new_session=True)
                instances.append(self)
                self._is_target = True
            else:
                # ps probes (process_identity) and friends run untouched.
                super().__init__(*args, **kwargs)
                self._is_target = False

        def communicate(self, *args, **kwargs):
            if self._is_target:
                raise daemon.WorkerShutdown("SIGTERM during native exec")
            return super().communicate(*args, **kwargs)

    orig_popen = daemon.subprocess.Popen
    monkeypatch.setattr(daemon.subprocess, "Popen", RaiseOnce)
    try:
        with pytest.raises(daemon.WorkerShutdown):
            daemon.run_native({"task_id": "t-i", "action": "echo",
                               "instruction": "echo go"},
                              {"WORKER_ID": "MAC-01"})
    finally:
        monkeypatch.setattr(daemon.subprocess, "Popen", orig_popen)
    assert len(instances) == 1
    assert instances[0].poll() is not None  # reaped by finally: no zombie/orphan
    assert stray_sleep(64) == set()


def test_native_echo_has_no_shell(tmp_path, monkeypatch):
    """Separators, substitutions and redirects in echo text are literal output,
    never worker shell: chained commands must not execute while SUCCESS is
    reported (shell-escape fix)."""
    daemon = load_daemon(tmp_path, monkeypatch)
    spawns = []
    real_popen = daemon.subprocess.Popen

    def recording(*args, **kwargs):
        spawns.append((args, kwargs))
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(daemon.subprocess, "Popen", recording)
    marker = tmp_path / "pwned"
    marker2 = tmp_path / "pwned2"
    result = daemon.run_native({"task_id": "t-x", "action": "echo",
                                "instruction": "echo hi; touch %s" % marker},
                               {"WORKER_ID": "MAC-01"})
    assert result["status"] == "SUCCESS"
    assert result["stdout"] == "hi; touch %s\n" % marker
    assert not marker.exists()
    chained = daemon.run_native({"task_id": "t-y", "action": "echo",
                                 "instruction": "echo $(touch %s) `touch %s`" % (marker, marker2)},
                                {"WORKER_ID": "MAC-01"})
    assert chained["status"] == "SUCCESS"
    assert not marker.exists() and not marker2.exists()
    assert spawns and all(not kw.get("shell") for _, kw in spawns)


def test_native_echo_redirect_writes_declared_canary(tmp_path, monkeypatch):
    """The canary contract without a shell: `text > name` creates the file
    only when `name` is task-declared evidence and path-safe (physical gate)."""
    daemon = load_daemon(tmp_path, monkeypatch)
    work = tmp_path / "work"
    task = {"task_id": "process_a", "action": "echo",
            "instruction": "echo A > courier_canary_process_a.txt",
            "artifacts": ["courier_canary_process_a.txt"],
            "workspace": str(work)}
    result = daemon.run_native(task, {"WORKER_ID": "MAC-01"})
    assert result["status"] == "SUCCESS"
    assert (work / "courier_canary_process_a.txt").read_text() == "A "


def test_native_echo_redirect_refuses_undeclared_or_unsafe(tmp_path, monkeypatch):
    daemon = load_daemon(tmp_path, monkeypatch)
    work = tmp_path / "work"
    base = {"task_id": "t-r", "action": "echo", "workspace": str(work),
            "artifacts": ["courier_canary_t-r.txt"]}
    outside = tmp_path / "escape.txt"
    for instruction, forbidden in (
            ("echo hi > other.txt", work / "other.txt"),
            ("echo x > ../escape.txt", outside),
            ("echo a > b > courier_canary_t-r.txt", work / "courier_canary_t-r.txt")):
        result = daemon.run_native(dict(base, instruction=instruction),
                                   {"WORKER_ID": "MAC-01"})
        assert result["status"] == "SUCCESS"  # literal output, never a write
        assert not forbidden.exists()
