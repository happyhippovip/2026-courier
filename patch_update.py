import sys

with open("scripts/run_live_production_goal.py", "r") as f:
    code = f.read()

new_func = """def update_completed_tasks():
    results_dirs = [
        COURIER_DIR / "coordination" / "windows_to_mac" / "results",
        COURIER_DIR / "coordination" / "windows_to_mac" / "archive",
        COURIER_DIR / "events" / "processed",
        COURIER_DIR / "events" / "results",
    ]
    queue = OpportunityQueue(repo_dir=COURIER_DIR)
    
    for results_path in results_dirs:
        if not results_path.exists(): continue
        for res_file in results_path.glob("*.json"):
            if "-worker-job" in res_file.name: continue
            try:
                with open(res_file) as f:
                    data = json.load(f)
                mission_id = data.get("mission_id") or data.get("task_id")
                status = data.get("status")
                if mission_id and status == "COMPLETED":
                    opp = queue.get_opportunity(mission_id)
                    if opp and opp.status != "COMPLETED":
                        opp.status = "COMPLETED"
                        queue.save_opportunity(opp)
                        print(f"Marked task {mission_id} as COMPLETED")
            except Exception as e:
                pass"""

import re
code = re.sub(r'def update_completed_tasks\(\):.*?except Exception as e:\n\s*pass', new_func, code, flags=re.DOTALL)

with open("scripts/run_live_production_goal.py", "w") as f:
    f.write(code)
