import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target_eligible = """    required_capabilities = _string_list(task.get("required_capabilities"))
    required_authorities = _string_list(task.get("required_authorities"))
    worker_capabilities = _string_list(worker.get("capabilities"))
    worker_authorities = _string_list(worker.get("authorities"))"""

repl_eligible = """    # P5 Package 3: Communities
    goal_id = task.get("goal_id")
    if goal_id and "goals" in state and goal_id in state["goals"]:
        goal = state["goals"][goal_id]
        goal_community = goal.get("community_id", "public")
        worker_community = worker.get("community_id", "public")
        if goal_community != worker_community:
            return False

    required_capabilities = _string_list(task.get("required_capabilities"))
    required_authorities = _string_list(task.get("required_authorities"))
    worker_capabilities = _string_list(worker.get("capabilities"))
    worker_authorities = _string_list(worker.get("authorities"))
    
    # P5 Package 2: Group Discovery
    required_groups = _string_list(task.get("required_groups"))
    if required_groups:
        worker_groups = _string_list(worker.get("groups", []))
        if not worker_groups or not set(required_groups).issubset(set(worker_groups)):
            return False"""

content = content.replace(target_eligible, repl_eligible)

p.write_text(content)
print("SUCCESS")
