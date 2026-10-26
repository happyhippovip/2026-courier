"""[DRUIDE | ACCOUNT 2] Regression tests for the independent review (SCHURKE_REVIEW.md CW-1..CW-6, T-1, T-2; MAGIER B1, B2, B4).

Where the finding is about real behaviour the tests start real processes with a fake `gh` executable on PATH (POSIX only,
skipped cleanly on Windows); the rest uses the injectable clock and gh stub of test_ci_watcher_v2.py.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_call_counts as scen  # noqa: E402
from test_ci_watcher_v2 import BUSY, DONE, REPO_ROOT, SHA, Clock, Gh, go, iso, run, state_of  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="SKIPPED, NOT PASSED: needs an executable `gh` script on PATH / POSIX processes")

FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
d = os.environ["FAKEGH_DIR"]
open(os.path.join(d, "calls.log"), "a").write(" ".join(sys.argv[1:3]) + "\\n")
if sys.argv[1:3] == ["workflow", "run"]:
    fail = os.path.join(d, "dispatch_fail")
    if os.path.exists(fail):
        sys.stderr.write(open(fail).read()); sys.exit(1)
    sys.exit(0)
if sys.argv[1:3] == ["run", "list"]:
    sha = sys.argv[sys.argv.index("--commit") + 1]
    f = os.path.join(d, "runs.json")
    runs = json.load(open(f)) if os.path.exists(f) else []
    for r in runs: r["headSha"] = sha
    print(json.dumps(runs)); sys.exit(0)
sys.exit(1)
'''

TIMEOUT_WRAPPER = '''
import subprocess, sys
def fake(cmd, **kw): raise subprocess.TimeoutExpired(cmd, 120)
subprocess.run = fake
from tools.automation.ci_watcher_v2 import main
sys.exit(main(sys.argv[1:]))
'''


class Cli:
    """A real `python -m tools.automation.ci_watcher_v2` process with a fake gh first on PATH."""

    def __init__(self, tmp_path):
        self.dir = tmp_path / "fakegh"
        (self.dir / "bin").mkdir(parents=True)
        gh = self.dir / "bin" / "gh"
        gh.write_text(FAKE_GH)
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        self.state = tmp_path / "state"
        self.env = {**os.environ, "PATH": f"{self.dir / 'bin'}{os.pathsep}{os.environ['PATH']}", "FAKEGH_DIR": str(self.dir),
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(REPO_ROOT)}

    def args(self, *extra, workkey="WK"):
        return ["--workkey", workkey, "--sha", SHA, "--state-dir", str(self.state), "--window", "1", *extra]

    def run(self, *extra, **kw):
        cmd = [sys.executable, "-m", "tools.automation.ci_watcher_v2", *self.args(*extra, **kw)]
        return subprocess.run(cmd, cwd=REPO_ROOT, env=self.env, capture_output=True, text=True, timeout=60)

    def run_with_timeout_wrapper(self, *extra):
        return subprocess.run([sys.executable, "-c", TIMEOUT_WRAPPER, *self.args(*extra)], cwd=REPO_ROOT, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def calls(self, what):
        log = self.dir / "calls.log"
        return log.read_text().count(what) if log.exists() else 0

    def set_runs(self, runs):
        (self.dir / "runs.json").write_text(json.dumps(runs))


DISPATCH = ("--dispatch-workflow", "ci.yml", "--ref", "main")


# ------------------------------------------------------------------ CW-1: own exit codes, JSON, no traceback

@POSIX_ONLY
def test_cw1_dispatch_timeout_in_a_real_process_is_exit_15_with_json_and_no_traceback(tmp_path):
    cli = Cli(tmp_path)
    done = cli.run_with_timeout_wrapper(*DISPATCH)
    assert done.returncode == 15 and "Traceback" not in done.stderr, done.stderr
    result = json.loads(done.stdout)
    assert result["status"] == "DISPATCH_AMBIGUOUS" and result["exit_code"] == 15 and result["workkey"] == "WK"
    assert next(cli.state.glob(".ci-watch-*.json")).read_text().count('"DISPATCHING"') == 1  # marker kept
    again = cli.run(*DISPATCH)  # a second call must watch, never dispatch
    assert again.returncode in (10, 12) and cli.calls("workflow run") == 0


@POSIX_ONLY
def test_cw1_clean_dispatch_rejection_is_exit_16_and_frees_the_key(tmp_path):
    cli = Cli(tmp_path)
    (cli.dir / "dispatch_fail").write_text("HTTP 404: Not Found (workflow ci.yml)\n")
    done = cli.run(*DISPATCH)
    assert done.returncode == 16 and "Traceback" not in done.stderr
    assert json.loads(done.stdout)["status"] == "DISPATCH_FAILED"
    assert json.loads(next(cli.state.glob(".ci-watch-*.json")).read_text())["dispatch"] == "NONE"
    assert done.returncode != w.EXIT_CODES["FINISHED_NOT_SUCCESS"]  # no collision with "runs finished, not success"


@POSIX_ONLY
def test_cw1_unusable_state_directory_is_exit_17_json_not_a_traceback(tmp_path):
    cli = Cli(tmp_path)
    cli.state.write_text("this is a file, not a directory")
    done = cli.run()
    assert done.returncode == 17 and "Traceback" not in done.stderr
    assert json.loads(done.stdout)["status"] == "IO_ERROR"


def test_cw1_the_new_exit_codes_are_distinct_and_documented():
    codes = [v for k, v in w.EXIT_CODES.items() if k not in ("RESET", "NO_STATE")]
    assert len(codes) == len(set(codes))
    for number in ("15", "16", "17", "18"):
        assert f"{number} " in w.__doc__


# ------------------------------------------------------------------ CW-6: ambiguity of dispatch failures

@pytest.mark.parametrize("text,ambiguous", [
    ("HTTP 502: Bad Gateway", True), ("HTTP 504 Gateway Timeout", True), ("HTTP 500", True), ("HTTP 408 timeout", True),
    ("", True), ("connection reset by peer", True), ("error connecting to api.github.com", True),
    ("HTTP 404: Not Found", False), ("HTTP 422: Workflow does not have 'workflow_dispatch' trigger", False),
    ("HTTP 403: Resource not accessible", False), ("unknown flag: --refx", False),
    ("To get started with GitHub CLI, please run:  gh auth login", False)])
def test_cw6_only_provable_rejections_free_the_key(text, ambiguous):
    dispatch = w.gh_dispatch("ci.yml", "main", run_cmd=lambda c: (1, "", text))
    expected = w.AmbiguousDispatch if ambiguous else RuntimeError
    with pytest.raises(expected) as caught:
        dispatch()
    assert isinstance(caught.value, w.AmbiguousDispatch) is ambiguous


def test_cw6_gh_that_cannot_start_never_sent_anything():
    def missing(command):
        raise FileNotFoundError("gh")

    with pytest.raises(RuntimeError) as caught:
        w.gh_dispatch("ci.yml", "main", run_cmd=missing)()
    assert not isinstance(caught.value, w.AmbiguousDispatch)


@POSIX_ONLY
def test_cw6_gateway_error_on_dispatch_is_never_followed_by_a_second_dispatch(tmp_path):
    """Schurke repro cw6: HTTP 502 used to free the key, so the next call dispatched again."""
    cli = Cli(tmp_path)
    (cli.dir / "dispatch_fail").write_text("HTTP 502 Bad Gateway\n")
    first = cli.run(*DISPATCH)
    assert first.returncode == 15 and json.loads(first.stdout)["status"] == "DISPATCH_AMBIGUOUS"
    (cli.dir / "dispatch_fail").unlink()  # GitHub recovers
    second = cli.run(*DISPATCH)
    assert cli.calls("workflow run") == 1, "a second dispatch was sent"
    assert second.returncode in (10, 12)


# ------------------------------------------------------------------ CW-2 / B1: only our runs, no first-poll SUCCESS

def test_cw2_an_old_finished_run_never_completes_a_fresh_dispatch():
    clock = Clock()
    old = run("completed", "success", rid=99, created=clock.t - 3600)
    result = go(Path(tempfile.mkdtemp()), Gh([old], clock=clock), clock, dispatch=lambda: None)
    assert result["status"] == w.WAITING and result["outcome"] != "SUCCESS" and result["runs"] == []


def test_cw2_the_run_created_by_the_dispatch_is_awaited_then_reported(tmp_path):
    clock = Clock()
    old = run("completed", "success", rid=99, created=clock.t - 3600)
    ours_busy = run("in_progress", rid=100, created=clock.t + 2)
    ours_done = run("completed", "failure", rid=100, created=clock.t + 2)
    gh = Gh([old], [old, ours_busy], [old, ours_done], clock=clock)
    result = go(tmp_path, gh, clock, dispatch=lambda: None)
    assert result["outcome"] == "FINISHED_NOT_SUCCESS" and [r["databaseId"] for r in result["runs"]] == [100]
    assert len(gh.lists) == 3  # the old green run did not end the watch at poll 1


def test_cw2_clock_skew_allowance_counts_a_run_created_a_few_seconds_before_our_clock_reading(tmp_path):
    clock = Clock()
    gh = Gh([run("completed", "success", rid=5, created=clock.t - 3)], clock=clock)
    assert go(tmp_path, gh, clock, dispatch=lambda: None)["outcome"] == "SUCCESS"


def test_cw2_a_push_event_run_created_after_the_dispatch_is_not_ours(tmp_path):
    clock = Clock()
    gh = Gh([run("completed", "success", rid=7, created=clock.t + 1, event="push")], clock=clock)
    assert go(tmp_path, gh, clock, dispatch=lambda: None)["status"] == w.WAITING


def test_cw2_a_dispatch_whose_run_never_appears_ends_unconfirmed_after_the_grace(tmp_path):
    clock = Clock()
    gh = Gh([run("completed", "success", rid=99, created=clock.t - 3600)], clock=clock)
    result = go(tmp_path, gh, clock, dispatch=lambda: None, window=0, dispatch_grace=30, max_attempts=50)
    assert result["status"] == w.UNCONFIRMED and result["exit_code"] == 12


def test_b1_observer_mode_needs_two_identical_finished_polls_and_notices_a_late_workflow(tmp_path):
    """Magier B1: two workflows on one SHA; the second registers after the first finished."""
    clock = Clock()
    first = run("completed", "success", rid=1)
    second_busy = run("in_progress", rid=2)
    both = [first, run("completed", "success", rid=2)]
    gh = Gh([first], [first, second_busy], both, clock=clock)
    result = go(tmp_path, gh, clock, window=300)
    assert result["outcome"] == "SUCCESS" and [r["databaseId"] for r in result["runs"]] == [1, 2]
    assert len(gh.lists) == 4  # finished(1) -> changed set -> finished(1,2) -> confirmed(1,2)


def test_b1_a_single_finished_look_is_not_a_result(tmp_path):
    gh = Gh(DONE)
    result = go(tmp_path, gh, window=0, max_attempts=1)
    assert result["status"] == w.EXHAUSTED and result["conclusion"] is None and len(gh.lists) == 1
    assert state_of(tmp_path)["last_complete_ids"] == ["1"]  # remembered for the confirming poll


@POSIX_ONLY
def test_cw2_real_process_old_green_run_does_not_make_a_fresh_dispatch_succeed(tmp_path):
    """Schurke repro cw2 in a real process: a run finished long ago exists for the SHA."""
    cli = Cli(tmp_path)
    cli.set_runs([{"databaseId": 1, "status": "completed", "conclusion": "success", "displayTitle": "old", "workflowName": "ci",
                   "url": "u", "event": "push", "createdAt": "2020-01-01T00:00:00Z"}])
    done = cli.run(*DISPATCH)
    assert cli.calls("workflow run") == 1 and done.returncode == 10 and json.loads(done.stdout)["outcome"] == "WAITING"


# ------------------------------------------------------------------ CW-3: reset path

def reset(tmp_path, capsys, extra=()):
    code = w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), "--reset-state", *extra])
    return code, json.loads(capsys.readouterr().out)


def test_cw3_reset_state_reopens_a_completed_watch_but_keeps_the_dispatch_marker(tmp_path, capsys):
    clock = Clock()
    count = []
    go(tmp_path, Gh(DONE, clock=clock), clock, dispatch=lambda: count.append(1))
    assert state_of(tmp_path)["status"] == w.COMPLETED
    code, result = reset(tmp_path, capsys)
    assert code == 0 and result["status"] == "RESET"
    after = state_of(tmp_path)
    assert after["status"] == w.WATCHING and after["attempts"] == 0 and after["dispatch"] == "DISPATCHED"
    gh = Gh([run("in_progress", rid=100, created=clock.t + 1)], clock=clock)
    again = go(tmp_path, gh, clock, dispatch=lambda: count.append(1), window=1)
    assert len(gh.lists) >= 1 and count == [1]  # polls again, never dispatches again


def test_cw3_reset_state_works_for_exhausted_and_is_a_no_op_without_state(tmp_path, capsys):
    code, result = reset(tmp_path, capsys)
    assert (code, result["status"]) == (0, "NO_STATE")
    go(tmp_path, Gh(BUSY), window=0, max_attempts=2)
    assert state_of(tmp_path)["status"] == w.EXHAUSTED
    assert reset(tmp_path, capsys)[1]["status"] == "RESET"


@pytest.mark.parametrize("status,dispatch", [(w.WATCHING, "NONE"), (w.WATCHING, "DISPATCHING"), (w.UNCONFIRMED, "DISPATCHING")])
def test_cw3_reset_state_refuses_everything_that_is_not_completed_or_exhausted(tmp_path, capsys, status, dispatch):
    key = w.idempotency_key("WK", SHA)
    state = {"key": key, "sha": SHA, "workkey": "WK", "status": status, "attempts": 3, "next_poll_at": None, "runs": [],
             "dispatch": dispatch, "dispatched_at": 1_800_000_000.0}
    path = w.state_path(tmp_path, key)
    w.write_state(path, state)
    before = path.read_text()
    code, result = reset(tmp_path, capsys)
    assert code == 18 and result["status"] == "RESET_REFUSED" and path.read_text() == before


# ------------------------------------------------------------------ CW-4: lower bounds

@pytest.mark.parametrize("flags", [["--base", "0"], ["--max-interval", "0"], ["--base", "0.5"], ["--max-interval", "0.2"],
                                   ["--base", "0", "--max-interval", "0", "--max-attempts", "200", "--window", "0"],
                                   ["--base", "-1"]])
def test_cw4_zero_or_tiny_intervals_are_a_usage_error_before_any_gh_call(tmp_path, capsys, flags):
    code = w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), *flags])
    captured = capsys.readouterr()
    assert code == 2 and captured.out == "" and ">= 1" in captured.err
    assert list(tmp_path.iterdir()) == []  # nothing started, no state, no lock


# ------------------------------------------------------------------ CW-5: a lock without fcntl

def test_cw5_without_fcntl_a_second_process_is_locked_out(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    first = go(tmp_path, Gh(BUSY), window=1)  # runs and releases
    assert first["status"] in (w.WAITING, w.EXHAUSTED)
    holder = w._Lock(w.state_path(tmp_path, w.idempotency_key("WK", SHA)).with_suffix(".lock"))
    assert holder.acquire()
    try:
        gh = Gh(DONE)
        result = go(tmp_path, gh)
        assert result["status"] == w.LOCKED and result["exit_code"] == 13 and gh.commands == []
    finally:
        holder.release()
    assert go(tmp_path, Gh(BUSY), window=1)["status"] != w.LOCKED  # released: not stuck


def test_cw5_a_stale_lock_is_taken_over_only_after_the_stale_age_and_the_heartbeat_keeps_it_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "fcntl", None)
    path = tmp_path / "x.lock"
    owner = w._Lock(path, stale_after=100.0)
    assert owner.acquire()
    os.utime(owner.excl_path, (1_000, 1_000))  # the owner died long ago
    rival = w._Lock(path, stale_after=100.0)
    assert rival.acquire() and rival.excl_held
    os.utime(rival.excl_path, (1_000, 1_000))
    rival.touch()  # heartbeat
    third = w._Lock(path, stale_after=100.0)
    assert not third.acquire()
    rival.release()
    assert not rival.excl_path.exists()


def test_cw5_the_docstring_no_longer_claims_idempotency_is_unlocked_or_the_lock_skipped():
    source = (REPO_ROOT / "tools" / "automation" / "ci_watcher_v2.py").read_text(encoding="utf-8")
    assert "the lock is skipped" not in source and "O_EXCL lock file" in w.__doc__


# ------------------------------------------------------------------ T-1: the state file is never written in place

def test_t1_a_write_that_dies_midway_leaves_the_old_state_intact_and_no_tmp_file(tmp_path, monkeypatch):
    path = tmp_path / ".ci-watch-x.json"
    w.write_state(path, {"attempts": 1})
    good = path.read_text()

    def dies_halfway(obj, handle, **kw):
        handle.write('{"attempts": 2, "tru')
        handle.flush()
        raise KeyboardInterrupt

    monkeypatch.setattr(w.json, "dump", dies_halfway)
    with pytest.raises(KeyboardInterrupt):
        w.write_state(path, {"attempts": 2})
    assert path.read_text() == good and json.loads(good) == {"attempts": 1}
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_t1_the_target_is_only_ever_replaced_from_a_complete_temp_file_in_the_same_directory(tmp_path, monkeypatch):
    path = tmp_path / ".ci-watch-x.json"
    seen = []
    real_replace = os.replace

    def spy(src, dst):
        seen.append((Path(src), Path(dst), json.loads(Path(src).read_text())))  # the temp file is complete JSON
        return real_replace(src, dst)

    monkeypatch.setattr(w.os, "replace", spy)
    w.write_state(path, {"attempts": 7})
    assert len(seen) == 1 and seen[0][0] != path and seen[0][0].parent == path.parent and seen[0][1] == path
    assert seen[0][2] == {"attempts": 7}


def test_t1_a_failing_replace_keeps_the_old_file_and_removes_the_temp_file(tmp_path, monkeypatch):
    path = tmp_path / ".ci-watch-x.json"
    w.write_state(path, {"attempts": 1})

    def broken(src, dst):
        raise OSError("disk says no")

    monkeypatch.setattr(w.os, "replace", broken)
    with pytest.raises(OSError):
        w.write_state(path, {"attempts": 2})
    assert json.loads(path.read_text()) == {"attempts": 1} and [p.name for p in tmp_path.iterdir()] == [path.name]


def test_cw8_a_short_permission_error_on_replace_is_retried(tmp_path, monkeypatch):
    path = tmp_path / ".ci-watch-x.json"
    real_replace, calls = os.replace, []

    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("target is held by a scanner")  # what Windows does
        return real_replace(src, dst)

    monkeypatch.setattr(w.os, "replace", flaky)
    monkeypatch.setattr(w.time, "sleep", lambda s: None)
    w.write_state(path, {"attempts": 5})
    assert len(calls) == 3 and json.loads(path.read_text()) == {"attempts": 5}


# ------------------------------------------------------------------ T-2 / B4: call-count harness

def test_t2_the_json_marks_not_comparable_scenarios_and_the_threshold_does_not_rest_on_s7_alone():
    done = subprocess.run([sys.executable, str(REPO_ROOT / "tests" / "automation" / "ci_call_counts.py")], capture_output=True,
                          text=True, timeout=120, cwd=REPO_ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode == 0, done.stderr
    rows = [json.loads(line) for line in done.stdout.splitlines()]
    summary = rows.pop()["summary"]
    flagged = {(r["code"], r["scenario"]) for r in rows if r["not_comparable"]}
    assert flagged == {(code, name) for code in ("old", "new") for name in scen.NOT_COMPARABLE}
    assert all("not_comparable" in r and "not_comparable_reason" in r for r in rows)
    assert summary["comparable_without_S7"]["new"] < summary["comparable_without_S7"]["old"] / 2
    assert summary["comparable"]["new"] < summary["comparable"]["old"] / 4


def test_b4_the_call_count_harness_removes_its_temp_directories(tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    scen.run_new()
    scen.run_old()
    assert list(scratch.iterdir()) == []
