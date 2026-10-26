"""CI watcher v2: sha scope, bounded backoff, restart resume, idempotent dispatch, call counts."""

import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_call_counts as scen  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SHA = "a" * 40
OTHER = "b" * 40


class Clock:
    def __init__(self):
        self.t = 1_800_000_000.0
        self.sleeps = []

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


class Gh:
    """gh stub that counts calls. `script` is a list of replies consumed in order; the last one repeats."""

    def __init__(self, *replies, clock=None):
        self.replies = list(replies) or [[]]
        self.commands = []
        self.times = []
        self.clock = clock

    def __call__(self, command):
        self.commands.append(command)
        if self.clock:
            self.times.append(self.clock.t)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, tuple):
            return reply
        return 0, json.dumps(reply), ""

    @property
    def lists(self):
        return [c for c in self.commands if c[1:3] == ["run", "list"]]


def run(status="in_progress", conclusion=None, sha=SHA, rid=1):
    return {"databaseId": rid, "status": status, "conclusion": conclusion, "headSha": sha, "displayTitle": "t",
            "workflowName": "ci", "url": f"https://x/{rid}"}


DONE = [run("completed", "success")]
BUSY = [run("in_progress")]


def go(tmp_path, gh, clock=None, key="WK", sha=SHA, dispatch=None, **cfg):
    clock = clock or Clock()
    cfg.setdefault("window", 60.0)
    return w.watch(key, sha, tmp_path, backoff=w.Backoff(**cfg), dispatch=dispatch, run_cmd=gh,
                   clock=clock.time, sleep=clock.sleep)


def state_of(tmp_path, key="WK", sha=SHA):
    return json.loads(w.state_path(tmp_path, w.idempotency_key(key, sha)).read_text())


# ---------------------------------------------------------------- backoff
def test_backoff_sequence_is_bounded_exponential():
    b = w.Backoff()
    assert [b.delay(n) for n in range(1, 10)] == [0, 5, 10, 20, 40, 60, 60, 60, 60]
    c = w.Backoff(base=1, factor=3, max_interval=10)
    assert [c.delay(n) for n in range(1, 7)] == [0, 1, 3, 9, 10, 10]
    assert w.Backoff(base=2, factor=0.1).delay(5) == 2  # factor < 1 never shrinks below the base


def test_poll_times_follow_the_schedule_and_the_last_poll_sits_on_the_window_edge(tmp_path):
    clock = Clock()
    t0 = clock.t
    gh = Gh(BUSY, clock=clock)
    r = go(tmp_path, gh, clock)
    assert [round(t - t0) for t in gh.times] == [0, 5, 15, 35, 60]
    assert r["status"] == w.WAITING and r["polls_this_call"] == 5


def test_completion_stops_polling_at_once(tmp_path):
    clock = Clock()
    gh = Gh(BUSY, BUSY, DONE, clock=clock)
    r = go(tmp_path, gh, clock)
    assert r["status"] == w.COMPLETED and r["outcome"] == "SUCCESS" and r["exit_code"] == 0
    assert len(gh.lists) == 3 and clock.sleeps == [5, 10]


def test_max_attempts_bounds_calls_then_zero_calls(tmp_path):
    gh = Gh(BUSY)
    r = go(tmp_path, gh, max_attempts=3, window=0)
    assert r["status"] == w.EXHAUSTED and len(gh.lists) == 3 and r["exit_code"] == 11
    again = go(tmp_path, gh, max_attempts=3, window=0)
    assert again["status"] == w.EXHAUSTED and len(gh.lists) == 3  # nothing more


def test_max_attempts_counts_across_restarts(tmp_path):
    clock, gh = Clock(), Gh(BUSY)
    go(tmp_path, gh, clock, max_attempts=4, window=12)  # polls at 0, 5, then edge 12
    first = len(gh.lists)
    r = go(tmp_path, gh, clock, max_attempts=4, window=0)
    assert first < 4 and len(gh.lists) == 4 and r["status"] == w.EXHAUSTED


