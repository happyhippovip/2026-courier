import json
import os
import subprocess
import sys
import time

import psutil
import pytest

from courier_runtime.ownership import (
    CREATE_TIME_TOLERANCE_S,
    OwnedProcess,
    Registry,
    is_same_process,
    terminate_owned,
    main,
)

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]


@pytest.fixture
def spawn():
    procs = []

    def _spawn(argv):
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
        procs.append(proc)
        return proc

    yield _spawn
    for proc in procs:
        try:
            if psutil.pid_exists(proc.pid):
                p = psutil.Process(proc.pid)
                for child in p.children(recursive=True):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                p.kill()
        except psutil.NoSuchProcess:
            pass
        proc.wait(timeout=5)


def test_create_time_tolerance_boundary():
    # Synthetic process record with non-existent PID
    fake_rec = OwnedProcess(
        pid=999999999,
        create_time=time.time(),
        workkey="wk-fake",
        owner="test",
        recorded_at=time.time(),
    )
    assert is_same_process(fake_rec) is False


def test_capture_nonexistent_pid_raises():
    with pytest.raises(psutil.NoSuchProcess):
        OwnedProcess.capture(999999999, "wk-fake", "test")


def test_registry_empty_or_missing_file(tmp_path):
    registry = Registry(str(tmp_path / "nonexistent.json"))
    assert registry.load() == []
    assert registry.owned() == []
    assert registry.owned("wk-x") == []


def test_registry_deduplication(spawn, tmp_path):
    proc = spawn(SLEEPER)
    registry = Registry(str(tmp_path / "owned.json"))

    rec1 = OwnedProcess.capture(proc.pid, "wk-1", "owner-1")
    registry.add(rec1)
    assert len(registry.load()) == 1

    # Adding updated record for same (pid, create_time) replaces old entry
    rec2 = OwnedProcess(
        pid=rec1.pid,
        create_time=rec1.create_time,
        workkey="wk-2",
        owner="owner-2",
        recorded_at=time.time(),
    )
    registry.add(rec2)
    loaded = registry.load()
    assert len(loaded) == 1
    assert loaded[0].workkey == "wk-2"
    assert loaded[0].owner == "owner-2"


def test_registry_stop_all(spawn, tmp_path):
    p1 = spawn(SLEEPER)
    p2 = spawn(SLEEPER)
    registry = Registry(str(tmp_path / "owned.json"))

    registry.add(OwnedProcess.capture(p1.pid, "wk-alpha", "test"))
    registry.add(OwnedProcess.capture(p2.pid, "wk-beta", "test"))
    assert len(registry.owned()) == 2

    # Stop all without filtering by workkey
    receipts = registry.stop(workkey=None)
    assert len(receipts) == 2
    assert all(r["result"] == "STOPPED" for r in receipts)
    assert registry.owned() == []


def test_terminate_already_dead_process(spawn):
    proc = spawn(SLEEPER)
    rec = OwnedProcess.capture(proc.pid, "wk-dead", "test")
    proc.terminate()
    proc.wait(timeout=5)

    receipt = terminate_owned(rec)
    assert receipt["result"] == "NOT_RUNNING"
    assert receipt["action"] == "NONE"
    assert receipt["terminated"] == []
    assert receipt["still_alive"] == []


def test_cli_stop_no_matching_records(tmp_path, capsys):
    path = str(tmp_path / "owned.json")
    registry = Registry(path)
    assert main(["stop", "--registry", path, "--workkey", "wk-none"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
