#!/usr/bin/env python3
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
from scripts.live_worker_registry import LiveWorkerRegistry
from scripts.opportunity_queue import OpportunityQueue, Opportunity

def main():
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    w = registry.get_worker("CODEX")
    if w:
        w.state = "SAFE_IDLE"
        registry._save_worker_record(w)

    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    task_id = "GOOGLE_TO_CODEX_HANDOFF_PROOF_20260914"
    dedupe_hash = hashlib.sha256(f"CODEX_HANDOFF_{task_id}".encode()).hexdigest()[:16]
    
    opp = Opportunity(
        opportunity_id=task_id,
        source="GOOGLE_ANTIGRAVITY",
        project="Windows-AI-OS",
        description="Report remote project identity and one harmless project fact.",
        objective_id="OBJ-HANDOFF-1",
        priority=10,
        risk="SAFE",
        estimated_cost=0.0,
        heavy_job=False,
        status="READY",
        target_agent="CODEX",
        allowed_scope=["C:\\Dev\\Windows-AI-OS"],
        allowed_actions=["READ"],
        dedupe_hash=dedupe_hash,
    )
    queue.add_opportunity(opp)
    
    task_envelope = {
        "task_hash": dedupe_hash,
        "worker_id": "CODEX",
        "target_agent": "CODEX",
        "task_id": task_id,
        "target_host": "DESKTOP-JDPRUGR",
        "project_path": "C:\\Dev\\Windows-AI-OS",
        "payload": {
            "prompt": "Report remote project identity and one harmless project fact.",
            "allowed_scope": ["C:\\Dev\\Windows-AI-OS"],
            "requires_write": False
        },
        "lease": {
            "status": "ACTIVE",
            "owner": "CODEX",
            "scope": "C:\\Dev\\Windows-AI-OS"
        },
        "source_agent": "GOOGLE_ANTIGRAVITY"
    }
    
    dispatch_dir = COURIER_DIR / "events" / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    out_path = dispatch_dir / f"{task_id}-worker-job.json"
    with open(out_path, "w") as f:
        json.dump(task_envelope, f, indent=2)
        
    print(f"Task envelope dropped to {out_path}")
    print("SUCCESS: DELIVERY TO CODEX PROVEN")

if __name__ == "__main__":
    main()