# ---------------------------------------------------------------- sha scope
def test_query_is_scoped_to_the_sha_with_a_small_limit(tmp_path):
    gh = Gh(DONE)
    go(tmp_path, gh)
    assert gh.lists[0][:7] == ["gh", "run", "list", "--commit", SHA, "--limit", "20"]
    assert "--json" in gh.lists[0]


def test_runs_of_another_sha_are_ignored(tmp_path):
    gh = Gh([run("completed", "success", sha=OTHER), run("completed", "failure", sha=OTHER, rid=2)])
    r = go(tmp_path, gh, max_attempts=3, window=0)
    assert r["status"] == w.EXHAUSTED and r["runs"] == []  # a foreign green run is not our result


def test_only_a_mixed_reply_counts_our_sha_and_waits_for_all_its_runs(tmp_path):
    clock = Clock()
    gh = Gh([run("completed", "success", rid=1), run("in_progress", rid=2), run("completed", "success", sha=OTHER, rid=3)],
            [run("completed", "success", rid=1), run("completed", "failure", rid=2)], clock=clock)
    r = go(tmp_path, gh, clock)
    assert r["status"] == w.COMPLETED and r["outcome"] == "FINISHED_NOT_SUCCESS" and r["exit_code"] == 1
    assert [x["databaseId"] for x in r["runs"]] == [1, 2] and len(gh.lists) == 2


def test_no_run_yet_is_not_completion(tmp_path):
    r = go(tmp_path, Gh([]), max_attempts=2, window=0)
    assert r["status"] == w.EXHAUSTED and r["conclusion"] is None


def test_invalid_input_is_rejected_before_any_call(tmp_path):
    gh = Gh(DONE)
    for sha in ("", "abc", "A" * 40, "g" * 40, "a" * 39):
        with pytest.raises(ValueError):
            go(tmp_path, gh, sha=sha)
    with pytest.raises(ValueError):
        go(tmp_path, gh, key="")
    assert gh.commands == []


# ---------------------------------------------------------------- errors
@pytest.mark.parametrize("reply,rate", [
    ((1, "", "gh: HTTP 500 server error"), False),
    ((1, "", "API rate limit exceeded for user"), True),
    ((1, "", "gh: HTTP 429"), True),
    ((0, "{not json", ""), False),
    ((0, json.dumps({"a": 1}), ""), False),
    ((0, json.dumps([1, 2]), ""), False),
    ((0, "", ""), False),
])
def test_errors_do_not_crash_are_recorded_and_retried(tmp_path, reply, rate):
    clock = Clock()
    gh = Gh(reply, DONE, clock=clock)
    r = go(tmp_path, gh, clock)
    assert r["status"] == w.COMPLETED and len(gh.lists) == 2
    wait_between = clock.sleeps[0]
    assert (wait_between >= 60) if rate else (wait_between == 5)


def test_error_text_is_truncated_and_kept_in_state(tmp_path):
    clock = Clock()
    gh = Gh((1, "", "x" * 5000), (1, "", "x" * 5000), clock=clock)
    go(tmp_path, gh, clock, max_attempts=2, window=0)
    assert 0 < len(state_of(tmp_path)["last_error"]) <= 200


def test_unreadable_state_is_never_guessed_and_blocks_dispatch(tmp_path):
    key = w.idempotency_key("WK", SHA)
    p = w.state_path(tmp_path, key)
    called = []
    for content in ("{broken", "[]", json.dumps({"attempts": "x"}), json.dumps({"key": "other@x", "attempts": 0})):
        p.write_text(content)
        gh = Gh(DONE)
        r = go(tmp_path, gh, dispatch=lambda: called.append(1))
        assert r["status"] == w.STATE_UNREADABLE and r["exit_code"] == 14
        assert gh.commands == [] and called == [] and p.read_text() == content  # file untouched


