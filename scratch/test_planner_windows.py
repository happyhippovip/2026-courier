import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from courier_goal_planner import CourierGoalPlanner

windows_result = {
    "status": "COMPLETED",
    "payload": {
        "action": "diagnose_infrastructure",
        "weakness_id": "WIN-COMPAT-001",
        "description": "Windows execution compatibility issue",
        "suggested_files": ["windows_compat.ps1"],
        "verification_strategy": "run_powershell_tests",
        "worker_agent": "WINDOWS_PC2"
    }
}

planner = CourierGoalPlanner()
decision = planner.plan_next_step(
    root_goal="Fix Windows compatibility",
    verified_history=[windows_result],
    latest_result=windows_result
)

print(decision.decision)
if decision.next_mission:
    print(decision.next_mission["goal"])
    print(decision.next_mission["preferred_agent"])
