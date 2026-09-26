"""The GitHub dispatcher must persist the full dispatch identity durably
before any worker execution starts, and resume it after a crash."""
import importlib.util
import json
from pathlib import Path

import pytest

DISPATCHER = Path(__file__).resolve().parents[1] / "scripts" / "courier_github_dispatcher.py"
IDENTITY = ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id")


def load(monkeypatch, tmp_path):
    monkeypatch.setenv("COURIER_API_KEY", "dummy-test-key-not-real")
    monkeypatch.setenv("COURIER_GITHUB_DISPATCH_DIR", str(tmp_path / "dispatch"))
    spec = importlib.util.spec_from_file_location("gh_dispatcher_under_test", DISPATCHER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def packet(**over):
    task = {
        "goal_id": "goal-1",
        "task_id": "task-1",
        "attempt_id": "task-1:attempt:1",
        "dispatch_id": "dispatch-" + "a" * 32,
        "worker_id": "GITHUB-DISPATCHER",
        "type": "metadata",
    }
    task.update(over)
    return task


class Spawns:
    def __init__(self, fail=False):
        self.paths, self.fail = [], fail

    def __call__(self, argv, *a, **k):
        path = Path(argv[-1])
        # Identity must already be durable when execution starts.
        assert path.is_file()
        on_disk = json.loads(path.read_text())
        for field in IDENTITY:
            assert on_disk[field]
        if self.fail:
            raise OSError("simulated crash before adapter start")
        self.paths.append(path)
        class MockProcess:
            def __init__(self):
                self.pid = 99999
            def poll(self):
                return None
        return MockProcess()


def test_identity_persisted_before_adapter_starts(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    spawns = Spawns()
    monkeypatch.setattr(d.subprocess, "Popen", spawns)
    task = packet()
    assert d.handle_claimed_task(task) is True
    assert len(spawns.paths) == 1
    stored = json.loads(spawns.paths[0].read_text())
    assert {k: stored[k] for k in IDENTITY} == {k: task[k] for k in IDENTITY}
    assert spawns.paths[0].parent == tmp_path / "dispatch"
    assert not list((tmp_path / "dispatch").glob("*.tmp"))


@pytest.mark.parametrize("field", IDENTITY)
def test_missing_identity_never_starts_execution(monkeypatch, tmp_path, field):
    d = load(monkeypatch, tmp_path)
    spawns = Spawns()
    monkeypatch.setattr(d.subprocess, "Popen", spawns)
    assert d.handle_claimed_task(packet(**{field: ""})) is False
    assert spawns.paths == []
    assert not list((tmp_path / "dispatch").glob("*.json")) if (tmp_path / "dispatch").exists() else True


@pytest.mark.parametrize("bad", ["../../etc/x", "dispatch-../x", "dispatch-a/b", ""])
def test_unsafe_dispatch_id_is_rejected(monkeypatch, tmp_path, bad):
    d = load(monkeypatch, tmp_path)
    spawns = Spawns()
    monkeypatch.setattr(d.subprocess, "Popen", spawns)
    assert d.handle_claimed_task(packet(dispatch_id=bad)) is False
    assert spawns.paths == []


def test_crash_between_persist_and_start_is_resumed_once(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    monkeypatch.setattr(d.subprocess, "Popen", Spawns(fail=True))
    with pytest.raises(OSError):
        d.handle_claimed_task(packet())
    # Restart: the persisted packet is resumed exactly once, with the same identity.
    d2 = load(monkeypatch, tmp_path)
    spawns = Spawns()
    monkeypatch.setattr(d2.subprocess, "Popen", spawns)
    assert d2.resume_pending() == 1
    assert len(spawns.paths) == 1
    assert json.loads(spawns.paths[0].read_text())["dispatch_id"] == packet()["dispatch_id"]


def test_posted_dispatch_is_not_resumed(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    monkeypatch.setattr(d.subprocess, "Popen", Spawns())
    d.handle_claimed_task(packet())
    path = next((tmp_path / "dispatch").glob("*.json"))
    path.with_name(f"{path.stem}.github-worker-state.json").write_text(
        json.dumps({"dispatch_id": packet()["dispatch_id"], "status": "POSTED"}))
    spawns = Spawns()
    monkeypatch.setattr(d.subprocess, "Popen", spawns)
    assert d.resume_pending() == 0
    assert spawns.paths == []


def test_redelivered_same_dispatch_does_not_spawn_twice_in_one_process(monkeypatch, tmp_path):
    d = load(monkeypatch, tmp_path)
    spawns = Spawns()
    monkeypatch.setattr(d.subprocess, "Popen", spawns)
    assert d.handle_claimed_task(packet()) is True
    assert d.handle_claimed_task(packet()) is False
    assert len(spawns.paths) == 1


def test_adapter_restart_after_workflow_dispatch_does_not_redispatch(tmp_path, monkeypatch):
    import importlib
    adapter = importlib.import_module("scripts.github_worker_adapter")
    task_file = tmp_path / "t.json"
    task_file.write_text(json.dumps(packet()))
    # State recorded that the workflow was already dispatched; GitHub shows the run.
    adapter.write_state(task_file, {"dispatch_id": packet()["dispatch_id"], "status": "WAITING_FOR_WORKER"})
    calls = []
    monkeypatch.setattr(adapter, "find_run", lambda did: ("123", "in_progress"))
    monkeypatch.setattr(adapter, "run_cmd", lambda cmd: calls.append(cmd) or (0, "", ""))
    monkeypatch.setattr(adapter, "post_result", lambda res: None)
    monkeypatch.setattr(adapter, "LOCAL_WAIT_SECONDS", 0)
    assert adapter.run(str(task_file)) == 0
    assert not any(c[:3] == ["gh", "workflow", "run"] for c in calls)