# ---------------------------------------------------------------- idempotent dispatch
def test_dispatch_runs_once_per_key_across_calls_and_restarts(tmp_path):
    count = []
    gh = Gh(BUSY)
    for _ in range(4):
        go(tmp_path, gh, Clock(), dispatch=lambda: count.append(1), window=1)
    assert count == [1]
    assert state_of(tmp_path)["dispatch"] == "DISPATCHED"


def test_other_sha_or_other_workkey_is_a_different_key(tmp_path):
    count = []
    for key, sha in (("WK", SHA), ("WK", OTHER), ("WK2", SHA), ("WK", SHA)):
        go(tmp_path, Gh(DONE), key=key, sha=sha, dispatch=lambda: count.append(1))
    assert len(count) == 3


def test_failed_dispatch_frees_the_key_but_a_crash_does_not(tmp_path):
    def failing():
        raise RuntimeError("gh workflow run failed")

    with pytest.raises(RuntimeError):
        go(tmp_path, Gh(DONE), dispatch=failing)
    assert state_of(tmp_path)["dispatch"] == "NONE"
    count = []
    go(tmp_path, Gh(DONE), dispatch=lambda: count.append(1))
    assert count == [1]

    class Kill(BaseException):
        pass

    def crash():
        raise Kill()

    with pytest.raises(Kill):
        go(tmp_path, Gh(BUSY), key="CRASH", dispatch=crash)
    assert state_of(tmp_path, "CRASH")["dispatch"] == "DISPATCHING"
    later = []
    go(tmp_path, Gh(BUSY), key="CRASH", dispatch=lambda: later.append(1), window=1)
    assert later == []  # never a second dispatch after a possibly-sent first one


def test_dispatching_marker_adopts_a_late_run_or_ends_unconfirmed_without_redispatch(tmp_path):
    clock = Clock()
    key = w.idempotency_key("WK", SHA)
    marker = {"key": key, "sha": SHA, "workkey": "WK", "status": "WATCHING", "attempts": 0, "next_poll_at": None,
              "dispatch": "DISPATCHING", "dispatched_at": clock.time()}
    w.write_state(w.state_path(tmp_path, key), marker)
    count = []
    gh = Gh([], [], BUSY, DONE, clock=clock)
    r = go(tmp_path, gh, clock, dispatch=lambda: count.append(1))
    assert r["status"] == w.COMPLETED and count == []

    d2 = tmp_path / "late"
    d2.mkdir()
    w.write_state(w.state_path(d2, key), marker | {"dispatched_at": clock.time()})
    gh2 = Gh([])
    r2 = w.watch("WK", SHA, d2, backoff=w.Backoff(window=0, dispatch_grace=20), dispatch=lambda: count.append(1),
                 run_cmd=gh2, clock=clock.time, sleep=clock.sleep)
    assert r2["status"] == w.UNCONFIRMED and r2["exit_code"] == 12 and count == []
    n = len(gh2.lists)
    assert go(d2, gh2, clock)["status"] == w.UNCONFIRMED and len(gh2.lists) == n


# ---------------------------------------------------------------- restart / resume
class SimulatedKill(BaseException):
    pass


def test_kill_mid_poll_then_restart_resumes_counter_without_early_poll_or_second_dispatch(tmp_path):
    clock = Clock()
    t0 = clock.t
    dispatched = []
    gh = Gh(BUSY, clock=clock)
    kills = {"n": 0}

    def killing_sleep(seconds):
        kills["n"] += 1
        if kills["n"] == 3:
            raise SimulatedKill()  # process dies while waiting for poll 4
        clock.sleep(seconds)

    with pytest.raises(SimulatedKill):
        w.watch("WK", SHA, tmp_path, backoff=w.Backoff(window=0, max_attempts=6), dispatch=lambda: dispatched.append(1),
                run_cmd=gh, clock=clock.time, sleep=killing_sleep)
    saved = state_of(tmp_path)
    assert saved["attempts"] == 3 and saved["status"] == "WATCHING" and dispatched == [1]
    assert round(saved["next_poll_at"] - t0) == 35
    clock.t = t0 + 20  # restarted 20 s later: poll 4 is due at 35
    r = go(tmp_path, gh, clock, dispatch=lambda: dispatched.append(1), window=0, max_attempts=6)
    assert dispatched == [1] and r["status"] == w.EXHAUSTED and r["attempts"] == 6
    assert round(gh.times[3] - t0) == 35  # not earlier than the persisted schedule
    assert len(gh.lists) == 6  # 3 before the kill + 3 after, nothing repeated


