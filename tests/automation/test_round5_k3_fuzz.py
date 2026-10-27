"""[DRUIDE | ACCOUNT 2] K3: seeded fuzz of ci_watcher_v2 against a hostile `gh` stub (WK-L6-CI-WATCHER-V2).

Every test is parametrised by a seed (default 300, FUZZ_SEEDS=n for more; the failing seed is in the test id).
The gh stub is random: valid run lists (all statuses/conclusions, foreign SHAs, old and new createdAt, odd field types), malformed
JSON, non-list JSON, non-zero exits with and without rate-limit text, timeouts, OSErrors. The clock jumps forwards and backwards.
The state file is damaged between calls. Invariants (an oracle written independently of the watcher):
  - no exception except the documented ones; exit code and status from the documented table; result is JSON-serialisable
  - never SUCCESS unless the last look(s) really show finished+success runs of exactly this SHA (and, after a dispatch, runs of ours)
  - an observed (not dispatched) result needs two finished looks
  - gh is only ever called as `gh run list --commit <sha> --limit 20 --json <FIELDS>` (read only)
  - polls per call and attempts per state are bounded by max_attempts; terminal states make zero gh calls
  - a key is dispatched at most once unless the earlier attempt failed cleanly; an unreadable state dispatches nothing and polls nothing
  - no temp/guard/lock leftovers after a call
"""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ci_watcher_v2 import SHA, OTHER, iso  # noqa: E402
from tools.automation import ci_watcher_v2 as w  # noqa: E402

SEEDS = range(int(os.environ.get("FUZZ_SEEDS", "300")))
T0 = 1_800_000_000.0
DOCUMENTED = set(w.EXIT_CODES.values())
STATUSES = ["completed", "completed", "completed", "in_progress", "queued", "waiting", "requested", None, "", 7, ["completed"]]
CONCLUSIONS = ["success", "success", "success", "failure", "cancelled", "skipped", "neutral", "timed_out", None, "", 0, ["success"]]
EVENTS = ["workflow_dispatch", "workflow_dispatch", "push", "pull_request", "schedule", None, 5]


