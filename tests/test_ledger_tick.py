"""Unit tests for the worker idle tick that runs one ledger bridge pass.

No network and no real bridge: the runner and clock are fakes.
"""

import os
import subprocess
import sys
import threading

import pytest

from courier_worker import ledger_tick, service
from courier_worker.ledger_tick import LedgerTick


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class FakeRunner:
    def __init__(self, codes):
        self.codes = list(codes)
        self.calls = []

    def __call__(self, argv, cwd, env, timeout_s):
        self.calls.append((argv, cwd, env, timeout_s))
        code = self.codes.pop(0) if self.codes else 0
        if isinstance(code, BaseException):
            raise code
        return ledger_tick.Completed(code)


_HOME = {}


@pytest.fixture(autouse=True)
def _home(tmp_path):
    _HOME["path"] = str(tmp_path / "home")
    yield
    _HOME.clear()


def _tick(runner, clock=None, probe=None, logs=None, **kw):
    return LedgerTick(_HOME["path"], "http://127.0.0.1:9", "GOOGLE_WINDOWS", "WINDOWS_REMOTE",
                      min_interval_s=kw.pop("min_interval_s", 5.0), timeout_s=kw.pop("timeout_s", 7.0),
                      pressure_probe=probe, runner=runner, clock=clock or FakeClock(),
                      log=(logs.append if logs is not None else (lambda _l: None)), **kw)


def test_argv_is_the_one_shot_bridge_with_explicit_ids():
    runner = FakeRunner([0])
    tick = _tick(runner)
    assert tick() == ledger_tick.RAN
    argv, cwd, env, timeout_s = runner.calls[0]
    assert argv[:3] == [sys.executable, "-m", "scripts.ledger_v1_bridge"]
    assert argv[3:] == ["--home", _HOME["path"], "--agent-id", "GOOGLE_WINDOWS", "--host-id", "WINDOWS_REMOTE",
                        "--controller", "http://127.0.0.1:9"]
    assert cwd == str(ledger_tick.REPO_ROOT)
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(ledger_tick.REPO_ROOT)
    assert timeout_s == 7.0
    assert not any("token" in part.lower() for part in argv)


def test_rate_limited_to_one_pass_per_interval():
    clock = FakeClock()
    runner = FakeRunner([0, 0, 0])
    tick = _tick(runner, clock=clock, min_interval_s=5.0)
    assert tick() == ledger_tick.RAN
    clock.now += 4.9
    assert tick() == ledger_tick.SKIPPED_INTERVAL
    clock.now += 0.1
    assert tick() == ledger_tick.RAN
    assert len(runner.calls) == 2


def test_retry_exit_runs_again_on_a_later_tick():
    clock = FakeClock()
    runner = FakeRunner([75, 0])
    tick = _tick(runner, clock=clock)
    assert tick() == ledger_tick.RETRY
    assert not tick.parked
    clock.now += 5.0
    assert tick() == ledger_tick.RAN
    assert len(runner.calls) == 2


@pytest.mark.parametrize("code", [2, 1, 3, -9])
def test_config_or_unknown_exit_parks_for_the_process_lifetime(code):
    clock = FakeClock()
    runner = FakeRunner([code, 0])
    logs = []
    tick = _tick(runner, clock=clock, logs=logs)
    assert tick() == ledger_tick.PARKED
    assert tick.parked
    for _ in range(3):
        clock.now += 1000
        assert tick() == ledger_tick.SKIPPED_PARKED
    assert len(runner.calls) == 1
    assert logs and "parked" in logs[0]


def test_timeout_is_retried_not_parked():
    clock = FakeClock()
    runner = FakeRunner([subprocess.TimeoutExpired("bridge", 7.0), 0])
    tick = _tick(runner, clock=clock)
    assert tick() == ledger_tick.TIMED_OUT
    assert not tick.parked
    clock.now += 5.0
    assert tick() == ledger_tick.RAN


