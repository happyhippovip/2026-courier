"""[DRUIDE | ACCOUNT 2] K0c (MAGIER_NACHTEST_K0 N1..N4).

N1 lock loss is checked right before the dispatch and right before every state write (deterministic takeover hooks, no real process stop).
N2 absurd int values: ValueError instead of OverflowError, no big-integer power in Backoff.delay.
N3 test gaps of the mutants W17/W19/W29/W30.
N4 the skip rule is enforced at run time by tests/automation/conftest.py (the AST scan stays as a lint).
"""

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import BUSY, DONE, SHA, Clock, Gh  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

HERE = Path(__file__).resolve().parent
TAKER = "someone-else:token"


def lock_file_of(tmp_path, key="WK"):
    state = w.state_path(tmp_path, w.idempotency_key(key, SHA))
    return state.with_name(state.name[:-5] + ".lock.x")


def state_file_of(tmp_path, key="WK"):
    return w.state_path(tmp_path, w.idempotency_key(key, SHA))


def steal(tmp_path):
    lock_file_of(tmp_path).write_text(TAKER)  # a taker replaced our lock file while we were stalled


def watch(tmp_path, gh, clock, **kw):
    cfg = dict(window=300, max_attempts=10)
    cfg.update(kw.pop("cfg", {}))
    return w.watch("WK", SHA, tmp_path, backoff=w.Backoff(**cfg), run_cmd=gh, clock=clock.time, sleep=clock.sleep, **kw)


# ------------------------------------------------------------------ N1 (O_EXCL fallback only; flock has no takeover)

