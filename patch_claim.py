with open("server/app.py", "r") as f:
    content = f.read()

target = """def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    state = load_state()
    
    if worker_id not in state["workers"]:
        return jsonify({"error": "Unknown worker"}), 404
        
    worker = state["workers"][worker_id]"""

replacement = """def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    
    wait_start = time.time()
    while time.time() - wait_start < 25:
        state = load_state()
        if worker_id not in state["workers"]:
            return jsonify({"error": "Unknown worker"}), 404
        worker = state["workers"][worker_id]
        
        # If the worker has a task assigned (e.g. by automatic dispatch), return it
        if worker.get("current_task"):
            break
            
        # Also break if there's any task we can claim
        has_ready = False
        for goal in state["goals"].values():
            if goal["status"] == "ACTIVE" and "workflow_plan" in goal:
                completed = {s["task_id"] for s in goal["workflow_plan"] if s.get("status") == "RECONCILED"}
                for s in goal["workflow_plan"]:
                    if s.get("status") == "QUEUED" and s.get("next_retry_at", 0) <= time.time():
                        deps = s.get("depends_on", [])
                        if isinstance(deps, str): deps = [deps]
                        if all(d in completed for d in deps):
                            has_ready = True
                            break
            if has_ready: break
            
        if has_ready: break
        
        with STATE_LOCK:
            NEW_TASK_EVENT.wait(timeout=5)
            
    # The rest is the same, so we just reload state one last time to be safe
    state = load_state()
    worker = state["workers"][worker_id]"""

content = content.replace(target, replacement)
with open("server/app.py", "w") as f:
    f.write(content)