def test_launch_error_parks():
    runner = FakeRunner([OSError("no python")])
    tick = _tick(runner)
    assert tick() == ledger_tick.PARKED
    assert tick.parked_reason.startswith("launch-failed")


def test_host_pressure_skips_without_consuming_the_interval():
    clock = FakeClock()
    pressure = ["swap low"]
    runner = FakeRunner([0])
    tick = _tick(runner, clock=clock, probe=lambda: pressure[0])
    assert tick() == ledger_tick.SKIPPED_PRESSURE
    assert runner.calls == []
    pressure[0] = None
    assert tick() == ledger_tick.RAN


def test_missing_bridge_script_parks(tmp_path):
    runner = FakeRunner([0])
    tick = _tick(runner, repo_root=tmp_path)
    assert tick() == ledger_tick.PARKED
    assert tick.parked_reason == "bridge-missing"
    assert runner.calls == []


@pytest.mark.parametrize("kw", [{"min_interval_s": 0.0}, {"min_interval_s": 4000}, {"timeout_s": 0.5},
                                {"timeout_s": 601}])
def test_bounds_are_enforced(kw):
    with pytest.raises(ValueError):
        _tick(FakeRunner([]), **kw)


def test_ids_are_required():
    with pytest.raises(ValueError):
        LedgerTick("/h", "http://127.0.0.1:9", "", "WINDOWS_REMOTE")


def test_real_runner_kills_a_pass_that_exceeds_its_timeout(tmp_path):
    import os
    argv = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(subprocess.TimeoutExpired):
        ledger_tick._run_bridge(argv, str(tmp_path), dict(os.environ), 0.5)


def test_real_runner_returns_the_exit_code(tmp_path):
    import os
    done = ledger_tick._run_bridge([sys.executable, "-c", "import sys; sys.exit(75)"], str(tmp_path),
                                   dict(os.environ), 20)
    assert done.returncode == 75


# -- worker loop wiring ------------------------------------------------------------

class _LoopHarness(service.WorkerLoop):
    """WorkerLoop.run without a controller: iterate() follows a script."""

    def __init__(self, actions, stop, **kw):
        super().__init__("/unused", "http://127.0.0.1:9", "w", 0.2, **kw)
        self.actions = list(actions)
        self.stop = stop

    def iterate(self, stop):
        if not self.actions:
            self.stop.set()
            return "delivered"
        return self.actions.pop(0)


def _run_loop(monkeypatch, loop):
    monkeypatch.setattr(service, "acquire_home_lock", lambda _home: None)
    monkeypatch.setattr(service, "release_home_lock", lambda _fd: None)
    monkeypatch.setattr(service, "run_orphan_gate", lambda _home: None)
    monkeypatch.setattr(service, "outbox_read_all", lambda _home: [])

    class _Client:
        def health(self):
            return True

        def deliver(self, _p):
            pass

    monkeypatch.setattr(loop, "_default_client", lambda: _Client())
    monkeypatch.setattr(loop.stop, "wait", lambda _s=None: loop.stop.is_set())
    return loop.run(loop.stop)


def test_hook_runs_only_on_idle_ticks(monkeypatch):
    calls = []
    stop = threading.Event()
    loop = _LoopHarness(["idle", "delivered", "idle", "spec-rejected", "idle"], stop,
                        idle_hook=lambda: calls.append(1))
    assert _run_loop(monkeypatch, loop) == 0
    assert len(calls) == 3


def test_hook_failure_never_stops_the_worker(monkeypatch, capsys):
    stop = threading.Event()

    def boom():
        raise RuntimeError("secret detail")

    loop = _LoopHarness(["idle", "idle", "idle"], stop, idle_hook=boom)
    assert _run_loop(monkeypatch, loop) == 0
    err = capsys.readouterr().err
    assert err.count("idle hook failed: RuntimeError") == 3
    assert "secret detail" not in err


