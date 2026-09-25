import re
from pathlib import Path

p = Path("tests/test_cannon_result_first.py")
content = p.read_text()

target = """    state = server_app.load_state()
    gid_b = t_b["goal_id"]
    for t in state["goals"][gid_b]["workflow_plan"]:
        if t["task_id"] == tid_b:
            t["status"] = "STALLED"
            break
    server_app.save_state(state)"""

replacement = """    state = server_app.load_state()
    gid_b = t_b["goal_id"]
    for t in state["goals"][gid_b]["workflow_plan"]:
        if t["task_id"] == tid_b:
            t["status"] = "STALLED"
            break
    if tid_b in state["tasks"]:
        state["tasks"][tid_b]["status"] = "STALLED"
    server_app.save_state(state)"""

content = content.replace(target, replacement)
p.write_text(content)
