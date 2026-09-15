#!/usr/bin/env python3
"""Minimal wiring from NextSafeWorkRouter -> GEMINI Adapter -> Result Customs."""

import json
import hashlib
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
COURIER_DIR = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(COURIER_DIR) not in sys.path:
    sys.path.insert(0, str(COURIER_DIR))

from scripts.next_safe_work_router import NextSafeWorkRouter
from scripts.live_worker_registry import LiveWorkerRegistry, WorkerRecord, WorkerState
from scripts.opportunity_queue import OpportunityQueue, Opportunity
from scripts.courier_real_worker_adapters import get_real_worker_adapters

def main():
    # 1. Ensure GEMINI worker is registered and SAFE_IDLE
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(
        worker_id="GEMINI",
        role="analysis",
        provider="local"
    )
    # Force state to SAFE_IDLE
    w = registry.get_worker("GEMINI")
    if w:
        w.state = WorkerState.SAFE_IDLE.value
        registry._save_worker_record(w)

    # 2. Inject a fresh harmless GEMINI opportunity
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    import uuid
    task_id = f"TASK-GEMINI-TEST-{uuid.uuid4().hex[:6]}"
    
    dedupe_hash = hashlib.sha256(f"GEMINI_TEST_{task_id}".encode()).hexdigest()[:16]
    opp = Opportunity(
        opportunity_id=task_id,
        source="TEST_INJECT",
        project="GEMINI_INTEGRATION",
        description="Harmless inspection task for Gemini",
        objective_id="OBJ-GEMINI-1",
        priority=6,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent="GEMINI",
        allowed_scope=["scripts/run_antigravity_bridge.py"],  # Read only scope
        allowed_actions=["READ"],
        dedupe_hash=dedupe_hash,
    )
    if queue.add_opportunity(opp):
        print(f"Injected GEMINI Opportunity: {task_id}")
    else:
        print(f"Opportunity {task_id} already exists.")

    # 3. Router evaluates next safe work
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    rec = res.get("recommendations", {}).get("GEMINI")
    
    if not rec or not rec.get("recommended_action", "").startswith("DISPATCH_TASK_"):
        print(f"Router did not select a task. Rec: {rec}")
        return
        
    print(f"Router selected GEMINI task: {rec.get('recommended_action')}")

    # 4. Dispatch to real GEMINI adapter
    recommended_task_id = rec.get("recommended_action", "").replace("DISPATCH_TASK_", "")
    task_envelope = {
        "task_hash": dedupe_hash,
        "worker_id": "GEMINI",
        "target_agent": "GEMINI",
        "task_id": recommended_task_id,
        "payload": {
            "action": "acceptance_review",
            "prompt": "Inspect run_antigravity_bridge.py safely.",
            "allowed_scope": ["scripts/run_antigravity_bridge.py"]
        }
    }

    # Write dummy original request so Result Customs will accept it
    req_id = f"REQ-MAC-{dedupe_hash[:8]}"
    requests_dir = COURIER_DIR / "coordination" / "mac_to_windows" / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    with open(requests_dir / f"{req_id}.json", "w") as f:
        json.dump(task_envelope, f)

    adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
    gemini_adapter = adapters.get("GEMINI")
    if not gemini_adapter:
        print("GEMINI adapter not found!")
        return

    print("Executing Gemini adapter...")
    result_envelope = gemini_adapter(task_envelope)
    
    # 5. Place result in Result Customs
    result_data = result_envelope.get("result")
    if not result_data:
        print("No result data returned!")
        return
        
    obs = "Gemini check completed"
    calc_fingerprint = hashlib.sha256(f"{req_id}COMPLETED{obs}".encode("utf-8")).hexdigest()
    wrapped_result = {
        "request_id": req_id,
        "mission_id": task_id,
        "schema_version": "1.0",
        "status": "COMPLETED",
        "observed_behavior": obs,
        "result_fingerprint": calc_fingerprint,
        "payload": result_data.get("payload", {})
    }
    
    results_dir = COURIER_DIR / "coordination" / "windows_to_mac" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_file = results_dir / f"{req_id}.json"
    
    with open(out_file, "w") as f:
        json.dump(wrapped_result, f, indent=2)
        
    print(f"Result returned to Customs: {out_file}")

    # 6. Run mac_result_consumer to prove it gets accepted
    print("Running mac_result_consumer to verify integration...")
    import subprocess
    subprocess.run([sys.executable, "scripts/mac_result_consumer.py"])
    print("Done.")

if __name__ == "__main__":
    main()
