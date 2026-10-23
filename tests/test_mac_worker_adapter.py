import pytest; pytest.importorskip("fcntl")
import os
import json
import time
from unittest import mock
import pytest
from pathlib import Path

from scripts import mac_worker_adapter

def test_run_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac1", "goal_id": "g1"}, f)

    # Place the Mac result before run(). The adapter binds the time module, so
    # patching scripts.mac_worker_adapter.time.sleep replaces global time.sleep.
    # A thread still running from an earlier test then rewrites the outbox
    # after the adapter has removed it.
    outbox_file = Path("scripts/mac_worker/outbox/mac1_result.json")
    outbox_file.parent.mkdir(parents=True, exist_ok=True)
    with open(outbox_file, "w") as f:
        json.dump({"status": "SUCCESS"}, f)

    mac_worker_adapter.run(str(task_file))

    incoming = Path("results/incoming/mac1_result.json")
    assert incoming.exists()

    with open(incoming, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"

    assert not outbox_file.exists()


def test_run_timeout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("results/incoming").mkdir(parents=True, exist_ok=True)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac2", "goal_id": "g2"}, f)
        
    start_time = 0
    def mock_time():
        nonlocal start_time
        res = start_time
        start_time += 400
        return res
        
    with mock.patch("scripts.mac_worker_adapter.time.time", side_effect=mock_time):
        mac_worker_adapter.run(str(task_file))
        
    incoming = Path("results/incoming/mac2_result.json")
    assert incoming.exists()
    
    with open(incoming, "r") as f:
        res = json.load(f)
        assert res["status"] == "FAILED"
        assert res["reason"] == "TIMEOUT"


def test_main(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac3", "goal_id": "g3"}, f)
        
    import threading
    def background_writer():
        time.sleep(0.1)
        outbox_file = Path("scripts/mac_worker/outbox/mac3_result.json")
        outbox_file.parent.mkdir(parents=True, exist_ok=True)
        with open(outbox_file, "w") as f:
            json.dump({"status": "SUCCESS"}, f)
            
    t = threading.Thread(target=background_writer)
    t.start()
            
    import sys
    import runpy
    
    sys.argv = ["mac_worker_adapter.py", str(task_file)]
    runpy.run_path(str(Path(str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "mac_worker_adapter.py"))), run_name="__main__")
    t.join()
        
    incoming = Path("results/incoming/mac3_result.json")
    assert incoming.exists()

def test_task_id_does_not_escape_the_inbox(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mac_worker_adapter.time, "sleep", lambda _seconds: None)
    clock = {"now": 0}

    def fake_time():
        clock["now"] += 400
        return clock["now"]

    monkeypatch.setattr(mac_worker_adapter.time, "time", fake_time)
    task = tmp_path / "task.json"
    task.write_text(json.dumps({"task_id": "../../../outside", "goal_id": "SECRET-TASK"}), encoding="utf-8")
    try:
        mac_worker_adapter.run(str(task))
        err = None
    except ValueError as exc:
        err = str(exc)
    except OSError:
        err = None
    outside = tmp_path / "outside.json"
    body = outside.read_text(encoding="utf-8") if outside.exists() else ""
    assert (err, "SECRET-TASK" in body) == ("refusing an unsafe task id", False)

def test_task_file_does_not_follow_a_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mac_worker_adapter.time, "sleep", lambda _seconds: None)
    clock = {"now": 0}

    def fake_time():
        clock["now"] += 400
        return clock["now"]

    monkeypatch.setattr(mac_worker_adapter.time, "time", fake_time)
    outside = tmp_path / "outside-task.json"
    outside.write_text(json.dumps({"task_id": "mac-link", "goal_id": "SECRET-JOB"}), encoding="utf-8")
    task = tmp_path / "task.json"
    task.symlink_to(outside)
    try:
        mac_worker_adapter.run(str(task))
        err = None
    except ValueError as exc:
        err = str(exc)
    except OSError:
        err = None
    copied = Path("scripts/mac_worker/inbox/mac-link.json")
    body = copied.read_text(encoding="utf-8") if copied.exists() else ""
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "task.json").write_text(
        json.dumps({"task_id": "mac-parent", "goal_id": "SECRET-PARENT"}),
        encoding="utf-8",
    )
    linked = tmp_path / "linked-parent"
    linked.symlink_to(parent_outside)
    try:
        mac_worker_adapter.run(str(linked / "task.json"))
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    except OSError:
        err2 = None
    copied2 = Path("scripts/mac_worker/inbox/mac-parent.json")
    body2 = copied2.read_text(encoding="utf-8") if copied2.exists() else ""
    assert (err, "SECRET-JOB" in body, err2, "SECRET-PARENT" in body2) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
    )
    assert "SECRET-JOB" in outside.read_text(encoding="utf-8")

