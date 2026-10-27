"""[DRUIDE | ACCOUNT 2] K0d (SCHURKE_REVIEW_K0: K0-1 extra, K0-2, K0-5, K0-6, K0-7, tiny --window).

Deterministic hooks, no real process stops. Every test here failed (or its mutant survived) before K0d, see ROT_VOR_FIX_K0d.txt / MUTATION_K0d.txt.
"""

import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, SHA, Clock, Gh  # noqa: E402
from test_round5_k0c import TAKER, state_file_of, steal  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402

HERE = Path(__file__).resolve().parent
RUNBOOK = (HERE / "RUNBOOK.md").read_text(encoding="utf-8")
POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="SKIPPED, NOT PASSED: directory fsync is POSIX-only")


# ------------------------------------------------------------------ K0-1 extra: stop at the first heartbeat that sees the loss

def test_k0d_a_lock_lost_at_the_first_heartbeat_stops_before_the_sleep(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    clock = Clock()
    cfg = dict(window=300, max_attempts=10, max_interval=86400)
    gh = Gh(BUSY)
    first = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=1, max_attempts=10, max_interval=86400), run_cmd=gh,
                    clock=clock.time, sleep=clock.sleep)
    assert first["status"] == w.WAITING
    polls_before = len(gh.lists)  # one poll plus the poll at the window edge
    before_bytes = state_file_of(tmp_path).read_bytes()
    clock.sleeps.clear()
    real_read = w.read_state

    def read_then_stall(path):
        value = real_read(path)
        steal(tmp_path)  # a taker replaced the lock while this process was stalled before its first heartbeat of the round
        return value

    monkeypatch.setattr(w, "read_state", read_then_stall)
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(**cfg), run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert result["status"] == w.LOCKED and "lock lost" in result["last_error"]
    assert clock.sleeps == [], "the owner slept although it had already seen that the lock is gone"
    assert len(gh.lists) == polls_before, "no further poll"
    assert state_file_of(tmp_path).read_bytes() == before_bytes


def test_k0d_touch_after_a_loss_never_refreshes_the_lock_of_the_new_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    lock = w._Lock(tmp_path / "k.lock")
    assert lock.acquire() and lock.excl_held
    lock.excl_path.write_text(TAKER)  # taken over
    os.utime(lock.excl_path, (1000, 1000))
    lock.touch()
    assert lock.lost
    assert lock.excl_path.stat().st_mtime == 1000, "the lost owner refreshed the heartbeat of the new owner's lock"
    lock.touch()
    assert lock.excl_path.stat().st_mtime == 1000
    lock.release()
    assert lock.excl_path.read_text() == TAKER, "release removed the lock of the new owner"


# ------------------------------------------------------------------ tiny --window: one look per call

class TickingClock(Clock):
    """Every reading of the clock advances it (a slow gh call, a busy machine)."""

    def __init__(self, tick):
        super().__init__()
        self.tick = tick

    def time(self):
        self.t += self.tick
        return self.t


@pytest.mark.parametrize("window", [1e-9, 1e-6])
def test_k0d_a_tiny_window_still_makes_the_one_poll_that_is_due_now(tmp_path, window):
    clock, gh = TickingClock(1e-6), Gh(BUSY)
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=window, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert result["status"] == w.WAITING
    assert result["polls_this_call"] == 1 and len(gh.lists) == 1


def test_k0d_the_due_now_poll_is_made_once_per_call_not_until_the_attempts_run_out(tmp_path):
    clock, gh = TickingClock(10.0), Gh(BUSY)  # each clock reading jumps 10 s: the next poll is always already due
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=1, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert result["status"] == w.WAITING
    assert result["polls_this_call"] == 1 and len(gh.lists) == 1


# ------------------------------------------------------------------ K0-6 directory fsync: which directory, and no fd leak

