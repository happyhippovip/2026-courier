"""Turn-boundary auto-continuation (PENDING_AUTO_CONTINUATION, max 1, coalescing)
and the status-write failure counter in LedgerTick. No bridge, controller or model runs."""
import threading

from courier_worker import ledger_tick, service
from courier_worker.ledger_tick import LedgerTick
from courier_worker.queue_feed import has_open_work


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class FakeRunner:
    def __init__(self):
        self.calls = 0

    def __call__(self, argv, cwd, env, timeout_s):
        self.calls += 1
        return ledger_tick.Completed(0)


def _tick(tmp_path, open_work, logs=None, **kw):
    return LedgerTick(str(tmp_path / "home"), "http://127.0.0.1:9", "A", "H", min_interval_s=30.0,
                      runner=kw.pop("runner", FakeRunner()), clock=kw.pop("clock", FakeClock()),
                      log=(logs.append if logs is not None else (lambda _l: None)),
                      open_work_probe=lambda: open_work, **kw)


def test_turn_end_with_open_work_gives_exactly_one_wakeup_and_coalesces(tmp_path):
    runner, clock = FakeRunner(), FakeClock()
    tick = _tick(tmp_path, True, runner=runner, clock=clock)
    assert tick() == ledger_tick.RAN                      # normal pass, starts the interval
    assert runner.calls == 1
    clock.now += 1.0                                      # well inside min_interval_s
    assert tick.request_continuation() == ledger_tick.CONT_REQUESTED
    assert tick.request_continuation() == ledger_tick.CONT_COALESCED
    assert tick.pending_continuation is True
    assert tick() == ledger_tick.RAN                      # wake-up ignores the interval
    assert (runner.calls, tick.continuation_wakeups, tick.continuations_coalesced) == (2, 1, 1)
    assert tick.pending_continuation is False
    clock.now += 1.0
    assert tick() == ledger_tick.SKIPPED_INTERVAL         # no second wake-up
    assert runner.calls == 2


def test_turn_end_without_open_work_gives_no_wakeup(tmp_path):
    runner, clock = FakeRunner(), FakeClock()
    tick = _tick(tmp_path, False, runner=runner, clock=clock)
    assert tick() == ledger_tick.RAN
    clock.now += 1.0
    assert tick.request_continuation() == ledger_tick.CONT_NO_OPEN_WORK
    assert tick.pending_continuation is False
    assert tick() == ledger_tick.SKIPPED_INTERVAL
    assert (runner.calls, tick.continuation_wakeups) == (1, 0)


def test_pending_continuation_still_respects_pressure_and_park(tmp_path):
    runner = FakeRunner()
    tick = _tick(tmp_path, True, runner=runner, pressure_probe=lambda: "swap")
    assert tick.request_continuation() == ledger_tick.CONT_REQUESTED
    assert tick() == ledger_tick.SKIPPED_PRESSURE
    assert tick.pending_continuation is True and runner.calls == 0
    tick.parked_reason = "bridge-config"
    assert tick() == ledger_tick.SKIPPED_PARKED and runner.calls == 0


def test_open_work_probe_failure_is_fail_closed(tmp_path):
    logs = []
    tick = LedgerTick(str(tmp_path / "home"), "http://127.0.0.1:9", "A", "H", runner=FakeRunner(),
                      clock=FakeClock(), log=logs.append,
                      open_work_probe=lambda: (_ for _ in ()).throw(RuntimeError("x")))
    try:
        tick.request_continuation()
    except RuntimeError:
        pass  # an injected probe may raise; the worker wraps the call (see loop test)
    assert tick.pending_continuation is False


def test_default_probe_without_queue_config_is_no_open_work(tmp_path):
    assert has_open_work(tmp_path) is False
    tick = LedgerTick(str(tmp_path), "http://127.0.0.1:9", "A", "H", runner=FakeRunner(),
                      clock=FakeClock(), log=lambda _l: None)
    assert tick.request_continuation() == ledger_tick.CONT_NO_OPEN_WORK


class _Hook:
    def __init__(self):
        self.requests = 0
        self.ticks = 0

    def __call__(self):
        self.ticks += 1

    def request_continuation(self):
        self.requests += 1
        if self.requests == 2:
            raise RuntimeError("boom")
        return ledger_tick.CONT_REQUESTED


class _LoopHarness(service.WorkerLoop):
    def __init__(self, actions, stop, **kw):
        super().__init__("/unused", "http://127.0.0.1:9", "w", 0.2, **kw)
        self.actions, self.stop = list(actions), stop

    def iterate(self, stop):
        if not self.actions:
            self.stop.set()
            return "stale"
        return self.actions.pop(0)


def test_worker_requests_continuation_only_at_turn_end(monkeypatch, capsys):
    monkeypatch.setattr(service, "acquire_home_lock", lambda _home: None)
    monkeypatch.setattr(service, "release_home_lock", lambda _fd: None)
    monkeypatch.setattr(service, "run_orphan_gate", lambda _home: None)
    monkeypatch.setattr(service, "outbox_read_all", lambda _home: [])
    hook = _Hook()
    loop = _LoopHarness(["delivered", "idle", "spec-rejected", "delivered", "idle"],
                        threading.Event(), idle_hook=hook)

    class _Client:
        def health(self):
            return True

    monkeypatch.setattr(loop, "_default_client", lambda: _Client())
    monkeypatch.setattr(loop.stop, "wait", lambda _s=None: loop.stop.is_set())
    assert loop.run(loop.stop) == 0
    assert (hook.requests, hook.ticks) == (2, 2)
    assert "continuation request failed: RuntimeError" in capsys.readouterr().err


def test_status_write_failure_is_logged_and_counted(tmp_path):
    blocker = tmp_path / "home"
    blocker.write_text("not a directory", encoding="utf-8")
    logs = []
    tick = LedgerTick(str(blocker), "http://127.0.0.1:9", "A", "H", min_interval_s=0.2,
                      runner=FakeRunner(), clock=FakeClock(), log=logs.append,
                      open_work_probe=lambda: False)
    assert tick() == ledger_tick.RAN
    assert tick.status_write_failures == 1
    assert any("status write failed" in l and "status_write_failures=1" in l for l in logs)
