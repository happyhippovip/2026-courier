import subprocess
import sys
import time
from dataclasses import replace

import psutil
import pytest

from courier_runtime.ownership import OwnedProcess, Registry, is_same_process, main, terminate_owned

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]
PARENT_WITH_CHILD = [sys.executable, "-c",
                     "import subprocess, sys, time;"
                     "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
                     "time.sleep(60)"]


@pytest.fixture
def spawn():
    procs = []

    def _spawn(argv):
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
        procs.append(proc)
        return proc

    yield _spawn
    for proc in procs:  # test cleanup: only processes this test started
        for child in psutil.Process(proc.pid).children(recursive=True) if psutil.pid_exists(proc.pid) else []:
            child.kill()
        proc.kill()
        proc.wait(timeout=10)


def test_owned_tree_is_stopped_and_receipted(spawn):
    parent = spawn(PARENT_WITH_CHILD)
    record = OwnedProcess.capture(parent.pid, "wk-1", "test")
    deadline = time.time() + 10
    while not psutil.Process(parent.pid).children() and time.time() < deadline:
        time.sleep(0.05)
    child_pid = psutil.Process(parent.pid).children()[0].pid

    receipt = terminate_owned(record, timeout=5)

    assert receipt["result"] == "STOPPED"
    assert {parent.pid, child_pid} <= set(receipt["terminated"])
    parent.wait(timeout=5)
    assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE


def test_unrelated_process_with_the_same_name_survives(spawn):
    mine = spawn(SLEEPER)
    foreign = spawn(SLEEPER)  # same executable and argv: a name-based kill would hit it
    receipt = terminate_owned(OwnedProcess.capture(mine.pid, "wk-1", "test"))
    assert receipt["result"] == "STOPPED"
    assert foreign.poll() is None, "a process Courier did not record must never be signalled"


def test_reused_pid_with_a_different_start_time_is_not_ours(spawn):
    proc = spawn(SLEEPER)
    stale = OwnedProcess(pid=proc.pid, create_time=psutil.Process(proc.pid).create_time() - 3600,
                         workkey="wk-1", owner="test", recorded_at=0.0)
    assert not is_same_process(stale)
    receipt = terminate_owned(stale)
    assert receipt["result"] == "NOT_RUNNING" and receipt["terminated"] == []
    assert proc.poll() is None


def test_dead_record_is_reported_not_signalled(spawn):
    proc = spawn(SLEEPER)
    record = OwnedProcess.capture(proc.pid, "wk-1", "test")
    proc.kill()
    proc.wait(timeout=5)
    assert terminate_owned(record)["result"] == "NOT_RUNNING"


def test_registry_stops_only_the_requested_workkey(spawn, tmp_path):
    registry = Registry(str(tmp_path / "owned.json"))
    a, b = spawn(SLEEPER), spawn(SLEEPER)
    registry.add(OwnedProcess.capture(a.pid, "wk-a", "test"))
    registry.add(OwnedProcess.capture(b.pid, "wk-b", "test"))

    receipts = registry.stop("wk-a")

    assert [r["workkey"] for r in receipts] == ["wk-a"]
    a.wait(timeout=5)
    assert b.poll() is None
    assert [r.workkey for r in registry.owned()] == ["wk-b"]


def test_cli_record_and_stop(spawn, tmp_path, capsys):
    path = str(tmp_path / "owned.json")
    proc = spawn(SLEEPER)
    assert main(["record", "--registry", path, "--pid", str(proc.pid), "--workkey", "wk-cli"]) == 0
    assert main(["stop", "--registry", path, "--workkey", "wk-cli"]) == 0
    assert '"STOPPED"' in capsys.readouterr().out
    proc.wait(timeout=5)
    assert main(["record", "--registry", path, "--pid", str(proc.pid), "--workkey", "wk-cli"]) == 1


@pytest.mark.parametrize("receipt", [
    {"result": "ORPHANS_REMAIN", "still_alive": [222]},
    {"result": "STOPPED", "still_alive": [222]},
    {"result": "IDENTITY_UNVERIFIED"},
    {"result": "UNKNOWN"},
])
def test_failed_cleanup_retains_durable_ownership(tmp_path, monkeypatch, receipt):
    from courier_runtime import ownership

    path = str(tmp_path / "owned.json")
    registry = Registry(path)
    failed = OwnedProcess(111, 1.0, "blocked", "test", 0.0)
    unrelated = OwnedProcess(333, 3.0, "other", "test", 0.0)
    registry.add(failed)
    registry.add(unrelated)
    monkeypatch.setattr(ownership, "terminate_owned", lambda *a, **kw: receipt)

    assert registry.stop("blocked") == [receipt]
    pending = replace(failed, cleanup_pending=True)
    assert Registry(path).owned() == [pending, unrelated]
    assert main(["stop", "--registry", path, "--workkey", "blocked"]) == 1
    assert Registry(path).owned() == [pending, unrelated]

    monkeypatch.setattr(ownership, "terminate_owned", lambda *a, **kw: {"result": "NOT_RUNNING"})
    assert registry.stop("blocked")[0]["result"] == "CLEANUP_UNVERIFIED"
    assert Registry(path).owned() == [pending, unrelated]

    monkeypatch.setattr(ownership, "terminate_owned", lambda *a, **kw: {"result": "STOPPED"})
    registry.stop("blocked")
    assert Registry(path).owned() == [unrelated]


def test_identity_access_denial_is_not_proof_of_exit(tmp_path, monkeypatch):
    from courier_runtime import ownership

    record = OwnedProcess(111, 1.0, "blocked", "test", 0.0)
    registry = Registry(str(tmp_path / "owned.json"))
    registry.add(record)

    def denied(pid):
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(ownership.psutil, "Process", denied)
    receipt = registry.stop("blocked")[0]
    assert receipt["result"] == "IDENTITY_UNVERIFIED"
    assert receipt["action"] == "NONE"
    assert Registry(registry.path).owned() == [replace(record, cleanup_pending=True)]


def test_cleanup_reuses_verified_identity_instead_of_reopening_pid(monkeypatch):
    from courier_runtime import ownership

    signalled, lookups = [], []

    class Process:
        pid = 111

        def __init__(self, name, created):
            self.name, self.created = name, created

        def status(self):
            return psutil.STATUS_RUNNING

        def create_time(self):
            return self.created

        def children(self, recursive):
            return []

        def terminate(self):
            signalled.append(self.name)

    owned, foreign = Process("owned", 1.0), Process("foreign", 2.0)

    def lookup(pid):
        lookups.append(pid)
        return owned if len(lookups) == 1 else foreign

    monkeypatch.setattr(ownership.psutil, "Process", lookup)
    monkeypatch.setattr(ownership.psutil, "wait_procs", lambda tree, **kw: (tree, []))
    assert terminate_owned(OwnedProcess(111, 1.0, "w", "test", 0.0))["result"] == "STOPPED"
    assert signalled == ["owned"]
    assert lookups == [111]
