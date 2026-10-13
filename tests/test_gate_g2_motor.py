"""Gate G2 motor: one path, idle without polling, isolated providers, one writer."""

import pytest

from courier_runtime.host_loop import main
from courier_runtime.lease import LeaseStore


PATH = (
    "persist",
    "validate",
    "contract",
    "reconcile",
    "dependencies",
    "ready",
    "eligibility",
    "select",
    "dispatch",
)


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _task(task_id, status, scope, provider, depends=None):
    return {
        "id": task_id,
        "status": status,
        "scope": scope,
        "provider": provider,
        "holder": "holder-" + task_id,
        "depends_on": depends or [],
        "contract": {"requires": "PASS"},
    }


def _world(tmp_path, tasks, providers):
    from courier_runtime.motor import advance

    clock = Clock()
    leases = LeaseStore(str(tmp_path / "lease.db"), clock=clock)
    return advance, clock, leases, tasks, providers, []


def test_idle_motor_blocks_on_wakeup_and_does_not_sleep(monkeypatch, tmp_path):
    slept = []
    woke = []

    def sleep(seconds):
        slept.append(seconds)
        raise SystemExit(7)

    def wake(path):
        woke.append(str(path))
        raise SystemExit(0)

    monkeypatch.setattr("courier_runtime.host_loop.time.sleep", sleep)
    monkeypatch.setattr("courier_runtime.host_loop.wait_for_wakeup", wake, raising=False)
    signals = tmp_path / "provider.signals"
    with pytest.raises(SystemExit) as caught:
        main([
            "--state", str(tmp_path / "kirby.json"),
            "--slot", "s1",
            "--signals", str(signals),
            "--interval", "0.01",
        ])
    assert caught.value.code == 0
    assert slept == []
    assert woke == [str(signals)]


def test_result_walks_every_step_and_dispatches_the_successor(tmp_path):
    tasks = {
        "A": _task("A", "RUNNING", "src/a/", "alpha"),
        "B": _task("B", "BLOCKED", "src/b/", "beta", depends=["A"]),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": "up", "beta": "up"},
    )
    try:
        out = advance(
            {"result_id": "r1", "task_id": "A", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert out["steps"] == list(PATH)
        assert journal == [{"result_id": "r1", "task_id": "A", "status": "PASS"}]
        assert tasks["A"]["status"] == "DONE"
        assert tasks["B"]["status"] == "RUNNING"
        assert out["dispatched"] == ["B"]
        assert out["waiting"] == []
        refused = advance(
            {"task_id": "A", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert refused["steps"] == ["persist", "validate"]
        assert refused["dispatched"] == []
        assert len(journal) == 2
    finally:
        leases.close()


def test_contract_mismatch_does_not_dispatch(tmp_path):
    tasks = {
        "A": _task("A", "RUNNING", "src/a/", "alpha"),
        "B": _task("B", "BLOCKED", "src/b/", "beta", depends=["A"]),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": "up", "beta": "up"},
    )
    try:
        out = advance(
            {"result_id": "r-fail", "task_id": "A", "status": "FAIL"},
            tasks, journal, leases, providers, clock,
        )
        assert out["steps"] == ["persist", "validate", "contract"]
        assert out["dispatched"] == []
        assert tasks["A"]["status"] == "RUNNING"
        assert tasks["B"]["status"] == "BLOCKED"
    finally:
        leases.close()


def test_one_provider_down_still_dispatches_the_other(tmp_path):
    def alpha():
        raise RuntimeError("alpha down")

    seen = []

    def beta():
        seen.append("beta")

    tasks = {
        "Z": _task("Z", "RUNNING", "src/z/", "gamma"),
        "A": _task("A", "READY", "src/a/", "alpha"),
        "B": _task("B", "READY", "src/b/", "beta"),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": alpha, "beta": beta, "gamma": "up"},
    )
    try:
        out = advance(
            {"result_id": "r1", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert out["dispatched"] == ["B"]
        assert {"id": "A", "reason": "PROVIDER_DOWN"} in out["waiting"]
        assert tasks["B"]["status"] == "RUNNING"
        assert tasks["A"]["status"] == "READY"
        assert seen == ["beta"]
        assert leases.current("src/a/") is None
    finally:
        leases.close()


def test_exactly_one_writer_per_scope(tmp_path):
    tasks = {
        "Z": _task("Z", "RUNNING", "src/z/", "gamma"),
        "A": _task("A", "READY", "src/shared/", "alpha"),
        "C": _task("C", "READY", "src/shared/", "beta"),
        "B": _task("B", "READY", "src/other/", "beta"),
    }
    advance, clock, leases, tasks, providers, journal = _world(
        tmp_path, tasks, {"alpha": "up", "beta": "up", "gamma": "up"},
    )
    try:
        out = advance(
            {"result_id": "r1", "task_id": "Z", "status": "PASS"},
            tasks, journal, leases, providers, clock,
        )
        assert out["dispatched"] == ["A", "B"]
        assert {"id": "C", "reason": "SCOPE_HELD"} in out["waiting"]
        assert tasks["C"]["status"] == "READY"
        held = leases.current("src/shared/")
        assert held is not None and held.holder == "holder-A"
        assert leases.current("src/other/").holder == "holder-B"
    finally:
        leases.close()


def test_signal_growth_wakes_the_idle_wait(tmp_path):
    import threading
    import time

    from courier_runtime.host_loop import wait_for_wakeup

    path = tmp_path / "signals" / "provider.signals"
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")

    def writer():
        time.sleep(0.1)
        path.write_text("IDLE\n", encoding="utf-8")

    threading.Thread(target=writer, daemon=True).start()
    wait_for_wakeup(str(path))
    assert path.read_text(encoding="utf-8") == "IDLE\n"


def test_idle_waits_once_and_does_not_sleep(monkeypatch):
    import courier_runtime.motor as motor

    slept = []
    monkeypatch.setattr(motor.time, "sleep", lambda seconds: slept.append(seconds))
    calls = []

    def wait():
        calls.append("wait")
        if len(calls) > 1:
            raise AssertionError("busy loop")

    assert motor.idle(wait) == {"state": "IDLE", "created": []}
    assert calls == ["wait"]
    assert slept == []
