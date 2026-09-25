import re

with open("scripts/work_queue.py", "r") as f:
    content = f.read()

# Replace the claim loop to increment attempt_count and dispatch_count
old_claim = """        task["status"] = "CLAIMED"
        task["owner"] = args.worker
        data["leases"][task["task_id"]] = {"""

new_claim = """        task["status"] = "CLAIMED"
        task["owner"] = args.worker
        task["attempt_count"] = task.get("attempt_count", 0) + 1
        task["dispatch_count"] = task.get("dispatch_count", 0) + 1
        task["attempt_id"] = f"{task['task_id']}:attempt:{task['attempt_count']}"
        task["dispatch_id"] = f"{task['task_id']}:dispatch:{task['dispatch_count']}"
        data["leases"][task["task_id"]] = {"""

content = content.replace(old_claim, new_claim)

with open("scripts/work_queue.py", "w") as f:
    f.write(content)