def test_inbox_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(mac_worker_adapter.time, "sleep", lambda _seconds: None)
    clock = {"now": 0}

    def fake_time():
        clock["now"] += 400
        return clock["now"]

    monkeypatch.setattr(mac_worker_adapter.time, "time", fake_time)

    def prepare(root: Path, task_id: str, marker: str) -> Path:
        monkeypatch.chdir(root)
        task = root / "task.json"
        task.write_text(json.dumps({"task_id": task_id, "goal_id": marker}), encoding="utf-8")
        Path("results/incoming").mkdir(parents=True, exist_ok=True)
        return task

    root = tmp_path / "file-case"
    root.mkdir()
    outside = tmp_path / "outside-inbox"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    task = prepare(root, "mac-inbox", "SECRET-INBOX")
    inbox = Path("scripts/mac_worker/inbox")
    inbox.parent.mkdir(parents=True)
    inbox.symlink_to(outside)
    outbox = Path("scripts/mac_worker/outbox")
    outbox.mkdir()
    (outbox / "mac-inbox_result.json").write_text('{"status":"SUCCESS"}\n', encoding="utf-8")
    try:
        mac_worker_adapter.run(str(task))
        err = None
    except ValueError as exc:
        err = str(exc)
    copied = outside / "mac-inbox.json"
    body = copied.read_text(encoding="utf-8") if copied.exists() else ""

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    parent_task = prepare(parent_root, "mac-parent", "SECRET-PARENT")
    worker = Path("scripts/mac_worker")
    worker.parent.mkdir(parents=True)
    worker.symlink_to(parent_outside)
    try:
        mac_worker_adapter.run(str(parent_task))
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    parent_copied = parent_outside / "inbox" / "mac-parent.json"
    parent_body = parent_copied.read_text(encoding="utf-8") if parent_copied.exists() else ""
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (err, "SECRET-INBOX" in body, err2, "SECRET-PARENT" in parent_body, names) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        ["keep.txt"],
    )


def test_outbox_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mac_worker_adapter.time, "sleep", lambda _seconds: None)
    clock = {"now": 0}

    def fake_time():
        clock["now"] += 400
        return clock["now"]

    monkeypatch.setattr(mac_worker_adapter.time, "time", fake_time)
    task = tmp_path / "task.json"
    task.write_text(json.dumps({"task_id": "mac-out", "goal_id": "LOCAL"}), encoding="utf-8")
    outside = tmp_path / "outside-outbox"
    outside.mkdir()
    secret = outside / "mac-out_result.json"
    secret.write_text('{"status":"SUCCESS","goal_id":"SECRET-OUTBOX"}\n', encoding="utf-8")
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    Path("scripts/mac_worker/inbox").mkdir(parents=True)
    Path("scripts/mac_worker/outbox").symlink_to(outside)
    Path("results/incoming").mkdir(parents=True)
    try:
        mac_worker_adapter.run(str(task))
        err = None
    except ValueError as exc:
        err = str(exc)
    incoming = Path("results/incoming/mac-out_result.json")
    body = incoming.read_text(encoding="utf-8") if incoming.exists() else ""
    assert (err, "SECRET-OUTBOX" in body, secret.exists()) == (
        "refusing to follow a symlink",
        False,
        True,
    )
    assert "SECRET-OUTBOX" in secret.read_text(encoding="utf-8")


def test_incoming_dir_does_not_follow_a_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(mac_worker_adapter.time, "sleep", lambda _seconds: None)
    clock = {"now": 0}

    def fake_time():
        clock["now"] += 400
        return clock["now"]

    monkeypatch.setattr(mac_worker_adapter.time, "time", fake_time)

    def prepare(root: Path) -> Path:
        monkeypatch.chdir(root)
        task = root / "task.json"
        task.write_text(json.dumps({"task_id": "mac-in", "goal_id": "LOCAL"}), encoding="utf-8")
        outbox = Path("scripts/mac_worker/outbox")
        outbox.mkdir(parents=True)
        (outbox / "mac-in_result.json").write_text(
            '{"status":"SUCCESS","goal_id":"SECRET-INCOMING"}\n',
            encoding="utf-8",
        )
        return task

    root = tmp_path / "file-case"
    root.mkdir()
    outside = tmp_path / "outside-incoming"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    task = prepare(root)
    incoming = Path("results/incoming")
    incoming.parent.mkdir(parents=True)
    incoming.symlink_to(outside)
    try:
        mac_worker_adapter.run(str(task))
        err = None
    except ValueError as exc:
        err = str(exc)
    copied = outside / "mac-in_result.json"
    body = copied.read_text(encoding="utf-8") if copied.exists() else ""

    parent_root = tmp_path / "parent-case"
    parent_root.mkdir()
    parent_outside = tmp_path / "parent-outside"
    parent_outside.mkdir()
    (parent_outside / "keep.txt").write_text("keep", encoding="utf-8")
    parent_task = prepare(parent_root)
    Path("results").symlink_to(parent_outside)
    try:
        mac_worker_adapter.run(str(parent_task))
        err2 = None
    except ValueError as exc:
        err2 = str(exc)
    parent_copied = parent_outside / "incoming" / "mac-in_result.json"
    parent_body = parent_copied.read_text(encoding="utf-8") if parent_copied.exists() else ""
    names = sorted(path.name for path in parent_outside.iterdir())
    assert (
        err,
        "SECRET-INCOMING" in body,
        err2,
        "SECRET-INCOMING" in parent_body,
        names,
    ) == (
        "refusing to follow a symlink",
        False,
        "refusing to follow a symlink",
        False,
        ["keep.txt"],
    )
