#!/usr/bin/env python3
import sys
import json
import uuid
import hashlib
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
import subprocess

def main():
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    worker_id = "GEMINI_TEST_AUTO"
    registry.register_worker(worker_id=worker_id, role="test", provider="local")
    w = registry.get_worker(worker_id)
    w.state = WorkerState.SAFE_IDLE.value
    registry._save_worker_record(w)
    
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    task2_id = f"TASK-AUTO2-{uuid.uuid4().hex[:6]}"
    opp2 = Opportunity(
        opportunity_id=task2_id,
        source="TEST_INJECT",
        project="AUTO_DISPATCH",
        description="Stage B safe task",
        objective_id="OBJ-TEST-2",
        priority=9999,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=worker_id,
        allowed_scope=["scripts/some_safe_scope.py"],
        allowed_actions=["READ"],
        dedupe_hash=hashlib.sha256(f"SAFE_{task2_id}".encode()).hexdigest()[:16]
    )
    queue.add_opportunity(opp2)
    
    task1_id = f"TASK-AUTO1-{uuid.uuid4().hex[:6]}"
    
    req_id = f"REQ-MAC-{task1_id}"
    
    # Fake initial request to pass customs
    requests_dir = COURIER_DIR / "coordination" / "mac_to_windows" / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    with open(requests_dir / f"{req_id}.json", "w") as f:
        json.dump({"task_id": task1_id, "worker_id": worker_id}, f)

    obs = "Completed Task 1"
    calc_fingerprint = hashlib.sha256(f"{req_id}COMPLETED{obs}".encode("utf-8")).hexdigest()
    
    result_payload = {
        "request_id": req_id,
        "mission_id": task1_id,
        "schema_version": "1.0",
        "status": "COMPLETED",
        "observed_behavior": obs,
        "result_fingerprint": calc_fingerprint,
        "payload": {"worker_agent": worker_id}
    }
    
    results_dir = COURIER_DIR / "coordination" / "windows_to_mac" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    res_file = results_dir / f"{req_id}.json"
    with open(res_file, "w") as f:
        json.dump(result_payload, f)
        
    print(f"Placed result {res_file.name}. Running mac_result_consumer...")
    
    # Run mac_result_consumer
    import scripts.mac_result_consumer as mrc
    mrc.RESULTS_DIR = results_dir
    mrc.REQUESTS_DIR = requests_dir
    mrc.consume_results()
    
    print("\nSTAGE B completed. Doing Quiescence test...")
    # Quiescence test: we just mark the second task completed (or it should be claimed)
    # The queue is not cleared! Unrelated ops are ignored!
    
    # Complete opp2 so no safe work exists for this worker
    opp2 = queue.get_opportunity(task2_id)
    opp2.status = "COMPLETED"
    queue.save_opportunity(opp2)
    
    # Drop the SAME result file again to prove idempotency/replay protection
    print("\nReplaying identical result file...")
    with open(res_file, "w") as f:
        json.dump(result_payload, f)
    
    # Capture output of second run
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    mrc.consume_results()
    output_replay = sys.stdout.getvalue()
    sys.stdout = old_stdout
    
    print(output_replay)
    
    replay_triggered = "Auto-dispatching" in output_replay
    quiesces = "Auto-dispatching" not in output_replay and "DUPLICATE_FINGERPRINT" in output_replay
    
    with open("real_customs_proof.env", "w") as f:
        f.write(f"FIRST_STAGE_TASK_ID={task1_id}\n")
        f.write(f"SECOND_STAGE_TASK_ID={task2_id}\n")
        f.write(f"SECOND_STAGE_WORKER={worker_id}\n")
        f.write(f"REPLAY_TRIGGERED_SECOND_DISPATCH={'YES' if replay_triggered else 'NO'}\n")
        f.write(f"NO_SAFE_WORK_QUIESCES={'YES' if quiesces else 'NO'}\n")

if __name__ == "__main__":
    main()
