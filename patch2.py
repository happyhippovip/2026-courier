import re

with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

# Fix the break logic to set BLOCKED if planner error
old_logic = """                if not next_missions:
                    if self.planner.evaluate_success(goal, {"status": "PASS"}, completed_missions):
                        self.intake.mark_satisfied(goal["goal_id"])
                    break"""

new_logic = """                if not next_missions:
                    if self.planner.evaluate_success(goal, {"status": "PASS"}, completed_missions):
                        self.intake.mark_satisfied(goal["goal_id"])
                    elif self.planner.last_planning_error:
                        self.intake.set_status(goal["goal_id"], "BLOCKED", {"planner_error": self.planner.last_planning_error})
                    break"""

content = content.replace(old_logic, new_logic)

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
