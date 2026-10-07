"""M06-02: a crash around the external `gh` dispatch must neither duplicate
nor lose the dispatch.

run() used to dispatch and only then record WAITING. A crash in between left
no state, so the resume dispatched a SECOND external run for the same
dispatch_id — after which find_run() sees multiple title matches and raises
forever (duplicate effect + permanently stuck task; proven in
/tmp/m06-02-probe/probe_dispatch_crash_window.py with stubbed externals).

The fix brackets the dispatch: a DISPATCHING marker (with timestamp) is
recorded first, WAITING confirms. A resume with a fresh marker adopts the
run when it appears within grace instead of redispatching; a stale marker
with no run dispatches exactly once (a crash before any marker still takes
the fresh-admission path, unchanged).
"""
import json
import time
from pathlib import Path

from scripts import github_worker_adapter as adapter


def packet(**changes):
    value = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "attempt-1", "dispatch_id": "dispatch-9",
             "worker_id": "GITHUB-HOSTED", "task_type": "report", "report": "hello"}
    value.update(changes)
    return value


class Gh:
    """Stubbed gh/git surface: counts external dispatches, replays a run feed."""

    def __init__(self, run_feed):
        self.dispatches = 0
        self.run_feed = list(run_feed)
        self.calls = 0

    def __call__(self, command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        assert command[0] == "gh", command
        if command[1:3] == ["workflow", "run"]:
            self.dispatches += 1
            return (0, "", "")
        if command[1:3] == ["run", "list"]:
            self.calls += 1
            if self.run_feed:
                return (0, json.dumps(self.run_feed.pop(0)), "")
            return (0, "[]", "")
        raise AssertionError(f"unexpected command: {command}")


def completed_run():
    return [{"databaseId": 7, "status": "queued", "displayTitle": "Courier dispatch dispatch-9"}]


def test_resume_adopts_run_instead_of_redispatching(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    # First admission sees no run; the run appears on the second listing
    # (GitHub list latency). Crash once on the WAITING confirmation write.
    gh = Gh(run_feed=[[], completed_run()])
    monkeypatch.setattr(adapter, "run_cmd", gh)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "POLL_SECONDS", 0)
    monkeypatch.setattr(adapter, "DISPATCH_GRACE_SECONDS", 60)
    real_write_state = adapter.write_state

    def crash_on_first_waiting(task_file_arg, state):
        if state.get("status") == "WAITING_FOR_WORKER":
            monkeypatch.setattr(adapter, "write_state", real_write_state)
            raise OSError("simulated crash after gh dispatch, before WAITING record")
        return real_write_state(task_file_arg, state)

    monkeypatch.setattr(adapter, "write_state", crash_on_first_waiting)
    try:
        adapter.run(str(task_file))
    except OSError:
        pass
    else:
        raise AssertionError("expected the staged crash to propagate")
    assert gh.dispatches == 1

    assert adapter.run(str(task_file)) == 0
    assert gh.dispatches == 1, "resume must adopt the run, not dispatch twice"


def test_stale_marker_without_run_dispatches_exactly_once(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    # A DISPATCHING marker older than grace with no run anywhere: the first
    # dispatch never happened (crash before the `gh` call), so the resume
    # owes exactly one dispatch — and must not spin without dispatching.
    adapter.write_state(task_file, {"dispatch_id": "dispatch-9", "status": "DISPATCHING",
                                    "dispatched_at": time.time() - 9999})
    gh = Gh(run_feed=[])
    monkeypatch.setattr(adapter, "run_cmd", gh)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "POLL_SECONDS", 0)
    monkeypatch.setattr(adapter, "DISPATCH_GRACE_SECONDS", 60)
    assert adapter.run(str(task_file)) == 0
    assert gh.dispatches == 1
    assert json.loads(adapter.state_path(task_file).read_text(encoding="utf-8"))["status"] == "WAITING_FOR_WORKER"
