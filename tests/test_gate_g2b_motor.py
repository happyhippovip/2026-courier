"""Rest points of Gate G2 that #609 did not evidence."""

import pytest

from courier_runtime.lease import StaleLease
from tests.test_gate_g2_motor import _task, _world


def test_expired_lease_reconciles_unknown_and_lets_the_waiter_in(tmp_path):
    tasks = {
        "Z": _task("Z", "RUNNING", "src/z/", "gamma"),
        "A": _task("A", "READY", "src/shared/", "alpha"),
        "C": _task("C", "READY", "src/shared/", "beta"),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": "up", "beta": "up", "gamma": "up"},
    )
    try:
        first = advance(
            {"result_id": "r1", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock, ttl_s=30,
        )
        assert first["dispatched"] == ["A"]
        token = leases.current("src/shared/").token
        clock.t += 31
        second = advance(
            {"result_id": "r2", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock, ttl_s=30,
        )
        assert tasks["A"]["status"] == "RECONCILED"
        assert tasks["A"]["execution"] == "UNKNOWN"
        assert "A" not in second["dispatched"]
        with pytest.raises(StaleLease):
            leases.check_write("src/shared/", token)
        assert second["dispatched"] == ["C"]
    finally:
        leases.close()


def test_restart_does_not_dispatch_the_same_attempt_again(tmp_path):
    tasks = {
        "Z": _task("Z", "RUNNING", "src/z/", "gamma"),
        "B": _task("B", "READY", "src/b/", "beta"),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"beta": "up", "gamma": "up"},
    )
    try:
        first = advance(
            {"result_id": "r1", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert first["dispatched"] == ["B"]
        tasks["B"]["status"] = "READY"
        tasks["B"].pop("token", None)
        tasks["B"].pop("open_attempt", None)
        second = advance(
            {"result_id": "r2", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert "B" not in second["dispatched"]
        assert tasks["B"]["status"] == "RECONCILED"
    finally:
        leases.close()


def test_backpressure_stops_dispatch_past_the_cap(tmp_path):
    tasks = {"Z": _task("Z", "RUNNING", "src/z/", "gamma")}
    for name in ("T0", "T1", "T2", "T3"):
        tasks[name] = _task(name, "READY", "src/" + name + "/", "beta")
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"beta": "up", "gamma": "up"},
    )
    try:
        out = advance(
            {"result_id": "r1", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock, max_dispatch=2,
        )
        assert out["dispatched"] == ["T0", "T1"]
        assert [item["id"] for item in out["waiting"] if item["reason"] == "BACKPRESSURE"] == ["T2", "T3"]
        assert tasks["T2"]["status"] == "READY"
    finally:
        leases.close()


def test_provider_retries_stop_at_the_bound(tmp_path):
    calls = []

    def alpha():
        calls.append("alpha")
        raise RuntimeError("alpha down")

    tasks = {
        "Z": _task("Z", "RUNNING", "src/z/", "gamma"),
        "A": _task("A", "READY", "src/a/", "alpha"),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": alpha, "gamma": "up"},
    )
    try:
        last = None
        for n in range(4):
            last = advance(
                {"result_id": "r" + str(n), "task_id": "Z", "status": "PASS"},
                tasks, journal, leases, providers, clock, max_retries=3,
            )
        assert len(calls) == 3
        assert {"id": "A", "reason": "RETRIES_EXHAUSTED"} in last["waiting"]
        assert tasks["A"]["status"] == "READY"
    finally:
        leases.close()


def test_windows_wakeup_does_not_use_inotify(monkeypatch):
    import courier_runtime.host_loop as host_loop

    monkeypatch.setattr(host_loop.sys, "platform", "win32")
    assert host_loop.wakeup_backend() == "read_directory_changes"
    used = []
    monkeypatch.setattr(host_loop, "_wait_inotify", lambda path: used.append(("inotify", path)))
    monkeypatch.setattr(host_loop, "_wait_windows", lambda path: used.append(("windows", path)))
    host_loop.wait_for_wakeup(r"C:\signals\provider.signals")
    assert used == [("windows", r"C:\signals\provider.signals")]


class _Kernel:
    def __init__(self):
        self.reads = 0
        self.closed = 0

    def CreateFileW(self, *args):
        return 1

    def ReadDirectoryChangesW(self, *args):
        self.reads += 1
        return 1

    def CloseHandle(self, handle):
        self.closed += 1
        return 1


def test_windows_wait_reads_directory_changes_once():
    import courier_runtime.host_loop as host_loop

    kernel = _Kernel()
    host_loop._wait_windows(r"C:\signals\provider.signals", kernel32=kernel)
    assert kernel.reads == 1
    assert kernel.closed == 1


def test_linux_wakeup_stays_on_inotify():
    import courier_runtime.host_loop as host_loop

    assert host_loop.wakeup_backend("linux") == "inotify"
