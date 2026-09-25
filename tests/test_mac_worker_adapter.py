"""Targeted test: mac worker adapter transport safety.

- Unsafe task_ids are refused before any path interpolation.
- Stale outbox results never bind to a new run.
- Timeout records FAILED atomically (previously crashed when
  results/incoming did not exist yet).
- Happy path delivers the worker result and cleans up the outbox.
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import mac_worker_adapter as adapter


def write_task(tmp_path, task_id="task-mac-1"):
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({"task_id": task_id, "goal_id": "g1"}))
    return task_file


def test_unsafe_task_id_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(adapter, "BASE_DIR", tmp_path / "mw")
    task_file = write_task(tmp_path, "../../evil")
    assert adapter.run(str(task_file)) == 2
    assert not (tmp_path / "mw").exists()


def test_timeout_records_failed_atomically(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(adapter, "BASE_DIR", tmp_path / "mw")
    monkeypatch.setattr(adapter.time, "sleep", lambda s: None)
    clock = iter([0.0, 400.0])
    monkeypatch.setattr(adapter.time, "time", lambda: next(clock))
    task_file = write_task(tmp_path)
    assert adapter.run(str(task_file)) == 1
    result = json.loads((tmp_path / "results" / "incoming" / "task-mac-1_result.json").read_text())
    assert result["status"] == "FAILED" and result["reason"] == "TIMEOUT"
    assert not list(tmp_path.glob("*.tmp"))


def test_stale_outbox_never_binds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(adapter, "BASE_DIR", tmp_path / "mw")
    monkeypatch.setattr(adapter.time, "sleep", lambda s: None)
    clock = iter([0.0, 400.0])
    monkeypatch.setattr(adapter.time, "time", lambda: next(clock))
    outbox = tmp_path / "mw" / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "task-mac-1_result.json").write_text(json.dumps({"stale": True}))
    task_file = write_task(tmp_path)
    assert adapter.run(str(task_file)) == 1  # timed out, did not take stale
    result = json.loads((tmp_path / "results" / "incoming" / "task-mac-1_result.json").read_text())
    assert result["reason"] == "TIMEOUT"


def test_happy_path_delivers_and_cleans_up(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(adapter, "BASE_DIR", tmp_path / "mw")
    task_file = write_task(tmp_path)

    def worker():
        import time as real_time
        real_time.sleep(3)
        (tmp_path / "mw" / "outbox" / "task-mac-1_result.json").write_text(
            json.dumps({"status": "SUCCESS"}))

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert adapter.run(str(task_file)) == 0
    finally:
        thread.join(timeout=30)
    delivered = json.loads((tmp_path / "results" / "incoming" / "task-mac-1_result.json").read_text())
    assert delivered["status"] == "SUCCESS"
    assert not (tmp_path / "mw" / "outbox" / "task-mac-1_result.json").exists()


def test_base_dir_is_script_relative():
    assert str(adapter.BASE_DIR).endswith("scripts/mac_worker")