def _dir_fsyncs(monkeypatch):
    seen = []
    real = os.fsync

    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            seen.append(os.fstat(fd).st_ino)
        return real(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    return seen


@POSIX_ONLY
def test_k0d_watcher_fsyncs_the_directory_that_holds_the_state_file(tmp_path, monkeypatch):
    nested = tmp_path / "outer" / "inner"
    nested.mkdir(parents=True)
    seen = _dir_fsyncs(monkeypatch)
    w.write_state(nested / ".ci-watch-x.json", {"a": 1})
    assert seen == [nested.stat().st_ino], "the directory fsynced is not the one that contains the state file"
    assert nested.stat().st_ino != nested.parent.stat().st_ino


@pytest.mark.parametrize("module", [w, je], ids=["watcher", "exporter"])
@POSIX_ONLY
def test_k0d_the_directory_descriptor_is_always_closed(tmp_path, monkeypatch, module):
    opened, closed = [], []
    real_open, real_close, real_fsync = os.open, os.close, os.fsync

    def op(path, *a, **k):
        fd = real_open(path, *a, **k)
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            opened.append(fd)
        return fd

    def cl(fd):
        closed.append(fd)
        return real_close(fd)

    def failing(fd):
        raise OSError("fsync refused")

    monkeypatch.setattr(os, "open", op)
    monkeypatch.setattr(os, "close", cl)
    module._fsync_dir(tmp_path)
    assert opened and sorted(opened) == sorted(closed), "descriptor of the directory leaked"
    opened.clear(), closed.clear()
    monkeypatch.setattr(os, "fsync", failing)
    module._fsync_dir(tmp_path)  # a refusing filesystem is not an error, and still no leak
    assert opened and sorted(opened) == sorted(closed)
    monkeypatch.setattr(os, "fsync", real_fsync)


# ------------------------------------------------------------------ K0-5 / K0-7 text and behaviour

def test_k0d_exporter_order_of_checks_is_what_the_docs_say(tmp_path, capsys):
    missing = tmp_path / "none.db"
    assert je.main([str(missing), "--out", str(missing)]) == 3  # missing journal wins, also with --out = the same path
    assert je.main([str(missing), "--expect-head-hash", "zz"]) == 2  # a malformed hash is decided first
    present = tmp_path / "junk.db"
    present.write_bytes(b"not a database")
    assert je.main([str(present), "--out", str(present)]) == 2  # --out = an existing journal is a usage error
    capsys.readouterr()
    doc = " ".join(je.__doc__.split())
    assert "only a malformed --expect-head-hash is decided before the journal is looked at" in doc
    assert "a missing journal is exit 3, also when --out names that same path" in doc
    assert "--out equal to the journal) are decided before" not in doc
    book = " ".join(RUNBOOK.split())
    assert "a malformed `--expect-head-hash` is exit 2 first, even if the journal is missing" in book
    assert "missing = exit 3 (also when `--out` names that same path)" in book


def test_k0d_runbook_does_not_promise_never_a_false_success_for_the_observer():
    book = " ".join(RUNBOOK.split())
    assert "never a false SUCCESS" not in book.replace("NOT a guarantee against a false SUCCESS", "")
    assert "NOT a guarantee against a false SUCCESS" in book
    assert "ANOTHER workflow of the same SHA" in book


def test_k0d_reset_from_unconfirmed_is_exit_18_as_documented(tmp_path):
    clock, gh = Clock(), Gh([])
    state = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=600, max_attempts=50, dispatch_grace=5), run_cmd=gh,
                    clock=clock.time, sleep=clock.sleep, dispatch=lambda: None)
    assert state["status"] == w.UNCONFIRMED
    out = w.reset_state("WK", SHA, tmp_path)
    assert out["status"] == w.RESET_REFUSED and out["exit_code"] == 18
    book = " ".join(RUNBOOK.split())
    assert "`--reset-state` from DISPATCH_UNCONFIRMED is refused (exit 18, RESET_REFUSED)" in book
    assert "`--reset-state` does not help here (exit 18, RESET_REFUSED)" in book


def test_k0d_help_and_the_exit_2_text_name_the_upper_limits(capsys):
    assert w.main(["--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    for needle in ("--base and --max-interval 1..86400 s", "--window 0..86400 s", "--factor 1..100", "--max-attempts >= 0"):
        assert needle in text, needle
    assert w.main(["--workkey", "k", "--sha", SHA, "--state-dir", "/nonexistent/never-created", "--base", "0.5"]) == 2
    err = capsys.readouterr().err
    assert "<= 86400" in err and "--factor <= 100" in err


def test_k0d_runbook_names_the_clock_jump_limit_and_the_tiny_window_rule():
    book = " ".join(RUNBOOK.split())
    assert "Known limit (Schurke K0-2, not fixed)" in book
    assert "two processes hold it until the owner's next heartbeat" in book
    assert "even `--window 1e-9` looks once" in book
    assert "first heartbeat of a round, before the sleep" in book
