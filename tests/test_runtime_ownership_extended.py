import os
import json
import psutil
import pytest
from courier_runtime.ownership import OwnedProcess, Registry, is_same_process, terminate_owned


def test_registry_empty_and_corrupt(tmp_path):
    path = tmp_path / "owned.json"
    registry = Registry(str(path))
    # File not found returns empty list
    assert registry.load() == []
    assert registry.owned() == []

    # Write corrupt JSON
    path.write_text("{corrupt-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        registry.load()


def test_registry_idempotent_add(tmp_path):
    path = tmp_path / "owned.json"
    registry = Registry(str(path))

    rec = OwnedProcess(pid=12345, create_time=1000.0, workkey="wk-1", owner="test", recorded_at=1000.0)
    registry.add(rec)
    assert len(registry.load()) == 1

    # Adding exact same pid and create_time replaces/deduplicates
    rec2 = OwnedProcess(pid=12345, create_time=1000.0, workkey="wk-1-updated", owner="test-2", recorded_at=1010.0)
    registry.add(rec2)
    loaded = registry.load()
    assert len(loaded) == 1
    assert loaded[0].workkey == "wk-1-updated"
    assert loaded[0].owner == "test-2"


def test_terminate_owned_nonexistent_pid():
    rec = OwnedProcess(pid=9999999, create_time=1000.0, workkey="wk-ghost", owner="test", recorded_at=1000.0)
    assert not is_same_process(rec)
    receipt = terminate_owned(rec)
    assert receipt["result"] == "NOT_RUNNING"
    assert receipt["action"] == "NONE"
    assert receipt["terminated"] == []
    assert receipt["still_alive"] == []


def test_registry_stop_all(tmp_path):
    path = tmp_path / "owned.json"
    registry = Registry(str(path))

    rec1 = OwnedProcess(pid=9999991, create_time=1000.0, workkey="wk-1", owner="test", recorded_at=1000.0)
    rec2 = OwnedProcess(pid=9999992, create_time=1000.0, workkey="wk-2", owner="test", recorded_at=1000.0)
    registry.add(rec1)
    registry.add(rec2)
    assert len(registry.load()) == 2

    # stop() without workkey stops all and empties registry
    receipts = registry.stop()
    assert len(receipts) == 2
    assert registry.load() == []
