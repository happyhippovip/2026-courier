"""[DRUIDE | ACCOUNT 2] K7 (MAGIER_NACHTEST_FINAL NF-1, C06): test gaps only, no change to the tools.

NF-1: the terminal saves (COMPLETED, DISPATCH_UNCONFIRMED, EXHAUSTED) must not overwrite the state of a taker when the lock was lost
while the gh call was running (O_EXCL fallback; deterministic takeover hook, not a real process stop).
C06: `0 <= now - looked_at`: a clock that went back between two finished looks is NOT a confirmation.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, DONE, SHA, Clock, Gh  # noqa: E402
from test_round5_k0c import TAKER, lock_file_of, state_file_of, steal, watch  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

TAKER_STATE = json.dumps({"attempts": 5, "dispatch": "NONE", "status": "WATCHING", "owner": "taker"})


def taker_takes_over(tmp_path):
    steal(tmp_path)
    state_file_of(tmp_path).write_text(TAKER_STATE)  # what the new owner has written meanwhile


def test_k7_nf1_a_lock_lost_during_the_poll_that_sees_our_finished_run_does_not_write_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    calls = []

    def gh(command):
        calls.append(command)
        taker_takes_over(tmp_path)
        return 0, json.dumps(DONE), ""

    result = watch(tmp_path, gh, Clock(), dispatch=lambda: None)  # dispatched by us: the finished run is "ours", the verdict is COMPLETED
    assert result["status"] == w.LOCKED and result["exit_code"] == 13 and result["polls_this_call"] == 1
    assert len(calls) == 1
    assert state_file_of(tmp_path).read_text() == TAKER_STATE  # the taker's state is untouched (still WATCHING)
    assert lock_file_of(tmp_path).read_text() == TAKER


def test_k7_nf1_a_lock_lost_during_the_poll_that_finds_no_run_does_not_write_unconfirmed(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    clock = Clock()

    def gh(command):
        clock.t += 10  # the poll takes 10 s: past dispatch_grace (5 s), no run of ours visible
        taker_takes_over(tmp_path)
        return 0, json.dumps([]), ""

    result = watch(tmp_path, gh, clock, dispatch=lambda: None, cfg=dict(dispatch_grace=5))
    assert result["status"] == w.LOCKED and result["exit_code"] == 13 and result["polls_this_call"] == 1
    assert state_file_of(tmp_path).read_text() == TAKER_STATE  # not DISPATCH_UNCONFIRMED over the taker's state
    assert lock_file_of(tmp_path).read_text() == TAKER


def test_k7_nf1_a_lock_lost_before_the_exhausted_verdict_does_not_write_exhausted(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    clock, gh = Clock(), Gh(BUSY)
    # call 1: two polls (one at the start, one at the window edge) and the state stays WATCHING with attempts == 2
    first = watch(tmp_path, gh, clock, cfg=dict(window=1, max_attempts=5))
    path = state_file_of(tmp_path)
    assert first["status"] == w.WAITING and json.loads(path.read_text())["attempts"] == 2
    before = path.read_text()
    # call 2 runs with max_attempts lowered to 2 (a real sequence, no hand-edited state): the exhausted check is the first thing it reaches
    real_read = w.read_state

    def read_then_stall(p):
        value = real_read(p)
        steal(tmp_path)  # lost between read_state and the exhausted check
        return value

    monkeypatch.setattr(w, "read_state", read_then_stall)
    result = watch(tmp_path, gh, clock, cfg=dict(window=300, max_attempts=2))
    assert result["status"] == w.LOCKED and result["exit_code"] == 13 and result["polls_this_call"] == 0
    assert path.read_text() == before  # EXHAUSTED was not written
    assert lock_file_of(tmp_path).read_text() == TAKER


# ------------------------------------------------------------------ C06

def test_k7_c06_a_clock_that_went_back_between_two_finished_looks_is_not_a_confirmation(tmp_path):
    clock, gh = Clock(), Gh(DONE)
    real_sleep = clock.sleep
    jumped = []

    def sleeping(seconds):
        real_sleep(seconds)
        if not jumped:
            jumped.append(True)
            clock.t -= 100.0  # the system clock is set back between look 1 and look 2

    # observer mode (no dispatch): COMPLETED needs two identical finished looks with a gap of 0..stability_gap
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=300, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=sleeping)
    assert jumped, "the clock never jumped: the scenario did not run"
    assert result["status"] == w.COMPLETED
    assert len(gh.lists) == 3, "look 2 came from a clock that went back (negative gap): it must not confirm, only look 3 may"


def test_k7_c06_a_gap_of_exactly_zero_still_confirms(tmp_path):
    clock, gh = Clock(), Gh(DONE)
    real_sleep = clock.sleep

    def sleeping(seconds):
        real_sleep(seconds)
        clock.t -= seconds  # the clock stands exactly where it stood at look 1: gap 0 (boundary of `0 <= gap`)

    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=300, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=sleeping)
    assert result["status"] == w.COMPLETED and len(gh.lists) == 2


def test_k7_a_single_unreadable_lock_file_during_the_poll_counts_as_a_loss_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    lock_path = lock_file_of(tmp_path)
    real_read, failures = Path.read_text, []

    def gh(command):
        def once(self, *a, **k):
            if self == lock_path and not failures:
                failures.append(True)
                raise PermissionError("EACCES")  # one failed read of the lock file, later reads work again
            return real_read(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", once)
        return 0, json.dumps(DONE), ""

    result = watch(tmp_path, gh, Clock(), dispatch=lambda: None)
    assert failures, "the read error never happened: the scenario did not run"
    assert result["status"] == w.LOCKED and result["exit_code"] == 13 and result["polls_this_call"] == 1
    stored = json.loads(state_file_of(tmp_path).read_text())
    assert stored["status"] == w.WATCHING and stored["dispatch"] == "DISPATCHED"  # the last write that happened is the dispatch marker, never COMPLETED
    assert not lock_path.exists(), "the lock file is still ours by content, so release removes it"


def test_k7_c06_the_text_says_that_a_clock_set_back_costs_the_observer_a_look():
    book = " ".join((Path(__file__).resolve().parent / "RUNBOOK.md").read_text(encoding="utf-8").split())
    assert "a clock set back between the two looks does not count: the next look starts over, so three looks are needed" in book
    assert "test_k7_c06_a_clock_that_went_back_between_two_finished_looks_is_not_a_confirmation" in book
    assert "a negative gap (a clock set back) does not count either" in " ".join((w.__doc__ or "").split())
