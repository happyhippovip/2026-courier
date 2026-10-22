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
