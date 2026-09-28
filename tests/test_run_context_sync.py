import pytest
import json
from pathlib import Path

def test_check_task_staleness_no_task_version(tmp_path, monkeypatch):
    import scripts.run_context_sync as script
    
    steward = script.UpdateSteward()
    task_data = {}
    current_snapshot = {"context_version": 2, "snapshot_hash": "hash2"}
    
    stale, reason = steward.check_task_staleness(task_data, current_snapshot)
    
    assert stale is True
    assert "Task missing context version" in reason

def test_check_task_staleness_mismatch(tmp_path, monkeypatch):
    import scripts.run_context_sync as script
    
    steward = script.UpdateSteward()
    task_data = {"context_version": 1, "context_snapshot_hash": "hash1"}
    current_snapshot = {"context_version": 2, "snapshot_hash": "hash2"}
    
    stale, reason = steward.check_task_staleness(task_data, current_snapshot)
    
    assert stale is True
    assert "differs from current" in reason

def test_check_task_staleness_current(tmp_path, monkeypatch):
    import scripts.run_context_sync as script
    
    steward = script.UpdateSteward()
    task_data = {"context_version": 2, "context_snapshot_hash": "hash2"}
    current_snapshot = {"context_version": 2, "snapshot_hash": "hash2"}
    
    stale, reason = steward.check_task_staleness(task_data, current_snapshot)
    
    assert stale is False
    assert reason == "CONTEXT_CURRENT"

def test_attach_task_context(tmp_path, monkeypatch):
    import scripts.run_context_sync as script
    
    steward = script.UpdateSteward()
    
    snapshot = {
        "context_version": 5,
        "snapshot_hash": "abc",
        "repositories": {"courier_head": "123"},
        "memory_truth": {
            "latest_verified_milestone": "M1",
            "latest_decisions": ["D1", "D2"]
        },
        "truth_classifications": {
            "truth_invariants": "INV1"
        }
    }
    
    task = {"task_id": "T-1"}
    result = steward.attach_task_context(task, snapshot)
    
    assert result["context_version"] == 5
    assert result["context_snapshot_hash"] == "abc"
    assert result["bounded_context"]["latest_verified_milestone"] == "M1"
    assert len(result["bounded_context"]["latest_decisions"]) == 2

