import os
import re

planner_path = "scripts/courier_goal_planner.py"
with open(planner_path, "r") as f:
    content = f.read()

# Replace preferred_agent: "GEMINI" with a dynamic check
replacement = """
                target_agent = "WINDOWS_PC2" if "windows" in root_goal.lower() else "GEMINI"
                mission = {
                    "mission_id": m_id,
                    "goal": root_goal,
                    "normalized_task": "Direct implementation of requested artifact: " + root_goal,
                    "capability_required": "architecture",
                    "preferred_agent": target_agent,
"""

content = re.sub(r'mission = \{\s+"mission_id": m_id,\s+"goal": root_goal,\s+"normalized_task": "Direct implementation of requested artifact: " \+ root_goal,\s+"capability_required": "architecture",\s+"preferred_agent": "GEMINI",', replacement.strip(), content)

with open(planner_path, "w") as f:
    f.write(content)
print("Patched planner to support Windows routing.")
