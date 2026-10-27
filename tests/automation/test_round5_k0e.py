"""[DRUIDE | ACCOUNT 2] K0e (SCHURKE_REVIEW_FINAL F-1 .. F-5). F-2 lives in test_round5_k3_fuzz.py (steady-clock schedule oracle)."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, SHA, Clock, Gh  # noqa: E402
from test_round5_k0c import TAKER, lock_file_of, state_file_of, steal, watch  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

HERE = Path(__file__).resolve().parent
BOOK = " ".join((HERE / "RUNBOOK.md").read_text(encoding="utf-8").split())


# ------------------------------------------------------------------ F-1 --reset-state never evicts a living watcher

def test_k0e_f1_reset_state_does_not_take_the_lock_of_a_watcher_with_a_long_max_interval(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    clock, gh = Clock(), Gh(BUSY)
    # a watcher with max_interval 1000 sleeps up to 1000 s between heartbeats; its own stale limit is 3300 s
    owner = {}
    real_sleep = clock.sleep

    def sleeping(seconds):
        real_sleep(seconds)
        if "result" not in owner:
            owner["seen"] = True
            lock = lock_file_of(tmp_path)
            old = time.time() - 700  # the lock age is measured with the real clock
            os.utime(lock, (old, old))  # the heartbeat is 700 s old: alive for this watcher (limit 3300 s)
            owner["lock_before"] = lock.read_text()
            owner["reset"] = w.reset_state("WK", SHA, tmp_path)
            owner["lock_after"] = lock.read_text() if lock.exists() else None
            owner["result"] = True

    clock.sleep = sleeping
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(base=1.0, max_interval=1000.0, window=3000, max_attempts=10), run_cmd=gh,
                     clock=clock.time, sleep=clock.sleep)
    assert owner.get("seen"), "the watcher never slept: the scenario did not run"
    assert owner["reset"]["status"] == w.LOCKED, "--reset-state took the lock of a living watcher"
    assert owner["lock_after"] == owner["lock_before"]
    assert result["status"] != w.LOCKED, "the living watcher was shot down by the reset"


def test_k0e_f1_the_reset_lock_limit_is_the_largest_a_watcher_can_have():
    assert w.RESET_LOCK_STALE_AFTER >= max(600.0, 3 * w.MAX_SECONDS + 300.0)


# ------------------------------------------------------------------ F-3 clean dispatch failure + lost lock

def test_k0e_f3_lock_lost_during_a_clean_dispatch_failure_is_locked_and_the_next_run_is_unconfirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)

    def failing():
        steal(tmp_path)
        raise RuntimeError("gh workflow run rejected (422)")

    clock = Clock()
    result = watch(tmp_path, Gh(BUSY), clock, dispatch=failing, cfg=dict(dispatch_grace=5))
    assert result["status"] == w.LOCKED and result["exit_code"] == 13
    assert json.loads(state_file_of(tmp_path).read_text())["dispatch"] == "DISPATCHING"
    lock_file_of(tmp_path).unlink()  # the taker is gone
    second = watch(tmp_path, Gh([]), clock, cfg=dict(dispatch_grace=5))
    assert second["status"] == w.UNCONFIRMED and second["exit_code"] == 12
    for needle in ("DISPATCH_FAILED would be exit 16", "the next run ends DISPATCH_UNCONFIRMED (exit 12, fail closed"):
        assert needle in BOOK, needle


# ------------------------------------------------------------------ F-4 a clock that jumped back

def test_k0e_f4_a_schedule_far_in_the_future_is_capped_at_max_interval(tmp_path):
    clock, gh = Clock(), Gh(BUSY)
    first = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(max_interval=10.0, window=1, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert first["status"] == w.WAITING
    stored = json.loads(state_file_of(tmp_path).read_text())
    stored["next_poll_at"] = clock.t + 1e6  # the clock jumped back after the schedule was written
    state_file_of(tmp_path).write_text(json.dumps(stored))
    clock.sleeps.clear()
    w.watch("WK", SHA, tmp_path, backoff=w.Backoff(max_interval=10.0, window=300, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert clock.sleeps[0] == 10.0
    assert "except after a clock that jumped back: the wait is capped at `max_interval`" in BOOK
    assert "it never polls before `next_poll_at`" not in BOOK


# ------------------------------------------------------------------ F-5 the LOCKED result of a lost lock reports the polls made

def test_k0e_f5_a_lock_lost_after_one_poll_reports_that_poll(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)

    def gh(command):
        steal(tmp_path)
        return 0, json.dumps(BUSY), ""

    result = watch(tmp_path, gh, Clock())
    assert result["status"] == w.LOCKED
    assert result["polls_this_call"] == 1


def test_k0e_f5_a_single_unreadable_lock_file_counts_as_a_loss_and_the_runbook_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    lock = w._Lock(tmp_path / "k.lock")
    assert lock.acquire()
    real = Path.read_text

    def failing(self, *a, **k):
        if self == lock.excl_path:
            raise PermissionError("EACCES")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", failing)
    lock.touch()
    assert lock.lost
    assert "A single failed read of the lock file (EACCES, EIO, EMFILE) counts as a loss" in BOOK
