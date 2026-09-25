import json

with open("scripts/courier_control_plane.py", "r") as f:
    content = f.read()

import re

# We will replace the mapped_plan block to dynamically map agents
old_block = """            mapped_plan = []
            for step in plan:
                mapped_plan.append({
                    "task_id": step["task_id"],
                    "goal_id": goal_id,
                    "description": step["instruction"],
                    "target_capability": "mac", # Use mac to prove real headless execution
                    "status": "QUEUED"
                })"""

new_block = """            mapped_plan = []
            for step in plan:
                target_agent = step.get("target_agent", "antigravity").lower()
                target_cap = "mac"
                if "codex" in target_agent or "windows" in target_agent:
                    target_cap = "windows"
                elif "github" in target_agent:
                    target_cap = "github"
                
                mapped_plan.append({
                    "task_id": step.get("task_id", f"task-{uuid.uuid4().hex[:8]}"),
                    "goal_id": goal_id,
                    "description": step.get("instruction", "Next step"),
                    "target_capability": target_cap,
                    "status": "QUEUED"
                })"""

content = content.replace(old_block, new_block)

with open("scripts/courier_control_plane.py", "w") as f:
    f.write(content)
