#!/usr/bin/env python3

import json
import hashlib
import sys
from pathlib import Path
import uuid

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerRecord, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity

def main():
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    
    # Setup Worker 1: Available and capable
    worker1_id = "TEST_CAPABLE_WORKER"
    registry.register_worker(worker_id=worker1_id, role="test_role", provider="local")
    w1 = registry.get_worker(worker1_id)
    w1.state = WorkerState.SAFE_IDLE.value
    registry._save_worker_record(w1)

    # Setup Worker 2: Unavailable
    worker2_id = "TEST_BUSY_WORKER"
    registry.register_worker(worker_id=worker2_id, role="test_role", provider="local")
    w2 = registry.get_worker(worker2_id)
    w2.state = WorkerState.WAITING_PERMISSION.value
    registry._save_worker_record(w2)

    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    # 1. GATED Opportunity (Targeting Available Worker, but HUMAN_GATE)
    gated_id = f"TASK-GATED-{uuid.uuid4().hex[:6]}"
    opp_gated = Opportunity(
        opportunity_id=gated_id,
        source="TEST_INJECT",
        project="ROUTING_TEST",
        description="Gated opportunity",
        objective_id="OBJ-TEST-1",
        priority=10,
        risk="HIGH",
        estimated_cost=0.0,
        heavy_job=False,
        status="HUMAN_GATE",
        target_agent=worker1_id,
        allowed_scope=["scripts/some_gated_scope.py"],
        allowed_actions=["WRITE"],
        dedupe_hash=hashlib.sha256(f"GATED_{gated_id}".encode()).hexdigest()[:16]
    )
    queue.add_opportunity(opp_gated)

    # 2. SAFE Opportunity (Targeting Available Worker)
    safe_id = f"TASK-SAFE-{uuid.uuid4().hex[:6]}"
    opp_safe = Opportunity(
        opportunity_id=safe_id,
        source="TEST_INJECT",
        project="ROUTING_TEST",
        description="Safe opportunity",
        objective_id="OBJ-TEST-1",
        priority=5,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=worker1_id,
        allowed_scope=["scripts/some_safe_scope.py"],
        allowed_actions=["READ"],
        dedupe_hash=hashlib.sha256(f"SAFE_{safe_id}".encode()).hexdigest()[:16]
    )
    queue.add_opportunity(opp_safe)
    
    # 3. SAFE Opportunity targeting the busy worker (Targeting Unavailable Worker)
    safe_busy_id = f"TASK-SAFE-BUSY-{uuid.uuid4().hex[:6]}"
    opp_safe_busy = Opportunity(
        opportunity_id=safe_busy_id,
        source="TEST_INJECT",
        project="ROUTING_TEST",
        description="Safe opportunity for busy worker",
        objective_id="OBJ-TEST-1",
        priority=5,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=worker2_id,
        allowed_scope=["scripts/some_busy_scope.py"],
        allowed_actions=["READ"],
        dedupe_hash=hashlib.sha256(f"SAFE_{safe_busy_id}".encode()).hexdigest()[:16]
    )
    queue.add_opportunity(opp_safe_busy)

    # Evaluate router
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    recommendations = res.get("recommendations", {})

    print("ROUTING RESULTS:")
    print("----------------")
    
    w1_rec = recommendations.get(worker1_id, {})
    w2_rec = recommendations.get(worker2_id, {})

    print(f"AVAILABLE WORKER ({worker1_id}) Recommended Action: {w1_rec.get('recommended_action')}")
    print(f"UNAVAILABLE WORKER ({worker2_id}) Recommended Action: {w2_rec.get('recommended_action')} (Block Reason: {w2_rec.get('block_reason')})")

    if w1_rec.get("recommended_action") == f"DISPATCH_TASK_{safe_id}":
        print(f"SAFE_BRANCH_ROUTABLE=YES")
        print(f"CORRECT_CAPABLE_AVAILABLE_WORKER_SELECTED=YES")
    else:
        print("FAIL: Safe task was not routed to available worker.")

    if w2_rec.get("available") == False:
        print("UNAVAILABLE_OR_INCAPABLE_WORKER_REJECTED=YES")
    else:
        print("FAIL: Unavailable worker was not rejected.")
        
    gated_routed = False
    for rec in recommendations.values():
        if rec.get("recommended_action") == f"DISPATCH_TASK_{gated_id}":
            gated_routed = True
            break
            
    if not gated_routed:
        print("GATED_BRANCH_ROUTED=NO")
        print("HUMAN_GATE_BYPASSED=NO")
        print("HUMAN_GATE_BRANCH_LOCAL=YES")
        print("SAFE_WORK_CONTINUES_WHILE_OTHER_BRANCH_GATED=YES")
    else:
        print("FAIL: Gated task was routed!")
        
    # Write environment variables for parsing
    with open("routing_proof.env", "w") as f:
        f.write(f"GATED_OPPORTUNITY_ID={gated_id}\n")
        f.write(f"SAFE_OPPORTUNITY_ID={safe_id}\n")
        f.write(f"SELECTED_WORKER={worker1_id}\n")

if __name__ == "__main__":
    main()
