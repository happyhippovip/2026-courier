from scripts.opportunity_queue import OpportunityQueue
from scripts.next_safe_work_router import NextSafeWorkRouter
from pathlib import Path

oq = OpportunityQueue(Path('/Users/user/Downloads/2026-courier'))
router = NextSafeWorkRouter(repo_dir=Path('/Users/user/Downloads/2026-courier'))

ready_tasks = [t for t in router.queue_manager.queue if t.status == "READY"]
print(f"Total ready tasks: {len(ready_tasks)}")

for candidate in ready_tasks:
    if candidate.opportunity_id == "WINDOWS_OVERNIGHT_TEST_1":
        print("Evaluating WINDOWS_OVERNIGHT_TEST_1 for WINDOWS")
        if candidate.target_agent and candidate.target_agent != "WINDOWS":
            print("Rejected: target_agent mismatch")
            continue
        if router.queue_manager.is_task_completed_in_history(candidate.opportunity_id):
            print("Rejected: completed in history")
            continue
        if candidate.estimated_cost > 0.0 or candidate.status == "PAYMENT_APPROVAL_REQUIRED":
            print("Rejected: spend firewall")
            continue
        if getattr(candidate, "risk", "LOW") == "HIGH" or candidate.status in ("WAITING_FOR_HUMAN", "HUMAN_GATE"):
            print("Rejected: high risk")
            continue
        if candidate.heavy_job:
            print("Rejected: heavy job")
            continue
            
        print("Candidate passed basic checks")
        cand_scopes = set(candidate.allowed_scope or [candidate.project or "GLOBAL"])
        print(f"Scopes: {cand_scopes}")
        
        req_caps = set(candidate.required_capabilities or [])
        req_windows = "WINDOWS_EXECUTION" in req_caps or "WINDOWS_RELAY_VALIDATOR" in req_caps
        print(f"req_windows: {req_windows}")
        
        if req_windows and "WINDOWS" != "CODEX":
            print("Rejected: directed to CODEX")
            continue
            
        print("Candidate should be recommended!")