def test_k0c_n1_a_lock_lost_before_the_dispatch_means_no_dispatch_no_poll_no_state(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    real_read = w.read_state
    dispatched = []

    def read_then_stall(path):
        value = real_read(path)
        steal(tmp_path)  # the owner stalled (>stale limit) between read_state and the dispatch
        return value

    monkeypatch.setattr(w, "read_state", read_then_stall)
    gh = Gh(BUSY)
    result = watch(tmp_path, gh, Clock(), dispatch=lambda: dispatched.append(1))
    assert result["status"] == w.LOCKED and "lost" in result["last_error"]
    assert dispatched == [] and gh.commands == []
    assert not state_file_of(tmp_path).exists()  # nothing written, not even the intent marker
    assert lock_file_of(tmp_path).read_text() == TAKER


def test_k0c_n1_a_lock_lost_during_the_dispatch_keeps_the_marker_and_writes_nothing_more(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    gh = Gh(BUSY)
    result = watch(tmp_path, gh, Clock(), dispatch=lambda: steal(tmp_path))
    assert result["status"] == w.LOCKED
    assert gh.commands == []
    stored = json.loads(state_file_of(tmp_path).read_text())
    assert stored["dispatch"] == "DISPATCHING"  # the intent marker stays: nobody dispatches this key a second time
    assert lock_file_of(tmp_path).read_text() == TAKER


def test_k0c_n1_a_lock_lost_during_the_poll_does_not_overwrite_the_state_of_the_new_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    taker_state = json.dumps({"attempts": 5, "dispatch": "NONE", "status": "WATCHING", "owner": "taker"})
    calls = []

    def gh(command):
        calls.append(command)
        steal(tmp_path)
        state_file_of(tmp_path).write_text(taker_state)  # what the new owner has written meanwhile
        return 0, json.dumps(DONE), ""

    result = watch(tmp_path, gh, Clock())
    assert result["status"] == w.LOCKED and "lost" in result["last_error"]
    assert len(calls) == 1
    assert state_file_of(tmp_path).read_text() == taker_state  # a finished run would have been written as COMPLETED over it


def test_k0c_n1_a_lock_lost_during_the_poll_blocks_the_write_of_a_wait_schedule_too(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    taker_state = json.dumps({"attempts": 5, "owner": "taker"})

    def gh(command):
        steal(tmp_path)
        state_file_of(tmp_path).write_text(taker_state)
        return 0, json.dumps(BUSY), ""

    assert watch(tmp_path, gh, Clock())["status"] == w.LOCKED
    assert state_file_of(tmp_path).read_text() == taker_state


def test_k0c_n1_a_clean_run_still_dispatches_polls_and_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    dispatched, clock = [], Clock()
    gh = Gh([dict(DONE[0], createdAt=w_iso(clock.t + 1))])
    result = watch(tmp_path, gh, clock, dispatch=lambda: dispatched.append(1))
    assert result["status"] == w.COMPLETED and dispatched == [1]
    assert json.loads(state_file_of(tmp_path).read_text())["status"] == w.COMPLETED
    assert not lock_file_of(tmp_path).exists()


def w_iso(epoch):
    from test_ci_watcher_v2 import iso
    return iso(epoch)


def test_k0c_n1_with_flock_nothing_changes(tmp_path):
    if w.fcntl is None:
        pytest.skip("SKIPPED, NOT PASSED: this platform has no fcntl (the O_EXCL fallback is the only lock here)")
    gh = Gh(DONE)
    first, second = watch(tmp_path, gh, Clock()), watch(tmp_path, gh, Clock())
    assert first["status"] == w.COMPLETED == second["status"]


def test_k0c_n1_the_runbook_states_what_is_and_is_not_covered():
    text = " ".join((HERE / "RUNBOOK.md").read_text(encoding="utf-8").split())
    assert "before the dispatch and before every state write" in text
    assert "between that check and the write" in text  # the remaining window is named, not hidden
    assert "stops without polling or writing" not in text  # the old, too broad promise


# ------------------------------------------------------------------ N2

@pytest.mark.parametrize("field", ["base", "max_interval", "window", "dispatch_grace", "factor"])
@pytest.mark.parametrize("value", [10 ** 400, -(10 ** 400)])
def test_k0c_n2_a_huge_int_is_a_value_error_not_an_overflow_error(field, value):
    with pytest.raises(ValueError):
        w.validate_backoff(w.Backoff(**{field: value}))


def test_k0c_n2_a_huge_attempt_number_with_an_int_factor_is_instant():
    backoff = w.Backoff(base=5, factor=100, max_interval=60)  # ints on purpose: int ** int is exact and slow
    started = time.monotonic()
    assert backoff.delay(10 ** 7) == 60.0  # the old int power needed ~16 s here and gigabytes for 10 ** 9
    assert time.monotonic() - started < 1.0


def test_k0c_n2_int_and_float_factors_give_the_same_delays():
    for attempt in range(1, 12):
        assert w.Backoff(base=2, factor=3, max_interval=500).delay(attempt) == w.Backoff(base=2.0, factor=3.0, max_interval=500.0).delay(attempt)


# ------------------------------------------------------------------ N3: the mutants W17 / W19 / W29 / W30

def _age_lock(tmp_path, seconds_from_now):
    path = tmp_path / "x.lock"
    owner = w._Lock(path, stale_after=100.0)
    assert owner.acquire()
    stamp = time.time() + seconds_from_now
    os.utime(owner.excl_path, (stamp, stamp))
    return path


@pytest.mark.parametrize("offset, stale", [(-150, True), (150, True), (-105, True), (105, True), (-95, False), (95, False), (-50, False), (50, False)])
def test_k0c_n3_the_mtime_thresholds_are_exactly_one_stale_limit_in_both_directions(tmp_path, monkeypatch, offset, stale):
    """W17 (future threshold -3x) and W19 (past threshold 2x) survived: 1.05x and 1.5x must already be stale, 0.95x must be live."""
    monkeypatch.setattr(w, "fcntl", None)
    path = _age_lock(tmp_path, offset)  # offset > 0: mtime in the future; offset < 0: mtime in the past
    assert w._Lock(path, stale_after=100.0).acquire() is stale


@pytest.mark.parametrize("max_interval, age, expect_locked", [
    (1.0, 400, True),     # 600 s floor: 400 s old is live (W29 mutant 300 s would take it over)
    (1.0, 700, False),    # beyond the floor: stale
    (1.0, 590, True),
    (100.0, 590, True),   # 3*100+300 = 600: still the floor
    (1000.0, 3200, True),  # 3*1000+300 = 3300 > 600: the formula, not the floor
    (1000.0, 3400, False),
])
def test_k0c_n3_the_stale_limit_of_a_watch_is_max_of_600_and_3_max_interval_plus_300(tmp_path, monkeypatch, max_interval, age, expect_locked):
    monkeypatch.setattr(w, "fcntl", None)
    lock = lock_file_of(tmp_path)
    lock.write_text("dead:token")
    stamp = time.time() - age
    os.utime(lock, (stamp, stamp))
    gh = Gh(BUSY)
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(base=1.0, max_interval=max_interval, window=1.0, max_attempts=2), run_cmd=gh,
                     clock=Clock().time, sleep=lambda s: None)
    assert (result["status"] == w.LOCKED) is expect_locked, (result["status"], age)


def test_k0c_n3_a_directory_that_cannot_be_opened_does_not_fail_the_state_write(tmp_path, monkeypatch):
    """W30: an open() error of the directory fsync must not propagate (same class as R3-3 in the exporter)."""
    real_open = os.open
    attempted = []

    def refuse_directory(path, flags, *args, **kwargs):
        if Path(path) == tmp_path:
            attempted.append(path)
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", refuse_directory)
    target = tmp_path / ".ci-watch-x.json"
    w.write_state(target, {"attempts": 1})
    if os.name != "nt":
        assert attempted, "the directory fsync must have been attempted (and its failure ignored)"
    assert json.loads(target.read_text()) == {"attempts": 1}


# ------------------------------------------------------------------ N4: run-time enforcement of the skip prefix

BYPASSES = {
    "from_import": "from pytest import skip\ndef test_x():\n    skip('x')\n",
    "alias": "import pytest as pt\ndef test_x():\n    pt.skip('x')\n",
    "importorskip": "import pytest\ndef test_x():\n    pytest.importorskip('module_that_does_not_exist_k0c')\n",
    "unittest_skip": "import unittest\n@unittest.skip('x')\ndef test_x():\n    pass\n",
    "skip_without_reason": "import pytest\n@pytest.mark.skip\ndef test_x():\n    pass\n",
    "skip_exception": "import pytest\ndef test_x():\n    raise pytest.skip.Exception('x')\n",
    "getattr": "import pytest\ndef test_x():\n    getattr(pytest, 'skip')('x')\n",
    "xfail_call": "import pytest\ndef test_x():\n    pytest.xfail('x')\n",
    "module_level": "import pytest\npytest.skip('x', allow_module_level=True)\ndef test_x():\n    pass\n",
    "skipif_reason": "import pytest\n@pytest.mark.skipif(True, reason='nope')\ndef test_x():\n    pass\n",
}


def _run_in_scratch(tmp_path, files):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "conftest.py").write_text((HERE / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, body in files.items():
        (scratch / name).write_text(textwrap.dedent(body), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--no-header", "-rs", str(scratch)],
                          capture_output=True, text=True, cwd=scratch, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    return proc


@pytest.mark.parametrize("name", sorted(BYPASSES))
def test_k0c_n4_a_skip_without_the_prefix_fails_at_run_time_however_it_is_spelled(tmp_path, name):
    proc = _run_in_scratch(tmp_path, {f"test_{name}.py": BYPASSES[name]})
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "SKIPPED, NOT PASSED: " in proc.stdout + proc.stderr  # the failure message names the rule


def test_k0c_n4_a_skip_with_the_prefix_stays_a_skip(tmp_path):
    body = "import pytest\ndef test_x():\n    pytest.skip('SKIPPED, NOT PASSED: no flask here')\n"
    proc = _run_in_scratch(tmp_path, {"test_ok.py": body})
    assert proc.returncode == 0 and "1 skipped" in proc.stdout, proc.stdout + proc.stderr


def test_k0c_n4_the_prefixed_importorskip_and_conditional_skips_stay_skips(tmp_path):
    body = ("import pytest\n"
            "@pytest.mark.skipif(True, reason='SKIPPED, NOT PASSED: because')\n"
            "def test_a():\n    pass\n")
    proc = _run_in_scratch(tmp_path, {"test_ok.py": body})
    assert proc.returncode == 0 and "1 skipped" in proc.stdout, proc.stdout + proc.stderr


def test_k0c_n4_the_docs_name_the_ast_scan_a_lint_and_the_hook_the_enforcement():
    text = " ".join((HERE / "RUNBOOK.md").read_text(encoding="utf-8").split())
    assert "conftest.py" in text and "run time" in text and "lint" in text
