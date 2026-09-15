#!/usr/bin/env python3
import json
import hashlib
import sys
import uuid
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

def dispatch_task(prompt_text, file_target):
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    w = registry.get_worker("GEMINI")
    if w:
        w.state = WorkerState.SAFE_IDLE.value
        registry._save_worker_record(w)

    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    task_id = f"COMMERCIAL-{uuid.uuid4().hex[:6]}"
    dedupe_hash = hashlib.sha256(f"GEMINI_COMMERCIAL_{task_id}".encode()).hexdigest()[:16]
    
    opp = Opportunity(
        opportunity_id=task_id,
        source="COMMERCIAL_INITIATIVE",
        project="COMMERCIAL",
        description=f"Create {file_target}",
        objective_id="OBJ-COMMERCIAL",
        priority=9,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent="GEMINI",
        allowed_scope=["UNKNOWN_WRITE"],
        allowed_actions=["implement_bounded_improvement"],
        dedupe_hash=dedupe_hash,
    )
    queue.add_opportunity(opp)
    
    router = NextSafeWorkRouter(repo_dir=COURIER_DIR)
    res = router.evaluate_next_safe_work()
    rec = res.get("recommendations", {}).get("GEMINI")
    
    task_envelope = {
        "task_hash": dedupe_hash,
        "worker_id": "GEMINI",
        "target_agent": "GEMINI",
        "task_id": task_id,
        "payload": {
            "action": "implement_bounded_improvement",
            "prompt": prompt_text,
            "allowed_scope": ["UNKNOWN_WRITE"]
        }
    }

    req_id = f"REQ-MAC-{dedupe_hash[:8]}"
    requests_dir = COURIER_DIR / "coordination" / "mac_to_windows" / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)
    with open(requests_dir / f"{req_id}.json", "w") as f:
        json.dump(task_envelope, f)

    adapters = get_real_worker_adapters(repo_root=COURIER_DIR)
    gemini_adapter = adapters.get("GEMINI")
    
    print(f"Executing Gemini adapter for {file_target}...")
    result_envelope = gemini_adapter(task_envelope)
    
    result_data = result_envelope.get("result")
    
    obs = "Commercial artifact generated"
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

    import subprocess
    subprocess.run([sys.executable, "scripts/mac_result_consumer.py"])
    print(f"Finished {file_target}.")

if __name__ == "__main__":
    import sys
    dispatch_task(sys.argv[1], sys.argv[2])
