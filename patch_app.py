import re

with open("server/app.py", "r") as f:
    content = f.read()

# Update register_worker
content = content.replace(
    '"current_task": current_task,\n        "cost_class": data.get("cost_class", "unknown")',
    '"current_task": current_task,\n        "cost_class": data.get("cost_class", "unknown"),\n        "resource_state": data.get("resource_state", "NORMAL")'
)

# Update heartbeat
heartbeat_old = """
    if worker_id in state["workers"]:
        state["workers"][worker_id]["last_seen"] = time.time()
        # Only mark available if not currently working
        worker = state["workers"][worker_id]
        if not worker.get("current_task") and not worker.get("unregistered"):
            state["workers"][worker_id]["available"] = True
        save_state(state)
        return jsonify({"status": "OK"})
"""
heartbeat_new = """
    if worker_id in state["workers"]:
        state["workers"][worker_id]["last_seen"] = time.time()
        worker = state["workers"][worker_id]
        if "resource_state" in data:
            worker["resource_state"] = data["resource_state"]
        # Only mark available if not currently working AND normal pressure
        if not worker.get("current_task") and not worker.get("unregistered") and worker.get("resource_state", "NORMAL") == "NORMAL":
            worker["available"] = True
        else:
            worker["available"] = False
        save_state(state)
        return jsonify({"status": "OK"})
"""
content = content.replace(heartbeat_old, heartbeat_new)

# Update claim to also check pressure (just to be sure)
claim_old = """
    if worker.get("current_task") or not worker.get("available", False):
        save_state(state)
        return jsonify({"task": None, "reason": "WORKER_BUSY"})
"""
claim_new = """
    if "resource_state" in data:
        worker["resource_state"] = data["resource_state"]
        if worker["resource_state"] != "NORMAL":
            worker["available"] = False
            
    if worker.get("current_task") or not worker.get("available", False):
        save_state(state)
        return jsonify({"task": None, "reason": "WORKER_BUSY"})
"""
content = content.replace(claim_old, claim_new)

with open("server/app.py", "w") as f:
    f.write(content)
