import datetime
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from scripts.resource_policy import (
    load_json,
    ResourcePolicyManager,
    TaskLeaseManager,
    FileManifestTracker,
    TaskDedupeEngine,
)


def test_load_json_exception(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    # load_json should catch Exception and return None
    assert load_json(p) is None


def test_get_default_iterations_fallback(monkeypatch, tmp_path):
    policy_file = tmp_path / "events" / "policies" / "resource_policy.json"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text('{"operating_invariants": {"max_autonomous_iterations_per_task": "invalid"}}')
    assert ResourcePolicyManager.get_default_iterations(tmp_path) == 1


def test_task_lease_reclaim_exception(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_reclaim_exc"
    
    # Create an expired lease
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({
        "task_id": task_id,
        "owner_id": "old_owner",
        "expires_at": 0  # expired
    }))
    
    # Mock os.open to raise FileExistsError ONLY for the reclaim lock
    original_open = os.open
    def mock_open(path, flags, mode=0o777, *args, **kwargs):
        if str(path).endswith(".reclaim.lock"):
            raise FileExistsError("mocked conflict")
        return original_open(path, flags, mode, *args, **kwargs)
    
    monkeypatch.setattr(os, "open", mock_open)
    
    ok, msg, data = mgr.acquire_lease(task_id, "hash", "new_owner")
    assert not ok
    assert msg == "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER"
    assert data["owner_id"] == "old_owner"


def test_task_lease_reclaim_success(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_reclaim_succ"
    
    # Create an expired lease
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({
        "task_id": task_id,
        "owner_id": "old_owner",
        "expires_at": 0  # expired
    }))
    
    ok, msg, data = mgr.acquire_lease(task_id, "hash", "new_owner")
    assert ok
    assert msg == "LEASE_RECLAIMED_EXPIRED"
    assert data["owner_id"] == "new_owner"


def test_task_lease_reclaim_interrupted_by_other(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_reclaim_int"
    
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({
        "task_id": task_id,
        "owner_id": "old_owner",
        "expires_at": 0  # expired
    }))
    
    # When load_json is called under the lock, pretend the lease is now active
    original_load_json = load_json
    load_json_calls = 0
    def mock_load_json(path):
        nonlocal load_json_calls
        res = original_load_json(path)
        load_json_calls += 1
        if load_json_calls == 2:  # The call inside the reclaim lock
            res["expires_at"] = datetime.datetime.now(datetime.timezone.utc).timestamp() + 300
        return res
        
    monkeypatch.setattr("scripts.resource_policy.load_json", mock_load_json)
    
    ok, msg, data = mgr.acquire_lease(task_id, "hash", "new_owner")
    assert not ok
    assert msg == "TASK_ALREADY_CLAIMED_BY_ANOTHER_BUILDER"


def test_release_lease_not_exists(tmp_path):
    mgr = TaskLeaseManager(tmp_path)
    assert mgr.release_lease("not_exist", "owner") is True


def test_release_lease_exception(tmp_path, monkeypatch):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_exc"
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({"owner_id": "owner"}))
    
    def mock_unlink(*args, **kwargs):
        raise RuntimeError("unlink failed")
    
    monkeypatch.setattr(Path, "unlink", mock_unlink)
    assert mgr.release_lease(task_id, "owner") is False


def test_is_task_claimed_empty(tmp_path):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_empty"
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text("")
    assert mgr.is_task_claimed(task_id) is False


def test_is_task_claimed_expired(tmp_path):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_exp"
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({"expires_at": 0}))
    assert mgr.is_task_claimed(task_id) is False


def test_is_task_claimed_same_owner(tmp_path):
    mgr = TaskLeaseManager(tmp_path)
    task_id = "test_same"
    lease_path = mgr._get_lease_path(task_id)
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    lease_path.write_text(json.dumps({
        "owner_id": "owner1", 
        "expires_at": datetime.datetime.now(datetime.timezone.utc).timestamp() + 300
    }))
    assert mgr.is_task_claimed(task_id, "owner1") is False


def test_get_file_hash_not_found(tmp_path):
    assert FileManifestTracker.get_file_hash(tmp_path / "not_exist.txt") == "FILE_NOT_FOUND"


def test_get_cached_result_telemetry_exception(tmp_path, monkeypatch):
    engine = TaskDedupeEngine(tmp_path)
    
    task_hash = "thash"
    engine.registry_file.parent.mkdir(parents=True, exist_ok=True)
    engine.registry_file.write_text(json.dumps({
        task_hash: {
            "task_id": "t1",
            "result_file": "r1.json",
            "result_hash": "dummy_hash"
        }
    }))
    
    res_path = tmp_path / "events" / "demo" / "results" / "r1.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps({"payload": {"a": 1}}))
    
    # We need to set the result_hash to match the payload's hash
    real_hash = json.dumps({"a": 1}, sort_keys=True).encode("utf-8")
    import hashlib
    h = hashlib.sha256(real_hash).hexdigest()
    
    engine.registry_file.write_text(json.dumps({
        task_hash: {
            "task_id": "t1",
            "result_file": "r1.json",
            "result_hash": h
        }
    }))
    
    # Mock open for the reuse_log to raise an exception
    original_open = open
    def mock_open_exc(path, mode="r", *args, **kwargs):
        if "reuse_events.jsonl" in str(path):
            raise IOError("log failed")
        return original_open(path, mode, *args, **kwargs)
        
    monkeypatch.setattr("builtins.open", mock_open_exc)
    
    # It should catch the exception and still return the result
    res = engine.get_cached_result(task_hash)
    assert res is not None
    assert res["reused_from_cache"] is True


def test_get_cached_result_not_found_on_disk(tmp_path):
    engine = TaskDedupeEngine(tmp_path)
    task_hash = "thash"
    engine.registry_file.parent.mkdir(parents=True, exist_ok=True)
    engine.registry_file.write_text(json.dumps({
        task_hash: {
            "task_id": "t1",
            "result_file": "not_exist.json",
            "result_hash": "dummy_hash"
        }
    }))
    assert engine.get_cached_result(task_hash) is None
