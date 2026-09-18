from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts import courier_github_dispatcher as dispatcher


class FinishedProcess:
    def __init__(self, returncode):
        self.returncode = returncode

    def poll(self):
        return self.returncode


def test_waiting_adapter_is_reentered_without_second_claim(monkeypatch):
    replacement = FinishedProcess(None)
    launched = []
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda task_file: launched.append(task_file) or replacement,
    )
    active = {
        "task-1": {
            "process": FinishedProcess(dispatcher.WAITING_EXIT_CODE),
            "task_file": "/tmp/task-1.json",
        }
    }

    dispatcher.reap_adapters(active)

    assert launched == ["/tmp/task-1.json"]
    assert active["task-1"]["process"] is replacement


def test_terminal_adapter_is_reaped_and_owned_files_are_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("must not restart terminal adapter")),
    )
    task_file = tmp_path / "task.json"
    state_file = tmp_path / "task.github-worker-state.json"
    task_file.write_text("{}", encoding="utf-8")
    state_file.write_text("{}", encoding="utf-8")
    active = {
        "task-1": {
            "process": FinishedProcess(0),
            "task_file": str(task_file),
        }
    }

    dispatcher.reap_adapters(active)

    assert active == {}
    assert not task_file.exists()
    assert not state_file.exists()


def test_failed_adapter_gets_bounded_recovery(monkeypatch):
    replacement = FinishedProcess(None)
    launched = []
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda task_file: launched.append(task_file) or replacement,
    )
    active = {
        "task-1": {
            "process": FinishedProcess(1),
            "task_file": "/tmp/task-1.json",
            "retries": 0,
        }
    }

    dispatcher.reap_adapters(active)

    assert launched == ["/tmp/task-1.json"]
    assert active["task-1"]["process"] is replacement
    assert active["task-1"]["retries"] == 1


def test_failed_adapter_stops_after_bounded_recovery(monkeypatch):
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("retry bound exceeded")),
    )
    active = {
        "task-1": {
            "process": FinishedProcess(1),
            "task_file": "/tmp/task-1.json",
            "retries": dispatcher.MAX_ADAPTER_RESTARTS,
        }
    }

    dispatcher.reap_adapters(active)

    assert active == {}


def test_task_file_path_is_confined_and_does_not_use_untrusted_task_id(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))

    path = Path(
        dispatcher.task_file_path(
            {"task_id": "../../escape", "dispatch_id": "dispatch-safe"}
        )
    )

    assert path.parent == tmp_path
    assert path.name.startswith("courier-github-")
    assert "escape" not in path.name


def test_task_file_path_requires_dispatch_identity():
    with pytest.raises(ValueError, match="dispatch_id"):
        dispatcher.task_file_path({"task_id": "task-1"})


def test_persist_task_file_atomically_materializes_exact_packet(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    task = {"task_id": "task-1", "dispatch_id": "dispatch-1"}

    path = Path(dispatcher.persist_task_file(task))

    assert json.loads(path.read_text(encoding="utf-8")) == task
    assert list(tmp_path.glob(".*.tmp")) == []


def test_conflicting_task_packet_never_replaces_previous_packet(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    original = {"task_id": "task-1", "dispatch_id": "dispatch-1", "value": "old"}
    path = Path(dispatcher.persist_task_file(original))

    with pytest.raises(RuntimeError, match="conflicting TaskPacket"):
        dispatcher.persist_task_file({**original, "value": "new"})

    assert json.loads(path.read_text(encoding="utf-8")) == original
    assert list(tmp_path.glob(".*.tmp")) == []


def test_concurrent_identical_task_packet_materialization_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    task = {"task_id": "task-1", "dispatch_id": "dispatch-1", "value": "same"}

    with ThreadPoolExecutor(max_workers=16) as pool:
        paths = list(pool.map(lambda _: dispatcher.persist_task_file(task), range(64)))

    assert len(set(paths)) == 1
    assert json.loads(Path(paths[0]).read_text(encoding="utf-8")) == task
    assert list(tmp_path.glob(".*.tmp")) == []


def test_dispatcher_restart_resumes_single_durable_task(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    task = {"task_id": "task-1", "dispatch_id": "dispatch-1"}
    task_file = dispatcher.persist_task_file(task)
    launched = []
    process = FinishedProcess(None)
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda path: launched.append(path) or process,
    )

    recovered = dispatcher.recover_adapters()

    assert launched == [task_file]
    assert recovered["task-1"]["process"] is process
    assert recovered["task-1"]["task_file"] == task_file


def test_dispatcher_restart_cleans_posted_checkpoint_without_replay(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    task = {"task_id": "task-1", "dispatch_id": "dispatch-1"}
    task_file = Path(dispatcher.persist_task_file(task))
    state_file = task_file.with_name(f"{task_file.stem}.github-worker-state.json")
    state_file.write_text(json.dumps({"status": "POSTED"}), encoding="utf-8")
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("posted task must not replay")),
    )

    assert dispatcher.recover_adapters() == {}
    assert not task_file.exists()
    assert not state_file.exists()


def test_dispatcher_restart_fails_closed_on_multiple_unfinished_tasks(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    dispatcher.persist_task_file({"task_id": "task-1", "dispatch_id": "dispatch-1"})
    dispatcher.persist_task_file({"task_id": "task-2", "dispatch_id": "dispatch-2"})
    monkeypatch.setattr(
        dispatcher,
        "launch_adapter",
        lambda _: (_ for _ in ()).throw(AssertionError("ambiguous recovery must not execute")),
    )

    with pytest.raises(RuntimeError, match="multiple unfinished"):
        dispatcher.recover_adapters()


def test_dispatcher_restart_fails_closed_on_corrupt_durable_task(monkeypatch, tmp_path):
    monkeypatch.setattr(dispatcher.tempfile, "gettempdir", lambda: str(tmp_path))
    (tmp_path / "courier-github-corrupt.json").write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid persisted GitHub task"):
        dispatcher.recover_adapters()
