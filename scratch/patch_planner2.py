import re

planner_path = "scripts/courier_goal_planner.py"
with open(planner_path, "r") as f:
    content = f.read()

# Replace preferred_agent: "GEMINI" inside the direct implementation block
replacement = """                    "capability_required": "architecture",
                    "preferred_agent": "WINDOWS_PC2" if "windows" in root_goal.lower() else "GEMINI","""

content = re.sub(r'                    "capability_required": "architecture",\n                    "preferred_agent": "GEMINI",', replacement, content)

with open(planner_path, "w") as f:
    f.write(content)
print("Patched planner (attempt 2).")