def test_persisted_schedule_beyond_window_costs_no_call_and_no_sleep(tmp_path):
    clock = Clock()
    key = w.idempotency_key("WK", SHA)
    w.write_state(w.state_path(tmp_path, key), {"key": key, "sha": SHA, "workkey": "WK", "status": "WATCHING", "attempts": 4,
                                               "next_poll_at": clock.t + 50, "dispatch": "DISPATCHED"})  # <= max_interval, > window
    gh = Gh(DONE)
    r = go(tmp_path, gh, clock, window=30)
    assert r["status"] == w.WAITING and gh.commands == [] and clock.sleeps == []


def test_terminal_state_costs_zero_calls(tmp_path):
    gh = Gh(DONE)
    go(tmp_path, gh)
    n = len(gh.commands)
    for _ in range(3):
        assert go(tmp_path, gh)["status"] == w.COMPLETED
    assert len(gh.commands) == n


def test_state_file_is_a_small_dotfile_written_atomically(tmp_path):
    go(tmp_path, Gh(DONE))
    names = sorted(p.name for p in tmp_path.iterdir())
    assert all(n.startswith(".ci-watch-") for n in names)
    assert not [n for n in names if n.endswith(".tmp")]
    path = w.state_path(tmp_path, w.idempotency_key("WK", SHA))
    assert path.stat().st_size < 4096 and json.loads(path.read_text())["key"] == f"WK@{SHA}"


@pytest.mark.skipif(w.fcntl is None, reason="no flock on this platform")
def test_second_process_for_the_same_key_is_refused_without_calls(tmp_path):
    lock = w._Lock(w.state_path(tmp_path, w.idempotency_key("WK", SHA)).with_name(
        w.state_path(tmp_path, w.idempotency_key("WK", SHA)).name[:-5] + ".lock"))
    assert lock.acquire()
    try:
        gh = Gh(DONE)
        r = go(tmp_path, gh)
        assert r["status"] == w.LOCKED and r["exit_code"] == 13 and gh.commands == []
    finally:
        lock.release()
    assert go(tmp_path, Gh(DONE))["status"] == w.COMPLETED


# ---------------------------------------------------------------- real process, SIGKILL
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys, time
log = os.environ["FAKE_GH_LOG"]
with open(log, "a") as f:
    f.write(" ".join(sys.argv[1:3]) + "\\n")
if sys.argv[1:3] == ["workflow", "run"]:
    sys.exit(0)
if sys.argv[1:3] == ["run", "list"]:
    sha = sys.argv[sys.argv.index("--commit") + 1]
    done = os.path.exists(os.environ["FAKE_GH_DONE"])
    print(json.dumps([{"databaseId": 7, "status": "completed" if done else "in_progress",
                       "conclusion": "success" if done else None, "headSha": sha, "displayTitle": "t",
                       "workflowName": "ci", "url": "u"}]))
    sys.exit(0)
