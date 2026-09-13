import pytest
import os
import time
import json
import uuid
import multiprocessing
from pathlib import Path
from scripts.courier_safety_dispatcher import CourierSafetyDispatcher
from scripts.resource_policy import TaskLeaseManager

def acquire_lease_worker(repo_dir_str: str, task_hash: str):
    lm = TaskLeaseManager(repo_dir=Path(repo_dir_str))
    lm.acquire_lease("global_heavy_job_lease", task_hash, "test_worker_1", 3600)

def test_orphan_recovery_dead_holder_no_effect(tmp_path):
    # Setup
    from scripts.courier_safety_dispatcher import MissionQueue
    q = MissionQueue(tmp_path)
    
    # 1. Enqueue and claim a mission
    task_hash = "deadbeef_no_effect"
    m_id = str(uuid.uuid4())
    q.enqueue({
        "mission_id": m_id,
        "status": "PENDING",
        "task_hash": task_hash,
        "preferred_agent": "GEMINI"
    })
    q.claim_next("test_worker_1")
    
    # 2. Acquire lease in a subprocess so it dies and pid is dead
    p = multiprocessing.Process(target=acquire_lease_worker, args=(str(tmp_path), task_hash))
    p.start()
    p.join()
    
    # Verify lease is there and held by a dead process
    lm = TaskLeaseManager(repo_dir=tmp_path)
    lease_file = lm.locks_dir / "task_global_heavy_job_lease.lease"
    assert lease_file.exists()
    
    # 3. Trigger reconciliation
    dispatcher = CourierSafetyDispatcher(tmp_path)
    dispatcher.reconcile_orphans()
    
    # 4. Verify lease is reclaimed
    assert not lease_file.exists(), "DEAD_HOLDER_DETECTED=PASS, LEASE_RECLAIMED_AUTOMATICALLY=PASS"
    
    # 5. Verify mission is PENDING
    missions = q.read_all()
    m = next(x for x in missions if x["mission_id"] == m_id)
    assert m["status"] == "PENDING", "SAME_TASK_RECOVERED=PASS"

def test_orphan_recovery_confirmed_effect(tmp_path):
    from scripts.courier_safety_dispatcher import MissionQueue
    q = MissionQueue(tmp_path)
    
    task_hash = "deadbeef_confirmed"
    m_id = str(uuid.uuid4())
    q.enqueue({
        "mission_id": m_id,
        "status": "PENDING",
        "task_hash": task_hash,
        "preferred_agent": "GEMINI"
    })
    q.claim_next("test_worker_1")
    
    p = multiprocessing.Process(target=acquire_lease_worker, args=(str(tmp_path), task_hash))
    p.start()
    p.join()
    
    # Simulate confirmed effect
    dispatcher = CourierSafetyDispatcher(tmp_path)
    envelope_dir = tmp_path / "events" / "task-envelopes"
    envelope_dir.mkdir(parents=True, exist_ok=True)
    with open(envelope_dir / f"result_gemini_{task_hash}.json", "w") as f:
        json.dump({"payload": {"status": "COMPLETED"}}, f)
        
    dispatcher.reconcile_orphans()
    
    lm = TaskLeaseManager(repo_dir=tmp_path)
    lease_file = lm.locks_dir / "task_global_heavy_job_lease.lease"
    assert not lease_file.exists()
    
    missions = q.read_all()
    m = next(x for x in missions if x["mission_id"] == m_id)
    assert m["status"] == "PENDING_VERIFY", "CUSTOMS_RECONCILED=PASS"

def test_orphan_recovery_ambiguous_effect(tmp_path):
    from scripts.courier_safety_dispatcher import MissionQueue
    q = MissionQueue(tmp_path)
    
    task_hash = "deadbeef_ambiguous"
    m_id = str(uuid.uuid4())
    q.enqueue({
        "mission_id": m_id,
        "status": "PENDING",
        "task_hash": task_hash,
        "preferred_agent": "GEMINI"
    })
    q.claim_next("test_worker_1")
    
    p = multiprocessing.Process(target=acquire_lease_worker, args=(str(tmp_path), task_hash))
    p.start()
    p.join()
    
    # Simulate ambiguous effect (no verdict/status in result payload)
    dispatcher = CourierSafetyDispatcher(tmp_path)
    envelope_dir = tmp_path / "events" / "task-envelopes"
    envelope_dir.mkdir(parents=True, exist_ok=True)
    with open(envelope_dir / f"result_gemini_{task_hash}.json", "w") as f:
        json.dump({"payload": {"something_else": "yes"}}, f)
        
    dispatcher.reconcile_orphans()
    
    lm = TaskLeaseManager(repo_dir=tmp_path)
    lease_file = lm.locks_dir / "task_global_heavy_job_lease.lease"
    assert not lease_file.exists()
    
    missions = q.read_all()
    m = next(x for x in missions if x["mission_id"] == m_id)
    assert m["status"] == "FAILED", "FAIL_CLOSED=PASS"

