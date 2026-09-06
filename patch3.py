with open("scripts/courier_founder_mode.py", "r") as f:
    content = f.read()

# Add reopen_invalidated_blocker
new_method = """    def reopen_invalidated_blocker(self, goal_id: str) -> None:
        goal = self.read_goal(goal_id)
        if goal and goal["status"] in ["HUMAN_GATE", "BLOCKED", "FAILED"]:
            self.set_status(goal_id, "PENDING")

"""
content = content.replace("    def mark_satisfied(self, goal_id: str) -> None:", new_method + "    def mark_satisfied(self, goal_id: str) -> None:")

with open("scripts/courier_founder_mode.py", "w") as f:
    f.write(content)
