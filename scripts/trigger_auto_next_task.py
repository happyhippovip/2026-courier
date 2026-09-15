#!/usr/bin/env python3

import sys
import json
import uuid
import hashlib
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.courier_real_worker_adapters import get_real_worker_adapters

def main():
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    
    # Register available worker
    worker_id = "GEMINI"
    registry.register_worker(worker_id=worker_id, role="analysis", provider="local")
    w = registry.get_worker(worker_id)
    w.state = WorkerState.SAFE_IDLE.value
    registry._save_worker_record(w)
    
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    # Create two tasks: Task 1 (completed), Task 2 (Safe, ready to run)
    import time
    
    task2_id = f"TASK-AUTO-B-{uuid.uuid4().hex[:6]}"
    opp2 = Opportunity(
        opportunity_id=task2_id,
        source="TEST_INJECT",
        project="AUTO_DISPATCH",
        description="Safe task 2",
        objective_id="OBJ-TEST-2",
        priority=5,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent="GEMINI",
        allowed_scope=["scripts/some_safe_scope.py"],
        allowed_actions=["READ"],
        dedupe_hash=hashlib.sha256(f"SAFE_{task2_id}".encode()).hexdigest()[:16]
    )
    queue.add_opportunity(opp2)
    
    print("STAGE A: Task 1 completes")
    task1_id = f"TASK-AUTO-A-{uuid.uuid4().hex[:6]}"
    # Emulate ingestion of Task 1's completion
    from scripts.automatic_result_handoff import AutomaticResultHandoff
    handoff = AutomaticResultHandoff(repo_dir=COURIER_DIR)
    
    dummy_result = {
        "worker": "GEMINI",
        "mission": "MISSION_AUTO",
        "state": "COMPLETED",
        "result_id": f"res-{task1_id}",
        "request_id": task1_id,
        "schema_version": "1.0",
        "status": "COMPLETED",
        "observed_behavior": "Completed Task 1"
    }
    
    sig, reason = handoff.ingest_and_route_result(dummy_result)
    print(f"Handoff processed for {task1_id}: {sig.value} / {reason}")

    # STAGE B: Router selects next task and auto-dispatches
    print("\nSTAGE B: Auto-routing Next Task")
    
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    rec = res.get("recommendations", {}).get(worker_id)
    
    next_task_auto_selected = False
    next_task_auto_dispatched = False
    
    if rec and rec.get("recommended_action", "").startswith("DISPATCH_TASK_"):
        recommended_task_id = rec.get("recommended_action").replace("DISPATCH_TASK_", "")
        print(f"Router auto-selected: {recommended_task_id}")
        next_task_auto_selected = True
        
        # Existing dispatcher for that worker
        adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
        adapter = adapters.get(worker_id)
        if adapter:
            print(f"Auto-dispatching {recommended_task_id} to {worker_id}...")
            
            task_envelope = {
                "task_hash": opp2.dedupe_hash,
                "worker_id": worker_id,
                "target_agent": worker_id,
                "task_id": recommended_task_id,
                "payload": {
                    "action": "acceptance_review",
                    "prompt": "Auto-dispatched test",
                    "allowed_scope": ["scripts/some_safe_scope.py"]
                }
            }
            # Dispatch it!
            result_envelope = adapter(task_envelope)
            print("Dispatch complete.")
            next_task_auto_dispatched = True
        else:
            print("Adapter not found.")
            
    print("\nPROVING QUIESCENCE:")
    # Complete opp2 so no safe work exists
    opp2.status = "COMPLETED"
    queue.save_opportunity(opp2)
    
    res_quiesce = router.evaluate_next_safe_work()
    rec_quiesce = res_quiesce.get("recommendations", {}).get(worker_id)
    
    no_safe_work_quiesces = False
    if rec_quiesce and rec_quiesce.get("recommended_action") == "STANDBY_SAFE_IDLE":
        print("Router quiesces gracefully: STANDBY_SAFE_IDLE")
        no_safe_work_quiesces = True

    with open("auto_next_task_proof.env", "w") as f:
        f.write(f"FIRST_STAGE_TASK_ID={task1_id}\n")
        f.write(f"SECOND_STAGE_TASK_ID={task2_id}\n")
        f.write(f"SECOND_STAGE_WORKER={worker_id}\n")
        f.write(f"NEXT_SAFE_TASK_AUTO_SELECTED={'YES' if next_task_auto_selected else 'NO'}\n")
        f.write(f"NEXT_TASK_AUTO_DISPATCHED={'YES' if next_task_auto_dispatched else 'NO'}\n")
        f.write(f"NO_SAFE_WORK_QUIESCES={'YES' if no_safe_work_quiesces else 'NO'}\n")
    
if __name__ == "__main__":
    main()
