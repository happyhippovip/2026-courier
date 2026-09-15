import re
with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

# Replace the evaluate_success block with GoalSatisfactionEngine integration
engine_import = """
                    from scripts.courier_goal_satisfaction_engine import GoalSatisfactionEngine
                    engine = GoalSatisfactionEngine(self.workspace_dir)
                    all_missions = self.queue.read_all()
                    goal_missions = [m for m in all_missions if m.get("goal") == goal["goal"]]
                    decision = engine.recompute(goal["goal"], goal_missions)
                    
                    if decision == "VERIFIED_COMPLETE":
                        self.intake.mark_satisfied(goal["goal_id"])
                        break
                    elif decision == "WAIT_BRANCH_LOCAL_GATE":
                        break
                    elif decision == "QUIESCENT_WAKEABLE":
                        break
                    elif decision == "CONTINUE_SAFE_WORK":
                        # We just let it continue generating missions if it can, 
                        # but if discover_and_plan returned nothing, we break.
                        break
"""

new_content = re.sub(
    r"if self\.planner\.evaluate_success\(goal, \{\"status\": \"PASS\"\}, completed_missions\):\n\s*self\.intake\.mark_satisfied\(goal\[\"goal_id\"\]\)\n\s*break",
    engine_import.strip(),
    content
)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(new_content)
