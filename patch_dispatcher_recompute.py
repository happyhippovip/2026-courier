import re
with open("scripts/courier_safety_dispatcher.py", "r") as f:
    content = f.read()

replacement = """
        self.reconcile_orphans()
        
        all_m = self.mission_queue.read_all()
        goal_m = [m for m in all_m if m.get("goal") == goal] if goal else all_m
        if goal_m:
            from scripts.courier_goal_satisfaction_engine import GoalSatisfactionEngine
            engine = GoalSatisfactionEngine(self.workspace_dir)
            decision = engine.recompute(goal, goal_m)
            if decision == "VERIFIED_COMPLETE":
                return {"status": "VERIFIED_COMPLETE"}
        
        mission = self.mission_queue.claim_next(worker_id, goal=goal)
        if mission is None:
            if goal_m:
                return {"status": decision}
            return {"status": "DISCOVER_FROM_ACTIVE_ROOT_GOAL_GAPS"}
"""

new_content = re.sub(
    r"self\.reconcile_orphans\(\)\n\s*mission = self\.mission_queue\.claim_next\(worker_id, goal=goal\)\n\s*if mission is None:\n\s*all_m = self\.mission_queue\.read_all\(\)\n\s*goal_m = \[m for m in all_m if m\.get\(\"goal\"\) == goal\] if goal else all_m\n\s*if goal_m:\n\s*from scripts\.courier_goal_satisfaction_engine import GoalSatisfactionEngine\n\s*engine = GoalSatisfactionEngine\(self\.workspace_dir\)\n\s*decision = engine\.recompute\(goal, goal_m\)\n\s*return \{\"status\": decision\}\n\s*return \{\"status\": \"DISCOVER_FROM_ACTIVE_ROOT_GOAL_GAPS\"\}",
    replacement.strip(),
    content
)

with open("scripts/courier_safety_dispatcher.py", "w") as f:
    f.write(new_content)
