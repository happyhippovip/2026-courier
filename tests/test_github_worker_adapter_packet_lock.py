"""M06-03: one packet must never be worked by two adapters at once.

resume_pending() spawns an adapter per non-POSTED packet with no mutual
exclusion, so two resumers (or a resume racing a live adapter) start two
workers on one packet — proven in /tmp/m06-03-probe to double-spawn and
double-dispatch externally for the same dispatch_id.

The fix is a per-packet lock taken at run() entry: the loser defers
(return 0, work owned by the holder); a crashed holder's lock goes stale
and is stolen, so work is delayed but never lost.
"""
import json
import threading
import time
from pathlib import Path

from scripts import github_worker_adapter as adapter


def packet(**changes):
    value = {"goal_id": "goal-1", "task_id": "task-1", "attempt_id": "attempt-1", "dispatch_id": "dispatch-7",
             "worker_id": "GITHUB-HOSTED", "task_type": "report", "report": "hello"}
    value.update(changes)
    return value


def test_concurrent_runs_dispatch_exactly_once(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    # No gate: exactly one thread can hold the per-packet lock, so exactly
    # one dispatches regardless of interleaving.
    dispatches = []
    lock = threading.Lock()

    def fake_run_cmd(command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        assert command[0] == "gh", command
        if command[1:3] == ["workflow", "run"]:
            with lock:
                dispatches.append(1)
            return (0, "", "")
        if command[1:3] == ["run", "list"]:
            return (0, "[]", "")
        raise AssertionError(command)

    monkeypatch.setattr(adapter, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "POLL_SECONDS", 0)
    monkeypatch.setattr(adapter, "DISPATCH_GRACE_SECONDS", 0)
    errors = []

    def attempt():
        try:
            assert adapter.run(str(task_file)) == 0
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert dispatches == [1]
    assert not adapter.lock_path(task_file).exists()


def test_fresh_lock_defers_to_holder(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.lock_path(task_file).write_text(
        json.dumps({"pid": 999999, "started_at": time.time()}), encoding="utf-8")
    dispatches = []

    def fake_run_cmd(command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        if command[1:3] == ["workflow", "run"]:
            dispatches.append(1)
            return (0, "", "")
        if command[1:3] == ["run", "list"]:
            return (0, "[]", "")
        raise AssertionError(command)

    monkeypatch.setattr(adapter, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    assert adapter.run(str(task_file)) == 0
    assert dispatches == []
    assert adapter.lock_path(task_file).exists()


def test_stale_lock_is_stolen_and_released(tmp_path: Path, monkeypatch):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    adapter.lock_path(task_file).write_text(
        json.dumps({"pid": 999999, "started_at": time.time() - 9999}), encoding="utf-8")
    dispatches = []

    def fake_run_cmd(command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        if command[1:3] == ["workflow", "run"]:
            dispatches.append(1)
            return (0, "", "")
        if command[1:3] == ["run", "list"]:
            return (0, "[]", "")
        raise AssertionError(command)

    monkeypatch.setattr(adapter, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "POLL_SECONDS", 0)
    assert adapter.run(str(task_file)) == 0
    assert dispatches == [1]
    assert not adapter.lock_path(task_file).exists()


def test_bool_lock_timestamp_is_not_stolen(tmp_path: Path):
    """True is not a time. A bool started_at must not look ancient and be stolen."""
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    lock = adapter.lock_path(task_file)
    original = json.dumps({"pid": 999999, "started_at": True})
    lock.write_text(original, encoding="utf-8")
    owned = adapter.acquire_packet_lock(task_file)
    assert owned is False, lock.read_text(encoding="utf-8")
    assert lock.read_text(encoding="utf-8") == original
    false_body = json.dumps({"pid": 999999, "started_at": False})
    lock.write_text(false_body, encoding="utf-8")
    assert adapter.acquire_packet_lock(task_file) is False
    assert lock.read_text(encoding="utf-8") == false_body


def test_state_symlink_is_not_a_posted_result(tmp_path: Path, monkeypatch):
    """A symlinked state file must not count as an already posted result."""
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps(packet()), encoding="utf-8")
    outside = tmp_path / "outside-state.json"
    body = json.dumps({"dispatch_id": "dispatch-7", "status": "POSTED"})
    outside.write_text(body, encoding="utf-8")
    adapter.state_path(task_file).symlink_to(outside)
    dispatches = []

    def fake_run_cmd(command):
        if command[:2] == ["git", "branch"]:
            return (0, "main", "")
        if command[1:3] == ["workflow", "run"]:
            dispatches.append(1)
            return (0, "", "")
        if command[1:3] == ["run", "list"]:
            return (0, "[]", "")
        raise AssertionError(command)

    monkeypatch.setattr(adapter, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    monkeypatch.setattr(adapter, "POLL_SECONDS", 0)
    try:
        result = adapter.run(str(task_file))
    except ValueError as exc:
        assert "symlink" in str(exc).lower(), exc
    else:
        raise AssertionError(f"returned {result} dispatches={dispatches}")
    assert dispatches == []
    assert outside.read_text(encoding="utf-8") == body
