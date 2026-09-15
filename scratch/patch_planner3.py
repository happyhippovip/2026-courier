import re
planner_path = "scripts/courier_goal_planner.py"
with open(planner_path, "r") as f:
    content = f.read()

content = content.replace('"preferred_agent": "WINDOWS_PC2"', '"preferred_agent": "WINDOWS"')
with open(planner_path, "w") as f:
    f.write(content)
print("Patched planner to use WINDOWS.")
