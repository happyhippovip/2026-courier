import re
from pathlib import Path

file_path = Path("/Users/user/Downloads/2026-courier/scripts/courier_founder_mode.py")
content = file_path.read_text()

# Patch 1: pop_next_goal returns g if has_live
content = content.replace(
    "if has_live:\n                    # An active, non-orphaned goal exists. Deny admission to any other goal.\n                    return None",
    "if has_live:\n                    # An active, non-orphaned goal exists. Resume it.\n                    return g"
)

# Patch 2: run_autonomous_loop handles live missions without replanning, and loops forever
new_loop = """
    def run_autonomous_loop(self):
        import time
        while True:
            # 1. Take highest priority PENDING goal
            goal = self.intake.pop_next_goal()
            if not goal:
                print("No safe V1 work or blocked. Sleeping...")
                time.sleep(10)
                continue

            completed_missions = []
            # 2 & 3. Iterative Replan and Execution Loop
            while True:
                all_missions = self.queue.read_all()
                pending = [m for m in all_missions if m["status"] == "PENDING"]
                running_or_verify = [m for m in all_missions if m["status"] in ("RUNNING", "PENDING_VERIFY")]
                
                if not pending and not running_or_verify:
                    next_missions = self.planner.discover_and_plan(goal, completed_missions)
                    if not next_missions:
                        if self.planner.evaluate_success(goal, {"status": "PASS"}, completed_missions):
                            self.intake.mark_satisfied(goal["goal_id"])
                        break
                    
                    parent_id = completed_missions[-1]["mission_id"] if completed_missions else None
                    for m in next_missions:
                        if parent_id: m["parent_mission_id"] = parent_id
                        m["mission_id"] = str(uuid.uuid4())
                        self.queue.enqueue(m)
                        parent_id = m["mission_id"]
                        
                # Process next mission using Courier dispatcher
                worker_id = "founder_loop_1"
                mission_result = self.dispatcher.process_next_mission(worker_id)
            
                if not mission_result or mission_result.get("status") == "NO_PENDING_MISSION":
                    if running_or_verify:
                        print("Waiting for running/verifying missions...")
                        time.sleep(5)
                        continue
                    break # Queue somehow empty
"""

pattern = re.compile(r'    def run_autonomous_loop\(self\):.*?                if not mission_result:\n                    break # Queue somehow empty', re.MULTILINE | re.DOTALL)
new_content = pattern.sub(new_loop.strip(), content)

file_path.write_text(new_content)
print("Patched loop")
