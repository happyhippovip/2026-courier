import pytest; pytest.importorskip("fcntl")
import json
import time
import pytest
from pathlib import Path

from scripts import mac_worker_adapter

def test_run_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    
    task_file = tmp_path / "task.json"
    with open(task_file, "w") as f:
        json.dump({"task_id": "mac1", "goal_id": "g1"}, f)
        
    def mock_sleep(seconds):
        outbox_file = Path("scripts/mac_worker/outbox/mac1_result.json")
        outbox_file.parent.mkdir(parents=True, exist_ok=True)
        with open(outbox_file, "w") as f:
            json.dump({"status": "SUCCESS"}, f)
            
    # Bind a private clock. Patching mac_worker_adapter.time.sleep replaces the
    # shared time module, so other threads in the suite re-enter mock_sleep and
    # truncate the outbox while it is being read.
    real_sleep = time.sleep
    monkeypatch.setattr(mac_worker_adapter, "time", type("Clock", (), {
        "time": staticmethod(time.time),
        "sleep": staticmethod(mock_sleep),
    })())
    assert time.sleep is real_sleep
    mac_worker_adapter.run(str(task_file))
        
    incoming = Path("results/incoming/mac1_result.json")
    assert incoming.exists()
    
    with open(incoming, "r") as f:
        res = json.load(f)
        assert res["status"] == "SUCCESS"
        
    outbox_file = Path("scripts/mac_worker/outbox/mac1_result.json")
    assert not outbox_file.exists()


def test_a_truncated_outbox_is_not_published(tmp_path, monkeypatch):
    """The reader must not treat 'file exists' as 'write finished'.

    open(path, 'w') creates an empty file before json.dump. Publishing that
    window is the empty mac1_result.json JSONDecodeError.
    """
    monkeypatch.chdir(tmp_path)
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({"task_id": "mac1", "goal_id": "g1"}), encoding="utf-8")
    outbox = Path("scripts/mac_worker/outbox/mac1_result.json")
    polls = {"n": 0}

    def mock_sleep(seconds):
        polls["n"] += 1
        outbox.parent.mkdir(parents=True, exist_ok=True)
        if polls["n"] == 1:
            with open(outbox, "w", encoding="utf-8"):
                pass  # the truncate window: exists, zero bytes
            return
        with open(outbox, "w", encoding="utf-8") as handle:
            json.dump({"status": "SUCCESS"}, handle)

    # Replace the adapter's clock binding only. Patching mac_worker_adapter.time.sleep
    # replaces the shared time module and lets other threads enter this writer.
    monkeypatch.setattr(mac_worker_adapter, "time", type("Clock", (), {
        "time": staticmethod(time.time),
        "sleep": staticmethod(mock_sleep),
    })())
    mac_worker_adapter.run(str(task_file))

    incoming = Path("results/incoming/mac1_result.json")
    assert incoming.exists()
    loaded = json.loads(incoming.read_text(encoding="utf-8"))
    assert loaded["status"] == "SUCCESS"
    assert polls["n"] >= 2


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
        
    monkeypatch.setattr(mac_worker_adapter, "time", type("Clock", (), {
        "time": staticmethod(mock_time),
        "sleep": staticmethod(time.sleep),
    })())
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
