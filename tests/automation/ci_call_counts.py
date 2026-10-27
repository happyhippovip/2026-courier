"""Call-count scenarios S1-S7: OLD polling of scripts/github_worker_adapter.py vs the new
tools/automation/ci_watcher_v2.py, both against the same kind of gh stub with a fake clock.

Deterministic: no real sleeping, no network, no real GitHub, no model. Not a test file itself
(imported by test_ci_watcher_v2.py); `python3 tests/automation/ci_call_counts.py` prints JSON.

Differences that are NOT hidden: the old adapter also dispatches, downloads and POSTs the result
(git/api/workflow_run/run_download calls are counted in its total); the new watcher only
dispatches (optional) and lists. `run_list` is the like-for-like number.
"""
import json
import shutil
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for extra in (ROOT, ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from tools.automation import ci_watcher_v2 as watcher  # noqa: E402

SHA = "a" * 40
OTHER_SHA = "b" * 40

# Review T-2: scenarios whose old and new call counts do NOT measure the same thing. They stay in the JSON,
# flagged, and are excluded from the comparable sums.
NOT_COMPARABLE = {
    "S4_completed_run_consumer_fails_then_rerun":
        "old run includes the download + POST consumer step and its failed attempt; the new watcher has no consumer step",
    "S6_dispatching_marker_run_appears_late":
        "old waits one 60s window and gives up; the new watcher is given a 200s window, so both spend a different waiting budget",
}

_TEMP_DIRS = []


def _mkdtemp(prefix):
    path = tempfile.mkdtemp(prefix=prefix)
    _TEMP_DIRS.append(path)
    return Path(path)


def cleanup_temp_dirs():
    """Review B4: the harness removes every temp directory it created."""
    while _TEMP_DIRS:
        shutil.rmtree(_TEMP_DIRS.pop(), ignore_errors=True)


class Clock:
    def __init__(self):
        self.t = 0.0
        self.base = 1_800_000_000.0

    def sleep(self, seconds):
        self.t += max(0.0, seconds)

    def monotonic(self):
        return self.t

    def time(self):
        return self.base + self.t


class FakeGh:
    def __init__(self, clock, title="Courier dispatch x", appear_after=2.0, complete_after=None, noise=30):
        self.clock, self.title, self.appear_after = clock, title, appear_after
        self.complete_after, self.noise = complete_after, noise
        self.dispatched_at = None
        self.counts = {"run_list": 0, "workflow_run": 0, "run_download": 0, "api": 0, "git": 0}
        self.list_limits = []
        self.first_seen_at = None

    def _our_run(self):
        if self.dispatched_at is None:
            return None
        age = self.clock.t - self.dispatched_at
        if age < self.appear_after:
            return None
        status, conclusion = "queued", None
        if self.complete_after is not None and age >= self.complete_after:
            status, conclusion = "completed", "success"
        elif age >= self.appear_after + 8:
            status = "in_progress"
        appeared = self.clock.base + self.dispatched_at + self.appear_after
        return {"databaseId": 5000, "status": status, "conclusion": conclusion, "headSha": SHA,
                "displayTitle": self.title, "workflowName": "ci", "url": "https://example.invalid/runs/5000",
                "event": "workflow_dispatch",
                "createdAt": datetime.fromtimestamp(appeared, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    def __call__(self, command):
        if command[0] == "git":
            self.counts["git"] += 1
            return 0, "main", ""
        if command[1:3] == ["workflow", "run"]:
            self.counts["workflow_run"] += 1
            self.dispatched_at = self.clock.t
            return 0, "", ""
        if command[1] == "api":
            self.counts["api"] += 1
            return 0, SHA, ""
        if command[1:3] == ["run", "list"]:
            self.counts["run_list"] += 1
            limit = int(command[command.index("--limit") + 1])
            self.list_limits.append(limit)
            runs = []
            ours = self._our_run()
            if ours:
                runs.append(ours)
                if self.first_seen_at is None:
                    self.first_seen_at = self.clock.t
            runs += [{"databaseId": 100 + i, "status": "completed", "conclusion": "success", "headSha": OTHER_SHA,
                      "displayTitle": f"Courier dispatch other-{i}"} for i in range(self.noise)]
            if "--commit" in command:  # real gh filters server-side
                want = command[command.index("--commit") + 1]
                runs = [r for r in runs if r["headSha"] == want]
            return 0, json.dumps(runs[:limit]), ""
        raise AssertionError(f"unexpected command {command}")


def _row(name, desc, gh, clock, **extra):
    row = {"scenario": name, "description": desc, "not_comparable": name in NOT_COMPARABLE,
           "not_comparable_reason": NOT_COMPARABLE.get(name), "gh_calls": dict(gh.counts), "gh_total": sum(gh.counts.values()),
           "list_limits": sorted(set(gh.list_limits)), "fake_seconds": round(clock.t, 1)}
    row.update(extra)
    return row


# ----------------------------------------------------------------------------- NEW
def run_new():
    try:
        return _run_new()
    finally:
        cleanup_temp_dirs()


def _run_new():
    rows = []

    def setup(**kw):
        clock = Clock()
        return clock, FakeGh(clock, **kw), _mkdtemp("ciw-")

    def call(clock, gh, state_dir, workkey, window=60.0, dispatch=True, **cfg):
        def do_dispatch():
            gh.dispatched_at = clock.t
            gh.counts["workflow_run"] += 1
        return watcher.watch(workkey, SHA, state_dir, backoff=watcher.Backoff(window=window, **cfg),
                             dispatch=do_dispatch if dispatch else None, run_cmd=gh, clock=clock.time, sleep=clock.sleep)

    clock, gh, d = setup(complete_after=50)
    r = call(clock, gh, d, "S1")
    rows.append(_row("S1_fresh_dispatch_completes_at_50s", "fresh, run visible +2s, completes +50s, one 60s window", gh, clock,
                     final_state=r["status"], outcome=r["outcome"]))

    clock, gh, d = setup()
    r = call(clock, gh, d, "S2")
    rows.append(_row("S2_one_60s_window_run_never_completes", "fresh, run never completes in the 60s window", gh, clock,
                     final_state=r["status"]))

    clock, gh, d = setup()
    gh.dispatched_at = -10.0
    key = watcher.idempotency_key("S3", SHA)
    watcher.write_state(watcher.state_path(d, key), {"key": key, "sha": SHA, "workkey": "S3", "status": "WATCHING", "attempts": 0,
                                                    "next_poll_at": None, "runs": [], "dispatch": "DISPATCHED"})
    r = call(clock, gh, d, "S3", dispatch=False)
    rows.append(_row("S3_resume_waiting_state_in_progress", "restart with persisted WATCHING state, run in progress, 60s window", gh, clock,
                     final_state=r["status"]))

    clock, gh, d = setup(complete_after=0.0)
    gh.dispatched_at = -100.0
    r1 = call(clock, gh, d, "S4", dispatch=False)
    first = gh.counts["run_list"]
    r2 = call(clock, gh, d, "S4", dispatch=False)  # consumer failed after the result; watcher is re-run
    rows.append(_row("S4_completed_run_consumer_fails_then_rerun",
                     "completed run seen, consumer fails afterwards, watcher re-run (old: download+POST fail then resume)", gh, clock,
                     final_state=r2["status"], run_list_before_rerun=first))

    clock, gh, d = setup(complete_after=0.0)
    key = watcher.idempotency_key("S5", SHA)
    watcher.write_state(watcher.state_path(d, key), {"key": key, "sha": SHA, "workkey": "S5", "status": "COMPLETED", "attempts": 3,
                                                    "runs": [], "conclusion": "success", "dispatch": "DISPATCHED"})
    r = call(clock, gh, d, "S5", dispatch=False)
    rows.append(_row("S5_already_posted", "terminal state present, watcher restarted", gh, clock, final_state=r["status"]))

    clock, gh, d = setup(appear_after=100.0)
    gh.dispatched_at = 0.0
    clock.t = 1.0
    key = watcher.idempotency_key("S6", SHA)
    watcher.write_state(watcher.state_path(d, key), {"key": key, "sha": SHA, "workkey": "S6", "status": "WATCHING", "attempts": 0,
                                                    "next_poll_at": None, "runs": [], "dispatch": "DISPATCHING",
                                                    "dispatched_at": clock.time()})
    r = call(clock, gh, d, "S6", window=200.0, dispatch=True)
    rows.append(_row("S6_dispatching_marker_run_appears_late",
                     "DISPATCHING marker 1s old, run listed only after 100s, window 200s (no second dispatch)", gh, clock,
                     final_state=r["status"], first_seen_at=gh.first_seen_at))

    clock, gh, d = setup(complete_after=1500)
    r = call(clock, gh, d, "S7", window=1800.0)
    rows.append(_row("S7_long_window_1800s_run_completes_at_1500s", "window=1800s, run completes +1500s", gh, clock,
                     final_state=r["status"], outcome=r["outcome"]))
    return rows


# ----------------------------------------------------------------------------- OLD
def run_old():
    try:
        return _run_old()
    finally:
        cleanup_temp_dirs()


def _run_old():
    """Same stub shape against the unchanged scripts/github_worker_adapter.py (the old polling)."""
    from scripts import github_worker_adapter as adapter
    from scripts.integration_contract import canonical_result_id

    saved = {k: getattr(adapter, k) for k in ("time", "run_cmd", "post_result", "LOCAL_WAIT_SECONDS", "POLL_SECONDS",
                                               "DISPATCH_GRACE_SECONDS")}

    class OldGh(FakeGh):
        def __init__(self, clock, dispatch_id, **kw):
            super().__init__(clock, title=f"Courier dispatch {dispatch_id}", **kw)
            self.dispatch_id = dispatch_id

        def __call__(self, command):
            if command[1:3] == ["run", "download"]:
                self.counts["run_download"] += 1
                directory = Path(command[command.index("--dir") + 1])
                directory.mkdir(parents=True, exist_ok=True)
                result = {"goal_id": "g", "task_id": "t", "attempt_id": "a", "dispatch_id": self.dispatch_id,
                          "worker_id": "GITHUB-HOSTED", "run_id": "5000", "run_attempt": "1", "status": "FAILED",
                          "operation": "report", "artifacts": []}
                result["result_id"] = canonical_result_id(result)
                (directory / f"result_{self.dispatch_id}.json").write_text(json.dumps(result), encoding="utf-8")
                return 0, "", ""
            return super().__call__(command)

    posted = []

    def setup(dispatch_id, **kw):
        clock = Clock()
        gh = OldGh(clock, dispatch_id, **kw)
        adapter.time = types.SimpleNamespace(sleep=clock.sleep, monotonic=clock.monotonic, time=clock.time)
        adapter.run_cmd = gh
        adapter.post_result = posted.append
        adapter.LOCAL_WAIT_SECONDS, adapter.POLL_SECONDS, adapter.DISPATCH_GRACE_SECONDS = 60, 5, 300
        tf = _mkdtemp("ciold-") / f"{dispatch_id}.json"
        tf.write_text(json.dumps({"goal_id": "g", "task_id": "t", "attempt_id": "a", "dispatch_id": dispatch_id,
                                  "worker_id": "GITHUB-HOSTED", "task_type": "report", "report": "x"}), encoding="utf-8")
        return clock, gh, tf

    rows = []
    try:
        clock, gh, tf = setup("dispatch-s1", complete_after=50)
        adapter.run(str(tf))
        rows.append(_row("S1_fresh_dispatch_completes_at_50s", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s2")
        adapter.run(str(tf))
        rows.append(_row("S2_one_60s_window_run_never_completes", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s3")
        gh.dispatched_at = -10.0
        adapter.write_state(tf, {"dispatch_id": "dispatch-s3", "run_id": "5000", "status": "WAITING_FOR_WORKER"})
        adapter.run(str(tf))
        rows.append(_row("S3_resume_waiting_state_in_progress", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s4", complete_after=0.0)
        gh.dispatched_at = -100.0
        boom = {"n": 0}

        def failing_post(result):
            boom["n"] += 1
            if boom["n"] == 1:
                raise RuntimeError("simulated POST outage")
            posted.append(result)

        adapter.post_result = failing_post
        adapter.write_state(tf, {"dispatch_id": "dispatch-s4", "run_id": "5000", "status": "WAITING_FOR_WORKER"})
        try:
            adapter.run(str(tf))
        except RuntimeError:
            pass
        adapter.run(str(tf))
        rows.append(_row("S4_completed_run_consumer_fails_then_rerun", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s5", complete_after=0.0)
        adapter.write_state(tf, {"dispatch_id": "dispatch-s5", "status": "POSTED", "run_id": "5000"})
        adapter.run(str(tf))
        rows.append(_row("S5_already_posted", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s6", appear_after=100.0)
        gh.dispatched_at = 0.0
        clock.t = 1.0
        adapter.write_state(tf, {"dispatch_id": "dispatch-s6", "status": "DISPATCHING", "dispatched_at": clock.time()})
        adapter.run(str(tf))
        rows.append(_row("S6_dispatching_marker_run_appears_late", "old", gh, clock))

        clock, gh, tf = setup("dispatch-s7", complete_after=1500)
        adapter.LOCAL_WAIT_SECONDS = 1800
        adapter.run(str(tf))
        rows.append(_row("S7_long_window_1800s_run_completes_at_1500s", "old", gh, clock))
    finally:
        for k, v in saved.items():
            setattr(adapter, k, v)
    return rows


def summarize(old_rows, new_rows):
    """Total gh calls (old vs new) over all scenarios, over the comparable ones, and over the comparable ones
    without the long S7 window (the threshold must not hold only because of S7)."""
    def total(rows, keep):
        return sum(r["gh_total"] for r in rows if keep(r))
    everything = lambda r: True
    comparable = lambda r: not r["not_comparable"]
    no_s7 = lambda r: not r["not_comparable"] and not r["scenario"].startswith("S7_")
    out = {}
    for label, keep in (("all_scenarios", everything), ("comparable", comparable), ("comparable_without_S7", no_s7)):
        out[label] = {"old": total(old_rows, keep), "new": total(new_rows, keep)}
    out["not_comparable_scenarios"] = sorted(r["scenario"] for r in new_rows if r["not_comparable"])
    return out


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    out = {"old": run_old(), "new": run_new()}
    for which in ("old", "new"):
        for row in out[which]:
            print(json.dumps({"code": which, **row}, sort_keys=True))
    print(json.dumps({"summary": summarize(out["old"], out["new"])}, sort_keys=True))
