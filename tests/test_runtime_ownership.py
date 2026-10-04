import subprocess
import sys
import time

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