def test_no_hook_by_default(monkeypatch):
    stop = threading.Event()
    loop = _LoopHarness(["idle", "idle"], stop)
    assert loop._idle_hook is None
    assert _run_loop(monkeypatch, loop) == 0


# -- CLI flags -----------------------------------------------------------------------

def _capture_loop(monkeypatch):
    seen = {}

    def fake_run(self, stop=None):
        seen["hook"] = self._idle_hook
        return 0

    monkeypatch.setattr(service.WorkerLoop, "run", fake_run)
    return seen


def test_cli_default_is_off(monkeypatch):
    seen = _capture_loop(monkeypatch)
    assert service.main(["--home", "/h", "--controller", "http://127.0.0.1:9"]) == 0
    assert seen["hook"] is None


def test_cli_both_ids_enable_the_tick(monkeypatch):
    seen = _capture_loop(monkeypatch)
    assert service.main(["--home", "/h", "--controller", "http://127.0.0.1:9",
                         "--ledger-agent-id", "GOOGLE_WINDOWS", "--ledger-host-id", "WINDOWS_REMOTE",
                         "--ledger-tick-interval", "1.5", "--ledger-tick-timeout", "20"]) == 0
    hook = seen["hook"]
    assert isinstance(hook, LedgerTick)
    assert (hook.agent_id, hook.host_id, hook.min_interval_s, hook.timeout_s) == (
        "GOOGLE_WINDOWS", "WINDOWS_REMOTE", 1.5, 20.0)
    assert hook.controller == "http://127.0.0.1:9"


@pytest.mark.parametrize("extra", [
    ["--ledger-agent-id", "GOOGLE_WINDOWS"],
    ["--ledger-host-id", "WINDOWS_REMOTE"],
    ["--ledger-tick-interval", "5"],
    ["--ledger-agent-id", "GOOGLE_WINDOWS", "--ledger-host-id", "WINDOWS_REMOTE", "--ledger-tick-interval", "0"],
])
def test_cli_rejects_half_or_out_of_bounds_config(monkeypatch, extra):
    _capture_loop(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        service.main(["--home", "/h", "--controller", "http://127.0.0.1:9", *extra])
    assert exc.value.code == 2


def test_status_file_records_each_started_pass(tmp_path):
    import json
    clock = FakeClock()
    runner = FakeRunner([0, 2])
    tick = LedgerTick(str(tmp_path), "http://127.0.0.1:9", "GOOGLE_WINDOWS", "WINDOWS_REMOTE",
                      min_interval_s=1.0, runner=runner, clock=clock, log=lambda _l: None)
    status = tmp_path / "run" / "ledger_tick.json"
    assert not status.exists()
    assert tick() == ledger_tick.RAN
    first = json.loads(status.read_text(encoding="utf-8"))
    assert (first["passes"], first["outcome"], first["exit_code"], first["parked_reason"]) == (1, "ran", 0, None)
    clock.now += 0.5
    assert tick() == ledger_tick.SKIPPED_INTERVAL
    assert json.loads(status.read_text(encoding="utf-8")) == first
    clock.now += 1.0
    assert tick() == ledger_tick.PARKED
    second = json.loads(status.read_text(encoding="utf-8"))
    assert (second["passes"], second["outcome"], second["exit_code"], second["parked_reason"]) == (
        2, "parked", 2, "bridge-config")
    assert set(second) == {"pid", "passes", "outcome", "exit_code", "parked_reason", "updated_at"}
    assert [p.name for p in status.parent.iterdir()] == ["ledger_tick.json"]


def test_unwritable_status_never_raises(tmp_path):
    blocker = tmp_path / "home"
    blocker.write_text("not a directory", encoding="utf-8")
    tick = LedgerTick(str(blocker), "http://127.0.0.1:9", "GOOGLE_WINDOWS", "WINDOWS_REMOTE",
                      runner=FakeRunner([0]), clock=FakeClock(), log=lambda _l: None)
    assert tick() == ledger_tick.RAN
