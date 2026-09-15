from scripts.opportunity_queue import OpportunityQueue
from scripts.next_safe_work_router import NextSafeWorkRouter
from pathlib import Path

oq = OpportunityQueue(Path('/Users/user/Downloads/2026-courier'))
all_opps = oq.list_opportunities()
for cand in all_opps:
    if cand.opportunity_id == "WINDOWS_OVERNIGHT_TEST_2":
        print(f"Found candidate: {cand}")
        print(f"Risk: {cand.risk}")
        print(f"Status: {cand.status}")
        
router = NextSafeWorkRouter(repo_dir=Path('/Users/user/Downloads/2026-courier'))
ready_tasks = [o for o in all_opps if o.status == "READY"]

for cand in ready_tasks:
    if cand.opportunity_id == "WINDOWS_OVERNIGHT_TEST_2":
        print("\nEvaluating routing for WINDOWS:")
        wid = "WINDOWS"
        if cand.target_agent and cand.target_agent != wid:
            print("Rejected: target_agent mismatch")
        elif router.queue_manager.is_task_completed_in_history(cand.opportunity_id):
            print("Rejected: completed in history")
        elif cand.estimated_cost > 0.0 or cand.status == "PAYMENT_APPROVAL_REQUIRED":
            print("Rejected: cost")
        elif cand.risk == "HIGH" or cand.status in ("WAITING_FOR_HUMAN", "HUMAN_GATE"):
            print("Rejected: high risk")
        elif cand.heavy_job:
            print("Rejected: heavy job")
        else:
            print("Passed primary conditions.")
            cand_scopes = set(cand.allowed_scope or [cand.project or "GLOBAL"])
            print(f"Cand scopes: {cand_scopes}")
            
            req_caps = set(cand.required_capabilities or [])
            req_windows = "WINDOWS_EXECUTION" in req_caps or "WINDOWS_RELAY_VALIDATOR" in req_caps
            if req_windows and wid != "CODEX":
                print("Rejected: windows execution directed to codex")
            else:
                print("WOULD BE RECOMMENDED!")