class FuzzClock:
    def __init__(self, rng):
        self.rng, self.t = rng, T0

    def time(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
        if self.rng.random() < 0.05:
            self.t += self.rng.choice([-7200.0, -30.0, 30.0, 3600.0, 86400.0 * 3])  # a jump of the system clock


class FuzzGh:
    """Random `gh`. Records every command, the clock at the moment of each look and the oracle's view of each look."""

    def __init__(self, rng, clock, sha=SHA, mode="mixed"):
        self.rng, self.clock, self.sha, self.mode = rng, clock, sha, mode
        self.commands, self.looks = [], []  # looks: list of list-of-runs (None when the reply was unusable)
        self.dispatched_at = None

    def _run(self):
        r, c = self.rng, self.clock
        created = r.choice([c.t + r.uniform(-5000, 300), c.t + r.uniform(-4, 60), (self.dispatched_at or c.t) + r.uniform(0, 30)])
        run = {"databaseId": r.choice([r.randrange(1, 6), r.randrange(1, 6), None, "x1", 2.5]), "status": r.choice(STATUSES),
               "conclusion": r.choice(CONCLUSIONS), "headSha": self.sha if r.random() < 0.85 else r.choice([OTHER, None, 5, self.sha.upper()]),
               "displayTitle": r.choice(["t", "", "\u00e4\u202e\x00", "x" * 500]), "workflowName": "ci", "url": "https://x/1",
               "createdAt": r.choice([iso(created)] * 6 + [None, "garbage", 12345, "", iso(created)[:-1] + "+99:99", "2026-13-45T00:00:00Z"]),
               "event": r.choice(EVENTS)}
        for key in list(run):
            if r.random() < 0.02:
                del run[key]
        return run

    def _consistent_finished(self):
        """A burst of finished runs, mostly good (this is what makes SUCCESS reachable), often spoiled in exactly one way."""
        base = self.dispatched_at if self.dispatched_at is not None else self.clock.t
        runs = [{"databaseId": i, "status": "completed", "conclusion": "success", "headSha": self.sha, "displayTitle": "t",
                 "workflowName": "ci", "url": "u", "createdAt": iso(base + self.rng.uniform(0, 5)), "event": "workflow_dispatch"}
                for i in range(1, self.rng.randrange(2, 4))]
        spoil = self.rng.choice(["none", "none", "foreign_only", "plus_foreign_success", "one_running", "one_failed", "one_cancelled",
                                 "too_old", "other_event", "one_too_old", "missing_conclusion", "empty"])
        victim = runs[self.rng.randrange(len(runs))]
        if spoil == "foreign_only":
            for run in runs:
                run["headSha"] = OTHER
        elif spoil == "plus_foreign_success":
            runs.append(dict(runs[0], databaseId=99, headSha=OTHER))
        elif spoil == "one_running":
            victim["status"], victim["conclusion"] = "in_progress", None
        elif spoil == "one_failed":
            victim["conclusion"] = "failure"
        elif spoil == "one_cancelled":
            victim["conclusion"] = "cancelled"
        elif spoil == "too_old":
            for run in runs:
                run["createdAt"] = iso(base - 3600)
        elif spoil == "other_event":
            for run in runs:
                run["event"] = "push"
        elif spoil == "one_too_old":
            victim["createdAt"] = iso(base - 3600)
        elif spoil == "missing_conclusion":
            victim.pop("conclusion")
        elif spoil == "empty":
            runs = []
        return runs

    def __call__(self, command):
        self.commands.append(list(command))
        r = self.rng
        if self.rng.random() < 0.3:
            self.clock.t += r.uniform(0, 3)
        roll = r.random()
        if command[1:3] != ["run", "list"]:  # a dispatch command (CLI fuzz): random outcome
            return r.choice([(0, "", ""), (1, "", "HTTP 422 nope"), (1, "", "HTTP 503"), (1, "", ""), (1, "", "not logged in")])
        if roll < 0.06:
            self.looks.append(None)
            raise subprocess.TimeoutExpired(command, r.choice([1, 30]))
        if roll < 0.10:
            self.looks.append(None)
            raise r.choice([FileNotFoundError("gh"), PermissionError("gh"), OSError("boom")])
        if roll < 0.18:
            self.looks.append(None)
            return r.choice([(1, "", "HTTP 429 rate limit"), (1, "", "secondary rate limit"), (1, "", "HTTP 502"), (4, "x", ""), (127, "", "")])
        if roll < 0.26:
            self.looks.append(None)
            return 0, r.choice(["", "{", "null", "{}", "[1,2]", "[null]", "\"x\"", "[[]]", "NaN", "[{\"a\":1}]x", "\u00ff\ud800"[:1], "[" * 2000]), ""
        if roll < 0.46:
            runs = self._consistent_finished()
        else:
            runs = [self._run() for _ in range(r.randrange(0, 5))]
        self.looks.append(runs)
        text = json.dumps(runs)
        return 0, text, ""


def oracle_considered(run_list, sha, dispatched_at):
    """The runs the watcher may answer for, from the documented rules only."""
    if not isinstance(run_list, list):
        return None
    runs = [x for x in run_list if isinstance(x, dict) and x.get("headSha") == sha]
    if dispatched_at is None:
        return runs
    out = []
    for x in runs:
        created = x.get("createdAt")
        if not isinstance(created, str):
            continue
        try:
            from datetime import datetime
            epoch = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
        if epoch < dispatched_at - w.DISPATCH_SKEW or x.get("event") not in (None, "workflow_dispatch"):
            continue
        out.append(x)
    return out


def finished_success(runs):
    return bool(runs) and all(x.get("status") == "completed" and x.get("conclusion") == "success" for x in runs)


def finished(runs):
    return bool(runs) and all(x.get("status") == "completed" for x in runs)


def damage(rng, path: Path):
    kind = rng.randrange(8)
    data = path.read_bytes() if path.exists() else b"{}"
    if kind == 0:
        path.write_bytes(data[:rng.randrange(len(data) + 1)])
    elif kind == 1:
        path.write_bytes(bytes(rng.randrange(256) for _ in range(rng.randrange(1, 200))))
    elif kind == 2:
        path.write_bytes(b"")
    elif kind == 3:
        path.write_text(rng.choice(["[]", "null", "5", "\"x\"", "{\"attempts\": \"3\"}", "{\"attempts\": true}", "{\"runs\": 5}",
                                    "{\"dispatch\": \"MAYBE\"}", "{\"status\": \"COMPLETED \"}", "{\"next_poll_at\": \"soon\"}",
                                    "{\"last_complete_ids\": 5}", "{\"attempts\": 1e400}", "{\"attempts\": -3, \"next_poll_at\": 1e999}",
                                    "{\"key\": [1], \"sha\": {}}", "{\"key\": \"other\"}", "{\"sha\": \"" + "c" * 40 + "\"}"]))
    elif kind == 4:
        flipped = bytearray(data)
        if flipped:
            flipped[rng.randrange(len(flipped))] ^= 1 << rng.randrange(8)
        path.write_bytes(bytes(flipped))
    elif kind == 5:
        path.write_text(json.dumps({"attempts": rng.choice([0, 3, 10 ** 9, -1]), "next_poll_at": rng.choice([None, T0 - 1e6, T0 + 1e9, 1e300]),
                                    "dispatch": rng.choice(["NONE", "DISPATCHED", "DISPATCHING"]), "dispatched_at": rng.choice([None, T0, 1e300, -1e300]),
                                    "runs": rng.choice([[], [1], [{"a": 1}]]), "last_complete_at": rng.choice([None, T0 + 1e300]),
                                    "last_complete_ids": rng.choice([None, [], ["1"], [1]]), "status": "WATCHING"}))
    elif kind == 6:
        path.write_bytes(data + b"\n{}")
    else:
        path.write_bytes(data.replace(b"\"", b"'", 1))


def leftovers(directory: Path):
    return [p.name for p in directory.iterdir() if ".take-" in p.name or p.name.endswith(".tmp") or p.name.endswith(".lock.x")]


def scenario(tmp_path, seed):
    rng = random.Random(f"k3-{seed}")
    clock = FuzzClock(rng)
    gh = FuzzGh(rng, clock)
    dispatch_mode = rng.random() < 0.5
    max_attempts = rng.randrange(1, 9)
    cfg = dict(base=rng.choice([1.0, 2.0, 5.0]), factor=rng.choice([1.0, 2.0, 7.5]), max_interval=rng.choice([1.0, 8.0, 60.0]),
               max_attempts=max_attempts, window=rng.choice([0.0, 5.0, 30.0, 120.0]), dispatch_grace=rng.choice([0.0, 20.0, 300.0]))
    if cfg["window"] == 0.0:
        cfg["window"] = 20.0  # window 0 means "until terminal"; max_attempts still bounds it
    backoff = w.Backoff(**cfg)
    dispatch_log = {"calls": 0, "open": 0}
    corrupted = False
    history, dispatched_at = [], None
    state_attempts_floor = 0
    path = None

    def dispatch():
        nonlocal dispatched_at
        dispatch_log["calls"] += 1
        gh.dispatched_at = clock.t
        outcome = rng.random()
        if outcome < 0.15:
            gh.dispatched_at = None
            raise RuntimeError("clean failure")
        dispatched_at = clock.t
        dispatch_log["open"] += 1
        if outcome < 0.25:
            raise w.AmbiguousDispatch("unknown")

    for call_no in range(rng.randrange(1, 7)):
        looks_before = len(gh.looks)
        before_dispatch = dispatch_log["calls"]
        before_terminal = None
        key = w.idempotency_key("WK-K3", SHA)
        path = w.state_path(tmp_path, key)
        if call_no and rng.random() < 0.3 and path.exists():
            damage(rng, path)
            corrupted = True
            # a damaged state may forget history: the oracle is off for the rest of this scenario
        if path.exists():
            try:
                before_terminal = json.loads(path.read_text()).get("status") if not corrupted else None
            except ValueError:
                before_terminal = None
        try:
            result = w.watch("WK-K3", SHA, tmp_path, backoff=backoff, dispatch=dispatch if dispatch_mode else None,
                             run_cmd=gh, clock=clock.time, sleep=clock.sleep)
        except w.AmbiguousDispatch:
            continue
        except RuntimeError as exc:  # the stub's clean dispatch failure
            assert str(exc) == "clean failure"
            continue
        except OSError:
            continue
        # ---- invariants of one call
        assert result["status"] in (w.COMPLETED, w.EXHAUSTED, w.UNCONFIRMED, w.WAITING, w.LOCKED, w.STATE_UNREADABLE), result["status"]
        assert result["exit_code"] in DOCUMENTED and result["exit_code"] == w.EXIT_CODES[result["outcome"]]
        json.dumps(result)
        calls_this = len(gh.looks) - looks_before
        assert result["polls_this_call"] == calls_this, (result["polls_this_call"], calls_this)
        assert calls_this <= max_attempts, (calls_this, max_attempts, corrupted)
        for command in gh.commands:
            assert command[:6] == ["gh", "run", "list", "--commit", SHA, "--limit"] and command[6] == str(w.LIST_LIMIT)
            assert command[7:9] == ["--json", w.FIELDS] and len(command) == 9, command
        assert leftovers(tmp_path) == [], leftovers(tmp_path)
        if before_terminal in (w.COMPLETED, w.EXHAUSTED, w.UNCONFIRMED):
            assert calls_this == 0 and result["status"] == before_terminal  # terminal: zero gh calls, same answer
        if result["status"] == w.STATE_UNREADABLE:
            assert calls_this == 0 and dispatch_log["calls"] == before_dispatch
            assert corrupted
        if result["status"] == w.LOCKED:
            assert calls_this == 0
        if path.exists() and not corrupted:
            assert isinstance(json.loads(path.read_text()), dict)
        # ---- the oracle: no false SUCCESS
        if result["outcome"] == "SUCCESS" and not corrupted:
            considered = [oracle_considered(look, SHA, dispatched_at if dispatch_mode else None) for look in gh.looks]
            last_usable = [c for c in considered if c is not None]
            assert last_usable and finished_success(last_usable[-1]), "SUCCESS without a finished+success last look"
            if not dispatch_mode:
                assert len(last_usable) >= 2 and finished(last_usable[-2]), "observed result from one look"
            else:
                assert dispatched_at is not None
    # across the whole scenario
    if not corrupted:
        assert dispatch_log["open"] <= 1, dispatch_log  # dispatched at most once unless the earlier attempts failed cleanly
        total_looks = len([x for x in gh.commands if x[1:3] == ["run", "list"]])
        assert total_looks <= max_attempts, (total_looks, max_attempts)
    return gh, dispatch_log


@pytest.mark.parametrize("seed", SEEDS)
def test_k3_random_gh_clock_and_state_damage_never_break_an_invariant(tmp_path, seed):
    scenario(tmp_path, seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_k3_a_monotone_clock_keeps_the_polls_inside_the_window(tmp_path, seed):
    """Without clock jumps the number of polls per call is bounded by the window (delay >= base >= 1 after the first poll)."""
    rng = random.Random(f"k3w-{seed}")

    class Plain(FuzzClock):
        def sleep(self, seconds):
            self.t += seconds

    clock = Plain(rng)
    gh = FuzzGh(rng, clock)
    window = rng.choice([5.0, 30.0, 200.0])
    backoff = w.Backoff(base=rng.choice([1.0, 3.0]), factor=rng.choice([1.0, 2.0]), max_interval=rng.choice([1.0, 20.0]), max_attempts=0, window=window)
    result = w.watch("WK-K3W", SHA, tmp_path, backoff=backoff, run_cmd=gh, clock=clock.time, sleep=clock.sleep)
    assert result["exit_code"] in DOCUMENTED
    # one immediate poll, then at least min(base, max_interval) apart, plus one edge poll; gh itself may add up to 3 s per call
    spacing = min(backoff.base, backoff.max_interval)
    assert len(gh.looks) <= window / spacing + 3 + (len(gh.looks) * 3.0) / spacing


@pytest.mark.parametrize("seed", SEEDS)
def test_k3_the_cli_with_random_arguments_and_a_random_gh_ends_in_a_documented_exit_code(tmp_path, seed, monkeypatch, capsys):
    rng = random.Random(f"k3c-{seed}")
    clock = FuzzClock(rng)
    gh = FuzzGh(rng, clock)
    monkeypatch.setitem(w.watch.__kwdefaults__, "run_cmd", gh)
    monkeypatch.setitem(w.watch.__kwdefaults__, "sleep", clock.sleep)
    monkeypatch.setitem(w.watch.__kwdefaults__, "clock", clock.time)
    monkeypatch.setattr(w.gh_dispatch, "__defaults__", (None, gh))
    monkeypatch.setattr(w, "default_run_cmd", gh)
    args = ["--workkey", rng.choice(["WK", "", "a/b", "\u00e4" * 300, "x y"]), "--sha", rng.choice([SHA, SHA.upper(), "abc", "", SHA[:-1], OTHER]),
            "--state-dir", rng.choice([str(tmp_path), str(tmp_path / "a" / "b"), str(tmp_path / "file")])]
    (tmp_path / "file").write_text("not a dir")
    for flag, values in [("--window", ["0", "5", "-1", "nan", "inf", "1e9", "x", "30"]), ("--base", ["1", "0.5", "-2", "nan", "1e9", "7"]),
                         ("--factor", ["1", "0.5", "2", "inf", "1e4", "3"]), ("--max-interval", ["1", "0", "9", "1e9"]),
                         ("--max-attempts", ["1", "3", "-1", "x", "5.5", "7"]), ("--repo", ["o/r", ""]), ("--ref", ["main", ""]),
                         ("--dispatch-workflow", ["ci.yml", ""]), ("--reset-state", [None]), ("--bogus", ["1"])]:
        if rng.random() < 0.45:
            args += [flag] if values == [None] else [flag, rng.choice(values)]
    rng.shuffle(args) if rng.random() < 0.1 else None  # sometimes a scrambled command line
    if "--max-attempts" not in args and "--reset-state" not in args:
        args += ["--max-attempts", "4"]  # keep every run finite; the default 64 is exercised by the unit tests
    code = w.main(args)
    captured = capsys.readouterr()
    assert code in DOCUMENTED | {2}, code
    if code != 2:
        json.loads(captured.out)  # exactly one JSON document on stdout
        assert "Traceback" not in captured.err


@pytest.mark.parametrize("attempts", [-1, -3, -(10 ** 9)])
def test_k3_f1_a_negative_attempt_counter_in_the_state_file_is_unreadable_not_a_way_around_max_attempts(tmp_path, attempts):
    """Found by the fuzz (state damage): attempts=-3 gave a call more polls than max_attempts allows."""
    gh = FuzzGh(random.Random(1), FuzzClock(random.Random(1)))
    backoff = w.Backoff(base=1, max_interval=1, max_attempts=2, window=30)
    path = w.state_path(tmp_path, w.idempotency_key("WK", SHA))
    path.write_text(json.dumps({"attempts": attempts, "status": "WATCHING", "dispatch": "NONE"}))
    result = w.watch("WK", SHA, tmp_path, backoff=backoff, run_cmd=gh, clock=FuzzClock(random.Random(1)).time, sleep=lambda s: None)
    assert result["status"] == w.STATE_UNREADABLE and gh.commands == []


@pytest.mark.parametrize("dispatch_mode", [False, True])
def test_k3_one_unfinished_run_among_finished_ones_never_completes(tmp_path, dispatch_mode):
    """Deterministic twin of a mutant the random fuzz only kills with ~1000 seeds ('any run completed' instead of 'all')."""
    from test_ci_watcher_v2 import Clock, Gh, run
    clock = Clock()
    mixed = [run("completed", "success", rid=1), run("in_progress", rid=2)]
    gh = Gh(mixed)
    result = w.watch("WK", SHA, tmp_path, backoff=w.Backoff(base=1, max_interval=1, max_attempts=6, window=60), run_cmd=gh,
                     dispatch=(lambda: None) if dispatch_mode else None, clock=clock.time, sleep=clock.sleep)
    assert result["status"] == w.EXHAUSTED and result["outcome"] == "EXHAUSTED" and len(gh.lists) == 6
