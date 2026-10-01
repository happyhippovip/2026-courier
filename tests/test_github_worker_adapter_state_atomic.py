"""M06-05: adapter state writes must be atomic.

write_state() was a plain write_text (truncate + write). A kill in between
leaves a permanently torn state file; every future run() crashes with
JSONDecodeError (fail-closed) while resume keeps respawning into the crash —
proven in /tmp/m06-05-probe/probe_torn_state_loop.py.

The fix publishes via a thread-unique tmp + fsync + os.replace, so readers
only ever see complete state or nothing.
"""
import json
import os
import threading
from pathlib import Path

import pytest

from scripts import github_worker_adapter as adapter


def packet(**changes):
    value = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "attempt-1", "dispatch_id": "dispatch-6",
             "worker_id": "GITHUB-HOSTED", "task_type": "report", "report": "hi"}
    value.update(changes)
    return value


def test_corrupt_state_never_dispatches(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.state_path(task_file).write_text("", encoding="utf-8")

    def fail_on_dispatch(command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        if command[1:3] == ["workflow", "run"]:
            pytest.fail("must not dispatch on corrupt state")
        if command[1:3] == ["run", "list"]:
            return (0, "[]", "")
        raise AssertionError(command)

    monkeypatch.setattr(adapter, "run_cmd", fail_on_dispatch)
    with pytest.raises(json.JSONDecodeError):
        adapter.run(str(task_file))


def test_interrupted_publish_leaves_prior_state_intact(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.write_state(task_file, {"dispatch_id": "dispatch-6", "status": "WAITING_FOR_WORKER"})
    before = adapter.state_path(task_file).read_text(encoding="utf-8")

    real_replace = os.replace

    def crash_on_publish(src, dst):
        assert Path(src).is_file()
        raise OSError("simulated crash between tmp write and publish")

    monkeypatch.setattr(os, "replace", crash_on_publish)
    with pytest.raises(OSError, match="simulated crash"):
        adapter.write_state(task_file, {"dispatch_id": "dispatch-6", "status": "POSTED"})
    # Prior confirmed state is untouched; the staged tmp holds the complete
    # new payload (a later run can republish instead of losing it).
    assert adapter.state_path(task_file).read_text(encoding="utf-8") == before
    staged = list(tmp_path.glob("*.statetmp"))
    assert len(staged) == 1
    assert json.loads(staged[0].read_text(encoding="utf-8"))["status"] == "POSTED"
    real_replace(staged[0], adapter.state_path(task_file))


def test_concurrent_writes_never_tear_reads(tmp_path: Path):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    errors = []

    def writer(n):
        try:
            for _ in range(50):
                adapter.write_state(task_file, {"dispatch_id": "dispatch-6", "n": n})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def reader():
        try:
            for _ in range(200):
                path = adapter.state_path(task_file)
                if path.is_file():
                    json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert not list(tmp_path.glob("*.statetmp"))