sys.exit(1)
"""


@pytest.mark.skipif(sys.platform == "win32" or not hasattr(signal, "SIGKILL"),
                    reason="SIGKILL and an executable `gh` script on PATH are POSIX-only; restart is covered in-process")
def test_sigkill_mid_poll_then_real_restart_resumes_and_never_dispatches_twice(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    log, done, state_dir = tmp_path / "gh.log", tmp_path / "done.flag", tmp_path / "state"
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_LOG": str(log),
           "FAKE_GH_DONE": str(done), "PYTHONDONTWRITEBYTECODE": "1"}
    cmd = [sys.executable, "-m", "tools.automation.ci_watcher_v2", "--workkey", "WK", "--sha", SHA, "--state-dir",
           str(state_dir), "--window", "60", "--base", "0.4", "--factor", "1", "--max-interval", "0.4",
           "--dispatch-workflow", "ci.yml", "--ref", "main"]
    proc = subprocess.Popen(cmd, cwd=REPO_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + 30
    while time.time() < deadline and (not log.exists() or log.read_text().count("run list") < 3):
        time.sleep(0.05)
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    assert proc.returncode == -signal.SIGKILL
    before = log.read_text().count("run list")
    assert before >= 3 and log.read_text().count("workflow run") == 1
    saved = json.loads(next(state_dir.glob(".ci-watch-*.json")).read_text())  # intact JSON despite the kill
    assert saved["attempts"] >= before - 1 >= 2 and saved["dispatch"] == "DISPATCHED" and saved["status"] == "WATCHING"

    done.write_text("1")  # CI finishes while the watcher is down
    second = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert second.returncode == 0, second.stderr  # no stale lock: flock died with the process
    result = json.loads(second.stdout)
    assert result["outcome"] == "SUCCESS" and result["attempts"] > saved["attempts"]
    text = log.read_text()
    assert text.count("workflow run") == 1  # still exactly one dispatch
    assert text.count("run list") <= before + 2  # restart needed at most a poll or two, not a fresh series
    third = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert third.returncode == 0 and log.read_text() == text  # terminal: zero further gh calls


# ---------------------------------------------------------------- CLI
def test_dispatch_timeout_is_ambiguous_and_never_retried(tmp_path):
    """Review finding W3 (ci_watcher_v2.py gh_dispatch): a timed-out `gh workflow run` may have been accepted."""
    def timing_out(command):
        raise subprocess.TimeoutExpired(command, 120)

    with pytest.raises(w.AmbiguousDispatch):
        go(tmp_path, Gh(BUSY), dispatch=w.gh_dispatch("ci.yml", "main", run_cmd=timing_out))
    assert state_of(tmp_path)["dispatch"] == "DISPATCHING"
    later = []
    result = go(tmp_path, Gh(BUSY), dispatch=lambda: later.append(1), window=1)
    assert later == [] and result["status"] == w.WAITING


@pytest.mark.parametrize("field,value", [("next_poll_at", "soon"), ("dispatched_at", [1]), ("next_poll_at", True),
                                         ("runs", "x"), ("dispatch", "MAYBE"), ("status", "DONE")])
def test_badly_typed_state_fields_are_unreadable_not_a_crash(tmp_path, field, value):
    """Review finding W4 (read_state): wrong types used to raise TypeError deep inside the loop."""
    go(tmp_path, Gh(BUSY), window=1)
    path = w.state_path(tmp_path, w.idempotency_key("WK", SHA))
    state = json.loads(path.read_text())
    state[field] = value
    path.write_text(json.dumps(state))
    gh = Gh(DONE)
    assert go(tmp_path, gh)["status"] == w.STATE_UNREADABLE and gh.commands == []


def test_next_poll_far_in_the_future_is_clamped_to_max_interval(tmp_path):
    """Review finding W5: a stale/corrupt next_poll_at (clock jumped back) must not park the watcher forever."""
    clock = Clock()
    go(tmp_path, Gh(BUSY), clock=clock, window=1)
    path = w.state_path(tmp_path, w.idempotency_key("WK", SHA))
    state = json.loads(path.read_text())
    state["next_poll_at"] = clock.t + 10_000_000
    path.write_text(json.dumps(state))
    gh = Gh(DONE)
    result = go(tmp_path, gh, clock=clock, window=300, max_interval=60)
    assert result["status"] == w.COMPLETED and len(gh.lists) == 1 and max(clock.sleeps) <= 60


def test_cli_rejects_negative_or_nonsense_numbers(tmp_path):
    base = ["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path)]
    for bad in (["--window", "-1"], ["--base", "-5"], ["--factor", "0.5"], ["--max-interval", "-1"], ["--max-attempts", "-3"]):
        assert w.main(base + bad) == 2, bad
    assert list(tmp_path.iterdir()) == []


def test_cli_usage_errors_exit_2_and_make_no_call(tmp_path, capsys):
    assert w.main([]) == 2
    assert w.main(["--workkey", "WK", "--sha", "nope", "--state-dir", str(tmp_path)]) == 2
    assert w.main(["--workkey", "WK", "--sha", SHA, "--state-dir", str(tmp_path), "--dispatch-workflow", "x.yml"]) == 2
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------- call counts old vs new (stub, fake clock)
OLD_EXPECTED = {  # (gh_total, run_list) of the unchanged scripts/github_worker_adapter.py
    "S1_fresh_dispatch_completes_at_50s": (15, 12), "S2_one_60s_window_run_never_completes": (15, 13),
    "S3_resume_waiting_state_in_progress": (13, 13), "S4_completed_run_consumer_fails_then_rerun": (6, 4),
    "S5_already_posted": (0, 0), "S6_dispatching_marker_run_appears_late": (33, 33),
    "S7_long_window_1800s_run_completes_at_1500s": (305, 302)}
NEW_EXPECTED = {
    "S1_fresh_dispatch_completes_at_50s": (6, 5), "S2_one_60s_window_run_never_completes": (6, 5),
    "S3_resume_waiting_state_in_progress": (5, 5), "S4_completed_run_consumer_fails_then_rerun": (1, 1),
    "S5_already_posted": (0, 0), "S6_dispatching_marker_run_appears_late": (8, 8),
    "S7_long_window_1800s_run_completes_at_1500s": (30, 29)}


def test_call_counts_old_polling_baseline_vs_new_watcher_s1_to_s7():
    old = {r["scenario"]: r for r in scen.run_old()}
    new = {r["scenario"]: r for r in scen.run_new()}
    assert {k: (v["gh_total"], v["gh_calls"]["run_list"]) for k, v in old.items()} == OLD_EXPECTED
    assert {k: (v["gh_total"], v["gh_calls"]["run_list"]) for k, v in new.items()} == NEW_EXPECTED
    for name in OLD_EXPECTED:
        assert new[name]["gh_calls"]["run_list"] <= old[name]["gh_calls"]["run_list"], name
        assert new[name]["gh_total"] <= old[name]["gh_total"], name
    assert sum(v["gh_total"] for v in new.values()) < sum(v["gh_total"] for v in old.values()) / 4
    assert {limit for v in old.values() for limit in v["list_limits"]} == {100}
    assert {limit for v in new.values() for limit in v["list_limits"]} == {20}
    assert new["S1_fresh_dispatch_completes_at_50s"]["final_state"] == "COMPLETED"  # seen at the window edge, +10 s
    assert new["S1_fresh_dispatch_completes_at_50s"]["gh_calls"]["workflow_run"] == 1
    assert new["S6_dispatching_marker_run_appears_late"]["gh_calls"]["workflow_run"] == 0  # no re-dispatch
    assert new["S6_dispatching_marker_run_appears_late"]["first_seen_at"] == 136.0


def test_module_has_no_network_model_or_scheduler_imports_and_does_not_import_the_adapter():
    source = (REPO_ROOT / "tools" / "automation" / "ci_watcher_v2.py").read_text(encoding="utf-8")
    for banned in ("import requests", "import socket", "import urllib", "import http", "import sched", "import threading",
                   "from scripts", "import scripts", "openai", "anthropic", "API_KEY", "while True:  # forever"):
        assert banned not in source, banned
