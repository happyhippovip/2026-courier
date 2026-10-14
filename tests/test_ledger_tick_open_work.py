"""Gaps from AUF-20261013-06: fail-closed default open-work probe and the
positive paths of queue_feed.has_open_work. File-only, no bridge or model runs."""
import json

from courier_core.work_queue import WorkQueue
from courier_worker import ledger_tick, queue_feed
from courier_worker.ledger_tick import LedgerTick
from courier_worker.queue_feed import has_open_work

HOLDER = "integrator-test"


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


def _item(item_id, status="READY"):
    return {"id": item_id, "title": "Item " + item_id, "lane": "L2", "branch": "lane/L2-" + item_id,
            "files_scope": [f"scope/{item_id}.py"], "depends_on": [], "acceptance": ["tests"],
            "provider_hints": ["headless"], "status": status, "lease": None}


def _home(tmp_path, items, specs):
    home = tmp_path / "home"
    items_dir = tmp_path / "items"
    home.mkdir()
    items_dir.mkdir()
    for row in items:
        (items_dir / f"{row['id']}.json").write_text(json.dumps(row), encoding="utf-8")
    ledger = tmp_path / "queue_ledger.jsonl"
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({
        "holder": HOLDER, "items_dir": str(items_dir), "ledger": str(ledger), "specs": specs,
    }), encoding="utf-8")
    return home, WorkQueue(items_dir=items_dir, ledger_path=ledger)


def _tick(home, logs, runner, clock):
    # no open_work_probe: exercises the real _default_open_work
    return LedgerTick(str(home), "http://127.0.0.1:9", "A", "H", min_interval_s=30.0,
                      runner=runner, clock=clock, log=logs.append)


# -- 1) fail-closed branch of _default_open_work --------------------------------------

def _assert_no_wake(tick, runner, clock, logs, exc_name):
    assert tick() == ledger_tick.RAN
    clock.now += 1.0
    assert tick.request_continuation() == ledger_tick.CONT_NO_OPEN_WORK
    assert tick.pending_continuation is False
    assert tick() == ledger_tick.SKIPPED_INTERVAL
    assert (runner.calls, tick.continuation_wakeups) == (1, 0)
    assert f"courier_worker.ledger_tick: open-work probe failed ({exc_name})" in logs


def test_default_probe_error_is_no_open_work_and_no_wake(tmp_path, monkeypatch):
    def boom(_home, now=None):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(queue_feed, "has_open_work", boom)
    logs, runner, clock = [], FakeRunner(), FakeClock()
    tick = _tick(tmp_path, logs, runner, clock)
    _assert_no_wake(tick, runner, clock, logs, "RuntimeError")
    assert not any("secret detail" in line for line in logs)


def test_default_probe_with_broken_queue_config_fails_closed(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / queue_feed.CONFIG_NAME).write_text(json.dumps({"items_dir": "x"}), encoding="utf-8")
    logs, runner, clock = [], FakeRunner(), FakeClock()
    _assert_no_wake(_tick(home, logs, runner, clock), runner, clock, logs, "KeyError")


# -- 2) positive paths of has_open_work -----------------------------------------------

def test_ready_workkey_with_spec_is_open_work(tmp_path):
    home, _ = _home(tmp_path, [_item("WK1")], {"WK1": {"goal": "x"}})
    assert has_open_work(home) is True


def test_ready_workkey_without_spec_is_not_open_work(tmp_path):
    home, _ = _home(tmp_path, [_item("WK1")], {"OTHER": {"goal": "x"}})
    assert has_open_work(home) is False


def test_held_workkey_is_open_work_even_without_spec(tmp_path):
    home, queue = _home(tmp_path, [_item("WK1")], {})
    queue.claim("WK1", HOLDER, 3600, host="H")
    assert has_open_work(home) is True


def test_workkey_held_by_someone_else_is_not_open_work(tmp_path):
    home, queue = _home(tmp_path, [_item("WK1")], {"WK1": {"goal": "x"}})
    queue.claim("WK1", "other-holder", 3600, host="H")
    assert has_open_work(home) is False


def test_real_default_probe_with_ready_spec_gives_exactly_one_wake(tmp_path):
    home, _ = _home(tmp_path, [_item("WK1")], {"WK1": {"goal": "x"}})
    logs, runner, clock = [], FakeRunner(), FakeClock()
    tick = _tick(home, logs, runner, clock)
    tick._feed_queue = lambda: None  # keep the queue unchanged; only the wake-up is under test
    assert tick() == ledger_tick.RAN
    clock.now += 1.0
    assert tick.request_continuation() == ledger_tick.CONT_REQUESTED
    assert tick.request_continuation() == ledger_tick.CONT_COALESCED
    assert tick() == ledger_tick.RAN
    assert (runner.calls, tick.continuation_wakeups, tick.continuations_coalesced) == (2, 1, 1)
    assert not any("probe failed" in line for line in logs)
