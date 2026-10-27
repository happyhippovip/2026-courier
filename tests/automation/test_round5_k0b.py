"""[DRUIDE | ACCOUNT 2] K0b (SCHURKE_REREVIEW_R3 R3-W1..W5, R3-E2; MAGIER_NACHTEST_R3).

Real files and the real CLIs; the injectable clock/gh stub of test_ci_watcher_v2.py; no network.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, DONE, SHA, Clock, Gh, go, state_of  # noqa: E402
from test_ci_watcher_v2_round3 import make_stale_lock, no_real_gh  # noqa: E402,F401
from test_journal_export import export, make_journal  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402
from tools.automation import journal_export as je  # noqa: E402

HERE = Path(__file__).resolve().parent


def lock_file_of(tmp_path, key="WK"):
    state = w.state_path(tmp_path, w.idempotency_key(key, SHA))
    return state.with_name(state.name[:-5] + ".lock.x")


# ------------------------------------------------------------------ R3-W1: finite but absurd numbers are a usage error, never a traceback

@pytest.mark.parametrize("flags", [
    ["--factor", "1e200"], ["--factor", "101"], ["--base", "1e300", "--max-interval", "1e300", "--window", "0"],
    ["--base", "86401"], ["--max-interval", "86401"], ["--window", "86401"], ["--window", "1e300"],
    ["--max-attempts", "0", "--window", "1e308"]])
def test_r3_w1_absurd_cli_numbers_are_exit_2_with_a_message_not_a_traceback(tmp_path, capsys, flags, no_real_gh):
    code = w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), *flags])
    captured = capsys.readouterr()
    assert code == 2 and captured.out == "" and "Traceback" not in captured.err and "<=" in captured.err, captured.err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("cfg", [
    {"factor": 1e200}, {"factor": 100.5}, {"base": 86401.0, "max_interval": 86401.0}, {"max_interval": 86401.0}, {"window": 86401.0},
    {"dispatch_grace": 86401.0}, {"window": 1e300}])
def test_r3_w1_the_library_has_the_same_upper_bounds(tmp_path, cfg):
    gh = Gh(DONE)
    with pytest.raises(ValueError):
        go(tmp_path, gh, **cfg)
    assert gh.commands == [] and list(tmp_path.iterdir()) == []


def test_r3_w1_the_upper_bounds_themselves_are_allowed(tmp_path):
    result = go(tmp_path, Gh(DONE), base=86400.0, max_interval=86400.0, factor=100.0, window=86400.0, dispatch_grace=86400.0)
    assert result["status"] in (w.COMPLETED, w.WAITING)


@pytest.mark.parametrize("factor", [2.0, 100.0, 1e200])
def test_r3_w1_the_delay_never_overflows_even_after_thousands_of_attempts(factor):
    backoff = w.Backoff(factor=factor, max_attempts=0, window=0)  # not validated on purpose: delay() must be safe by itself
    assert backoff.delay(2) == 5.0
    for attempt in (100, 1024, 1025, 1030, 5000, 10 ** 6):
        assert backoff.delay(attempt) == 60.0, attempt


def test_r3_w1_a_slow_factor_still_grows_slowly_after_hundreds_of_attempts():
    backoff = w.Backoff(base=1.0, factor=1.0001, max_interval=86400.0)
    assert backoff.delay(2) == 1.0 and 1.0 < backoff.delay(1002) < 1.2 and backoff.delay(1002) > backoff.delay(502)


# ------------------------------------------------------------------ R3-W4: the LOCKED hint only names files that can exist

def test_r3_w4_with_flock_the_locked_hint_does_not_name_nonexistent_files(tmp_path):
    if w.fcntl is None:
        pytest.skip("SKIPPED, NOT PASSED: no flock on this platform; the O_EXCL hint is tested by test_n_w1_the_locked_result_tells_what_to_delete")
    holder = w._Lock(w.state_path(tmp_path, w.idempotency_key("WK", SHA)).with_suffix(".lock"))
    assert holder.acquire()
    try:
        result = go(tmp_path, Gh(DONE))
    finally:
        holder.release()
    assert result["status"] == w.LOCKED
    assert ".lock.x" not in result["last_error"] and "take-" not in result["last_error"] and "by hand" not in result["last_error"]
    assert "another watcher" in result["last_error"]


# ------------------------------------------------------------------ R3-W3: a lock whose mtime lies in the future must not block forever

def test_r3_w3_a_lock_with_an_absurd_future_mtime_counts_as_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path, excl = make_stale_lock(tmp_path)
    future = time.time() + 10 * 100.0  # far beyond stale_after
    os.utime(excl, (future, future))
    assert w._Lock(path, stale_after=100.0).acquire()


def test_r3_w3_a_slightly_future_mtime_is_still_a_live_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path, excl = make_stale_lock(tmp_path)
    near = time.time() + 5.0  # clock jitter, not an absurd value
    os.utime(excl, (near, near))
    assert not w._Lock(path, stale_after=100.0).acquire()


# ------------------------------------------------------------------ R3-W2b: the owner notices that its lock was taken over

def test_r3_w2_touch_reports_a_lost_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path = tmp_path / "x.lock"
    slow = w._Lock(path, stale_after=100.0)
    assert slow.acquire() and not slow.lost
    os.utime(slow.excl_path, (1_000, 1_000))  # suspended for a long time
    taker = w._Lock(path, stale_after=100.0)
    assert taker.acquire()
    slow.touch()
    assert slow.lost
    taker.touch()
    assert not taker.lost


def test_r3_w2_a_watcher_that_lost_its_lock_stops_without_polling_or_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    clock = Clock()
    gh = Gh(BUSY)
    stolen = []

    def sleep(seconds):
        clock.sleep(seconds)
        if not stolen:
            stolen.append(True)
            lock_file_of(tmp_path).write_text("someone-else:token")  # a taker replaced our lock file while we slept

    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=300, max_attempts=10), run_cmd=gh, clock=clock.time, sleep=sleep)
    assert result["status"] == w.LOCKED and "lost" in result["last_error"]
    assert len(gh.commands) == 1  # the poll before the first sleep only; none after the loss
    assert lock_file_of(tmp_path).read_text() == "someone-else:token"  # the new owner's lock is not removed


# ------------------------------------------------------------------ R3-W5: the stability window text and its +60 s part

def test_r3_w5_the_docs_no_longer_claim_a_five_second_window():
    text = (HERE.parent.parent / "tools" / "automation" / "ci_watcher_v2.py").read_text(encoding="utf-8")
    assert "5 s with the defaults" not in text
    assert re.search(r"3 \* max_interval \+ 60", text) and "between the two" in text


@pytest.mark.parametrize("gap, expected", [(75.0, w.COMPLETED), (75.5, w.EXHAUSTED), (60.0, w.COMPLETED), (15.0, w.COMPLETED)])
def test_r3_w5_two_looks_up_to_3_max_interval_plus_60_seconds_apart_confirm(tmp_path, gap, expected):
    """max_interval 5 -> gap limit 75 s. The 60 s part of the formula is what lets a look 60 s later still confirm."""
    clock = Clock()
    cfg = dict(base=1.0, max_interval=5.0, window=1.0, max_attempts=0)
    first = go(tmp_path, Gh(DONE, (1, "", "gh failed")), clock=clock, **cfg)  # one finished look, then a failed one
    assert first["status"] == w.WAITING
    looked_at = state_of(tmp_path)["last_complete_at"]
    assert looked_at is not None
    state = w.state_path(tmp_path, w.idempotency_key("WK", SHA))
    data = json.loads(state.read_text())
    data["next_poll_at"] = None  # poll at once
    state.write_text(json.dumps(data))
    clock.t = looked_at + gap
    second = go(tmp_path, Gh(DONE), clock=clock, **dict(cfg, max_attempts=3))  # exactly one more poll: no edge poll can re-confirm
    assert second["status"] == expected, (gap, second["status"])


def test_r3_w5_stability_gap_is_the_documented_formula():
    assert w.stability_gap(w.Backoff(max_interval=5.0)) == 75.0 and w.stability_gap(w.Backoff()) == 240.0


# ------------------------------------------------------------------ os.name guard (directory fsync is skipped on Windows)

def test_k0b_the_watcher_skips_the_directory_fsync_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "_IS_WINDOWS", True)
    opened = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda p, *a, **k: (opened.append(p), real_open(p, *a, **k))[1] if os.path.isdir(p) else real_open(p, *a, **k))
    w.write_state(tmp_path / ".s.json", {"status": "WATCHING"})
    assert opened == [] and (tmp_path / ".s.json").exists()


def test_k0b_the_exporter_skips_the_directory_fsync_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(je, "_IS_WINDOWS", True)
    db = make_journal(tmp_path / "courier.db")
    opened = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda p, *a, **k: (opened.append(p), real_open(p, *a, **k))[1] if os.path.isdir(p) else real_open(p, *a, **k))
    code, _, err = export(db, "--out", str(tmp_path / "export.jsonl"))
    assert code == 0 and opened == [], err


# ------------------------------------------------------------------ R3-E2: usage errors win over a missing journal

def test_r3_e2_a_malformed_head_hash_is_exit_2_even_if_the_journal_is_missing(tmp_path):
    code, out, err = export(tmp_path / "missing.db", "--expect-head-hash", "zzz")
    assert code == 2 and out == "" and "--expect-head-hash" in err


def test_r3_e2_a_good_head_hash_and_a_missing_journal_is_still_exit_3(tmp_path):
    assert export(tmp_path / "missing.db", "--expect-head-hash", "a" * 64)[0] == 3


def test_r3_e2_the_order_is_documented():
    doc = " ".join(je.__doc__.split())  # K0d: the old wording ("usage errors ... before the journal") was too broad, see test_round5_k0d.py
    assert "Order of checks" in doc and "malformed --expect-head-hash" in doc and "before the journal is looked at" in doc


# ------------------------------------------------------------------ RUNBOOK statements that the code can contradict

def test_k0b_the_runbook_names_the_limits_it_promises():
    text = (HERE / "RUNBOOK.md").read_text(encoding="utf-8")
    for needle in ("take-", "exit 13", "86400", "lock lost", "R3-W6", "FINISHED_NOT_SUCCESS", "Order of checks"):
        assert needle in text, needle
    assert "5 s with the defaults" not in text
    assert "`tests/test_github_worker_adapter.py` (needs flask), has no such prefix" in text
