import re
import sys

with open("server/app.py", "r") as f:
    content = f.read()

# 1. Add threading.Condition
if "NEW_TASK_EVENT = threading.Condition(STATE_LOCK)" not in content:
    content = content.replace("STATE_LOCK = threading.RLock()", "STATE_LOCK = threading.RLock()\nNEW_TASK_EVENT = threading.Condition(STATE_LOCK)")

# 2. Add Deduplication in verify_task_result
dedupe_code = """                    if all(d in completed_tasks for d in deps):
                        ready_work_exists = True
                        if step.get("status") == "QUEUED" and task.get("worker_id"):
                            # Deduplicate ownership: Assign to the same worker if eligible
                            if _worker_is_eligible(state, step, task["worker_id"]):
                                step["status"] = "DISPATCHED"
                                step["worker_id"] = task["worker_id"]
                                step["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
                                
                                # Update global tasks
                                next_task_id = step.get("task_id")
                                if next_task_id in state["tasks"]:
                                    next_task = state["tasks"][next_task_id]
                                    set_task_status(next_task, "DISPATCHED")
                                    next_task["worker_id"] = task["worker_id"]
                                    next_task["dispatch_id"] = step["dispatch_id"]
                                    
                                # Lock worker
                                worker = state["workers"].get(task["worker_id"])
                                if worker:
                                    worker["current_task"] = next_task_id
                                    worker["available"] = False
                                    
                                NEW_TASK_EVENT.notify_all()
                                break
"""

if "# Deduplicate ownership" not in content:
    # We find the exact line in verify_task_result
    target = """                    if all(d in completed_tasks for d in deps):
                        ready_work_exists = True"""
    content = content.replace(target, dedupe_code)

# 3. Add Long-polling in claim_task
claim_target = """    for goal_id, goal in state["goals"].items():
        if goal["status"] == "ACTIVE" and "workflow_plan" in goal:"""

claim_long_poll = """    # Long polling support: wait up to 20 seconds if no immediate tasks
    wait_start = time.time()
    while time.time() - wait_start < 20:
        for goal_id, goal in state["goals"].items():
            if goal["status"] == "ACTIVE" and "workflow_plan" in goal:"""

if "# Long polling support" not in content:
    content = content.replace(claim_target, claim_long_poll)

# Also need to indent the rest of claim_task? 
# Wait, replacing with a while loop requires re-indenting the rest of the function!
# Let's do it safely without re-indenting everything.

