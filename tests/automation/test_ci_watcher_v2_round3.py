"""[DRUIDE | ACCOUNT 2] Last fix round for tools/automation/ci_watcher_v2.py (SCHURKE_REREVIEW.md N-W1..N-W6, MAGIER_NACHTEST.md N-1..N-3).

Real files, the injectable clock/gh stub of test_ci_watcher_v2.py; the one seam added to the code is `_Lock._stale_hook`, which
lets a test run a second process' whole acquire() at the exact moment the first has decided the lock is stale.
"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, DONE, SHA, Clock, Gh, go, run, state_of  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="SKIPPED, NOT PASSED: directory fsync is a POSIX operation")
NAN, INF = float("nan"), float("inf")


# ------------------------------------------------------------------ (4) finite numbers everywhere (N-W4, N-3)

@pytest.fixture
def no_real_gh(tmp_path_factory, monkeypatch):
    """If a flag were wrongly accepted the CLI would start polling: make sure it can only reach a dead `gh`, never GitHub."""
    bin_dir = tmp_path_factory.mktemp("deadgh")
    if sys.platform != "win32":
        gh = bin_dir / "gh"
        gh.write_text("#!/bin/sh\necho 'no network in tests' >&2\nexit 1\n")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(bin_dir))  # nothing else on PATH: a missing gh is an OSError, also harmless

@pytest.mark.parametrize("flags", [
    ["--base", "nan"], ["--base", "inf"], ["--max-interval", "nan"], ["--max-interval", "inf"], ["--factor", "nan"],
    ["--factor", "inf"], ["--window", "nan"], ["--window", "inf"], ["--window=-inf"], ["--base=-inf"]])
def test_n_w4_non_finite_flags_are_a_usage_error_before_any_gh_call(tmp_path, capsys, flags, no_real_gh):
    code = w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), *flags])
    captured = capsys.readouterr()
    assert code == 2 and captured.out == "" and ">= 1" in captured.err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("cfg", [
    {"base": 0}, {"base": 0.5}, {"base": NAN}, {"base": INF}, {"max_interval": 0}, {"max_interval": NAN}, {"max_interval": INF},
    {"factor": 0.5}, {"factor": NAN}, {"factor": INF}, {"window": NAN}, {"window": INF}, {"window": -1},
    {"dispatch_grace": NAN}, {"dispatch_grace": INF}, {"dispatch_grace": -1}, {"max_attempts": -1}])
def test_n_3_the_library_enforces_the_same_bounds_as_the_cli(tmp_path, cfg):
    gh = Gh(DONE)
    with pytest.raises(ValueError):
        go(tmp_path, gh, **cfg)
    assert gh.commands == [] and list(tmp_path.iterdir()) == []  # refused before a lock, a state file or a gh call


def test_n_3_the_defaults_and_the_documented_minimum_still_work(tmp_path):
    assert go(tmp_path, Gh(DONE), window=60, base=1, max_interval=1, factor=1)["status"] in (w.COMPLETED, w.WAITING)


# ------------------------------------------------------------------ (5) stale-lock takeover is atomic (N-W1) and the heartbeat is used (N-W5)

def make_stale_lock(tmp_path):
    path = tmp_path / "x.lock"
    dead = w._Lock(path, stale_after=100.0)
    assert dead.acquire()
    dead.excl_held = False  # the owner died without releasing
    os.utime(dead.excl_path, (1_000, 1_000))
    return path, dead.excl_path


def test_n_w1_two_takers_of_one_stale_lock_never_both_hold_it(tmp_path, monkeypatch):
    """Forced interleaving: B saw the lock stale, then A completes a whole acquire(), then B continues."""
    monkeypatch.setattr(w, "fcntl", None)
    path, excl = make_stale_lock(tmp_path)
    a, b = w._Lock(path, stale_after=100.0), w._Lock(path, stale_after=100.0)
    seen = {}

    def a_runs_completely_while_b_is_paused():
        if "a" not in seen:
            seen["a"] = a.acquire()
            seen["inode"] = excl.stat().st_ino
    b._stale_hook = a_runs_completely_while_b_is_paused
    got_b = b.acquire()
    assert seen["a"] is True and a.excl_held
    assert got_b is False and not b.excl_held, "both processes believe they hold the lock"
    assert excl.exists() and excl.stat().st_ino == seen["inode"], "B removed A's fresh lock"
    a.release()
    assert not excl.exists() and not list(tmp_path.glob("x.lock.x*"))  # no guard / grave files left behind


def test_n_w1_the_same_race_the_other_way_round_and_three_takers(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path, excl = make_stale_lock(tmp_path)
    a, b, c = (w._Lock(path, stale_after=100.0) for _ in range(3))
    outcome = {}

    def b_and_c_run_while_a_is_paused():
        if not outcome:
            outcome["b"] = b.acquire()
            outcome["c"] = c.acquire()
    a._stale_hook = b_and_c_run_while_a_is_paused
    outcome["a"] = a.acquire()
    holders = [name for name in ("a", "b", "c") if outcome[name]]
    assert holders == ["b"], holders  # exactly the first complete taker wins; the paused one and the latecomer lose
    assert excl.exists()


def test_n_w1_a_takeover_that_died_midway_fails_closed_and_the_locked_result_names_the_files(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path, excl = make_stale_lock(tmp_path)
    guard = w._Lock(path, stale_after=100.0)._takeover_guard(excl.stat())
    guard.write_text("taker that died")  # a taker created the guard and was killed before removing the stale lock
    assert not w._Lock(path, stale_after=100.0).acquire()
    os.utime(guard, (1_000, 1_000))
    assert not w._Lock(path, stale_after=100.0).acquire()  # never guess: no second holder, however old the guard is
    guard.unlink()  # the documented manual step
    assert w._Lock(path, stale_after=100.0).acquire()


def test_n_w1_the_locked_result_tells_what_to_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    holder = w._Lock(w.state_path(tmp_path, w.idempotency_key("WK", SHA)).with_suffix(".lock"))
    assert holder.acquire()
    try:
        result = go(tmp_path, Gh(DONE))
    finally:
        holder.release()
    assert result["status"] == w.LOCKED and ".lock.x" in result["last_error"] and "by hand" in result["last_error"]


def test_n_w1_release_does_not_remove_a_lock_somebody_else_took_over(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path = tmp_path / "x.lock"
    slow = w._Lock(path, stale_after=100.0)
    assert slow.acquire()
    os.utime(slow.excl_path, (1_000, 1_000))  # looked dead (e.g. suspended laptop)
    taker = w._Lock(path, stale_after=100.0)
    assert taker.acquire()
    slow.release()  # wakes up and releases "its" lock
    assert taker.excl_path.exists(), "the late release removed the new holder's lock"
    assert not w._Lock(path, stale_after=100.0).acquire()
    taker.release()
    assert not taker.excl_path.exists()


def test_n_w5_the_watch_loop_refreshes_the_heartbeat_before_and_after_every_sleep(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    lock_file = w.state_path(tmp_path, w.idempotency_key("WK", SHA)).with_name("x").with_name(
        w.state_path(tmp_path, w.idempotency_key("WK", SHA)).name[:-5] + ".lock.x")
    clock = Clock()
    ages = []

    def age_of_heartbeat():
        return __import__("time").time() - lock_file.stat().st_mtime

    def age_it():
        os.utime(lock_file, (1_000, 1_000))  # pretend the previous step took very long

    class Probe(Gh):
        def __call__(self, command):
            ages.append(("poll", age_of_heartbeat()))
            age_it()
            return super().__call__(command)

    def sleep(seconds):
        ages.append(("sleep", age_of_heartbeat()))
        age_it()
        clock.sleep(seconds)

    gh = Probe(BUSY, BUSY, BUSY)
    w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=300, max_attempts=3), run_cmd=gh, clock=clock.time, sleep=sleep)
    assert [k for k, _ in ages].count("sleep") >= 2 and [k for k, _ in ages].count("poll") == 3
    stale = [entry for entry in ages if entry[1] > 60]
    assert stale == [], f"heartbeat not refreshed at: {stale}"


# ------------------------------------------------------------------ (6) stability window: documented, and time-limited (N-W3, N-1, N-2)

def test_n_w3_the_docs_state_the_size_of_the_stability_window_and_that_the_observer_is_no_gate():
    doc = " ".join(w.__doc__.split()).lower()
    assert "stability window" in doc and "one backoff interval" in doc
    assert "later than the stability window" in doc and "is not detected" in doc
    assert "not a merge gate" in doc and "dispatch mode" in doc


def test_n_2_two_finished_looks_hours_apart_are_not_a_confirmation(tmp_path):
    clock = Clock()
    first = Gh(DONE, (1, "", "boom"), clock=clock)  # look 1 is finished, the edge poll fails
    assert go(tmp_path, first, clock, window=1)["status"] == w.WAITING
    assert state_of(tmp_path)["last_complete_ids"] == ["1"]
    later = Clock()
    later.t = clock.t + 3 * 3600  # a second invocation hours later
    second = Gh(DONE, clock=later)
    result = go(tmp_path, second, later, window=300)
    assert result["outcome"] == "SUCCESS"
    assert len(second.lists) == 2, "a look from 3 hours ago was accepted as the confirming look"


def test_n_2_two_finished_looks_one_interval_apart_still_confirm_and_an_error_poll_in_between_is_fine(tmp_path):
    clock = Clock()
    gh = Gh(DONE, (1, "", "boom"), DONE, clock=clock)
    result = go(tmp_path, gh, clock, window=300)
    assert result["outcome"] == "SUCCESS" and len(gh.lists) == 3


# ------------------------------------------------------------------ (7) the rename is made durable (N-W5)

@POSIX_ONLY
def test_n_w5_write_state_fsyncs_the_directory_after_the_replace(tmp_path, monkeypatch):
    events = []
    real_fsync, real_replace = os.fsync, os.replace

    def fsync(fd):
        events.append("fsync-dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "fsync-file")
        return real_fsync(fd)

    def replace(src, dst):
        events.append("replace")
        return real_replace(src, dst)
    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "replace", replace)
    w.write_state(tmp_path / ".ci-watch-x.json", {"attempts": 1})
    assert events == ["fsync-file", "replace", "fsync-dir"]


@POSIX_ONLY
def test_n_w5_a_filesystem_that_refuses_directory_fsync_does_not_fail_the_write(tmp_path, monkeypatch):
    real_fsync = os.fsync

    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(22, "Invalid argument")
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", fsync)
    path = tmp_path / ".ci-watch-x.json"
    w.write_state(path, {"attempts": 7})
    assert json.loads(path.read_text()) == {"attempts": 7} and [p.name for p in tmp_path.iterdir()] == [path.name]


# ------------------------------------------------------------------ (8) clock skew: what to do with DISPATCH_UNCONFIRMED (N-W2)

def test_n_w2_the_docs_say_how_to_get_out_of_an_unconfirmed_dispatch():
    doc = " ".join(w.__doc__.split()).lower()
    assert "clock" in doc and "5 s" in doc and "delete the dotfile" in doc
    assert "without --dispatch-workflow" in doc and "would send a new dispatch" in doc


def test_n_w2_reset_refusal_for_an_unconfirmed_dispatch_names_the_clock_and_the_way_out(tmp_path, capsys):
    clock = Clock()
    go(tmp_path, Gh([]), clock, dispatch=lambda: None, window=600, max_interval=60)
    assert state_of(tmp_path)["status"] == w.UNCONFIRMED
    code = w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), "--reset-state"])
    result = json.loads(capsys.readouterr().out)
    assert code == 18 and result["status"] == w.RESET_REFUSED
    text = result["last_error"].lower()
    assert "clock" in text and "without --dispatch-workflow" in text and "dotfile" in text
