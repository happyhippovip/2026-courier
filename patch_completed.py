import re
from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

target = """            if durable_result.get("status") == "SUCCESS":
                set_task_status(task, "RESULT_RECEIVED")  # wait for independent /verify"""
                
repl = """            if durable_result.get("status") == "SUCCESS":
                set_task_status(task, "RESULT_RECEIVED")  # wait for independent /verify
                
                # P5 Package 1: Profile tasks_completed tracking
                if worker_id in state["workers"]:
                    state["workers"][worker_id]["tasks_completed"] = state["workers"][worker_id].get("tasks_completed", 0) + 1
"""

content = content.replace(target, repl)

p.write_text(content)
print("SUCCESS")
