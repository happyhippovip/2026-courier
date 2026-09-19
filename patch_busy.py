with open("server/app.py", "r") as f:
    content = f.read()

target = """    if worker.get("current_task") or not worker.get("available", False):
        task_id = worker.get("current_task")
        if task_id:
            task = state.get("tasks", {}).get(task_id)
            if not task or task.get("status") != "DISPATCHED":
                worker["current_task"] = None
                worker["available"] = True
            else:
                save_state(state)
                return jsonify({"task": None, "reason": "WORKER_BUSY"})
        else:
            worker["available"] = True"""

replacement = """    if worker.get("current_task") or not worker.get("available", False):
        task_id = worker.get("current_task")
        if task_id:
            task = state.get("tasks", {}).get(task_id)
            if not task or task.get("status") != "DISPATCHED":
                worker["current_task"] = None
                worker["available"] = True
            else:
                # Task is assigned to us, return it! (Deduplicated auto-dispatch)
                save_state(state)
                return jsonify({"task": task})
        else:
            worker["available"] = True"""

if target in content:
    content = content.replace(target, replacement)
    with open("server/app.py", "w") as f:
        f.write(content)
else:
    print("Could not find target!")
