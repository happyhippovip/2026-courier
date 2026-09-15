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

from scripts.live_worker_registry import LiveWorkerRegistry
from scripts.resource_policy import TaskLeaseManager

def main():
    registry = LiveWorkerRegistry(repo_dir=COURIER_DIR)
    registry.register_worker(worker_id="CODEX", role="specialist architecture", provider="local")
    w = registry.get_worker("CODEX")
    if w:
        w.state = "SAFE_IDLE"
        registry._save_worker_record(w)

    task_id = "GOOGLE_TO_CODEX_HANDOFF_PROOF_20260914_CLEAN1"
    objective_id = "OBJ-HANDOFF-1"
    dedupe_hash = hashlib.sha256(f"CODEX_HANDOFF_{task_id}".encode()).hexdigest()[:16]
    
    # 1. Authoritative lease acquisition
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
        
    print(f"Authoritative Lease acquired: {lease_data}")
    
    # 2. Canonical Provenance
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provenance = {
        "origin": "GOOGLE_ANTIGRAVITY",
        "task_identity": task_id,
        "parent_task_id": "GOOGLE_TO_CODEX_HANDOFF_PROOF_20260914",
        "objective_id": objective_id,
        "created_at": now_iso,
        "generation_source": "scripts/handoff_proof_clean.py"
    }

    # 3. Canonical Envelope
    task_envelope = {
        "task_id": task_id,
        "goal_id": objective_id,
        "source_agent": "GOOGLE_ANTIGRAVITY",
        "target_agent": "CODEX",
        "target_host": "DESKTOP-JDPRUGR",
        "project_path": "C:\\Dev\\Windows-AI-OS",
        "scope": ["C:\\Dev\\Windows-AI-OS"],
        "action": "Report remote project identity and one harmless project fact.",
        "acceptance_criteria": "Return a valid JSON object with the expected task identity and safe summary.",
        "status": "PENDING",
        "created_at": now_iso,
        "provenance": provenance,
        "lease": lease_data,
        "task_hash": dedupe_hash,
        "worker_id": "CODEX",
        "payload": {
            "prompt": "Report remote project identity and one harmless project fact.",
            "allowed_scope": ["C:\\Dev\\Windows-AI-OS"],
            "requires_write": False
        }
    }
    
    # 4. Dispatch
    dispatch_dir = COURIER_DIR / "events" / "dispatch"
    dispatch_dir.mkdir(parents=True, exist_ok=True)
    out_path = dispatch_dir / f"{task_id}-worker-job.json"
    with open(out_path, "w") as f:
        json.dump(task_envelope, f, indent=2)
        
    print(f"Task envelope dropped to {out_path}")
    print("SUCCESS: DISPATCH COMPLETE")

if __name__ == "__main__":
    main()
