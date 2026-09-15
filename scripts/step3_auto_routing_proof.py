#!/usr/bin/env python3
import json
import hashlib
import sys
import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.live_worker_registry import LiveWorkerRegistry, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.resource_policy import TaskLeaseManager

def main():
    # 1. Register CODEX worker
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    w = registry.get_worker("CODEX")
    if w:
        w.state = "SAFE_IDLE"
        registry._save_worker_record(w)

    # 2. Inject Opportunity requiring WINDOWS_EXECUTION
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    task_id = "TASK_WINDOWS_AUTO_ROUTING_PROOF_1"
    dedupe_hash = hashlib.sha256(task_id.encode()).hexdigest()[:16]
    
    opp = Opportunity(
        opportunity_id=task_id,
        source="AUTO_ROUTING",
        project="WINDOWS_AI_OS",
        description="Harmless Windows inspection task.",
        objective_id="OBJ-STEP3-1",
        priority=7,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent=None,  # Not hardcoded!
        required_capabilities=["WINDOWS_EXECUTION"], # Required capability
        allowed_scope=["C:\\Dev\\Windows-AI-OS"],
        allowed_actions=["READ"],
        dedupe_hash=dedupe_hash,
    )
    queue.add_opportunity(opp)
    
    # 3. Router selects
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    
    rec = res.get("recommendations", {}).get("CODEX")
    
    if not rec or not rec.get("recommended_action", "").startswith("DISPATCH_TASK_"):
        print("FAIL: Router did not select CODEX.")
        print("Router recommendations:", res)
        sys.exit(1)
        
    recommended_task_id = rec.get("task_id")
    if recommended_task_id != task_id:
        print(f"FAIL: Router selected wrong task: {recommended_task_id}")
        sys.exit(1)
        
    target_host = rec.get("target_host")
    if target_host != "DESKTOP-JDPRUGR":
        print(f"FAIL: Router selected wrong target host: {target_host}")
        sys.exit(1)
        
    print(f"ROUTER_SELECTED_WORKER=CODEX")
    print(f"ROUTER_SELECTED_HOST={target_host}")
    
    # 4. Acquire lease
    lease_mgr = TaskLeaseManager(repo_dir=COURIER_DIR)
    success, state, lease_data = lease_mgr.acquire_lease(
        task_id=task_id,
        task_hash=dedupe_hash,
        owner_id="CODEX",
        duration_sec=300
    )
    if not success:
        print(f"Failed to acquire lease: {state}")
        sys.exit(1)
        
    print("LEASE_VALID=YES")
    
    # 5. Build envelope and dispatch
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provenance = {
        "origin": "GOOGLE_ANTIGRAVITY",
        "task_identity": task_id,
        "parent_task_id": "NONE",
        "objective_id": "OBJ-STEP3-1",
        "created_at": now_iso,
        "generation_source": "scripts/step3_auto_routing_proof.py"
    }

    task_envelope = {
        "task_id": task_id,
        "goal_id": "OBJ-STEP3-1",
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "target_agent": "CODEX",
        "target_host": target_host,
        "project_path": "C:\\Dev\\Windows-AI-OS",
        "scope": ["C:\\Dev\\Windows-AI-OS"],
        "action": "Report remote project identity and one harmless project fact.",
        "acceptance_criteria": "Return a valid JSON object.",
        "status": "PENDING",
        "created_at": now_iso,
        "provenance": provenance,
        "lease": lease_data,
        "task_hash": dedupe_hash,
        "worker_id": "CODEX",
        "payload": {
            "prompt": "Report remote project identity.",
            "allowed_scope": ["C:\\Dev\\Windows-AI-OS"],
            "requires_write": False
        }
    }
    
    dispatch_dir = COURIER_DIR / "events" / "dispatch"
    out_path = dispatch_dir / f"{task_id}-worker-job.json"
    with open(out_path, "w") as f:
        json.dump(task_envelope, f, indent=2)
        
    print("TASK_DISPATCHED=YES")

if __name__ == "__main__":
    main()
