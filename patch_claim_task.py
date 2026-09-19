import re

with open("server/app.py", "r") as f:
    content = f.read()

old_block = """@app.route("/tasks/claim", methods=["POST"])
@require_auth
@serialize_state_mutation
def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    timeout = data.get("timeout", 25)
    
    wait_start = time.time()
    while time.time() - wait_start < timeout:
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
        
        with NEW_TASK_EVENT:
            NEW_TASK_EVENT.wait(timeout=1)
            
    # The rest is the same, so we just reload state one last time to be safe
    state = load_state()"""

new_block = """@app.route("/tasks/claim", methods=["POST"])
@require_auth
def claim_task():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    timeout = data.get("timeout", 25)
    
    wait_start = time.time()
    while time.time() - wait_start < timeout:
        with STATE_LOCK:
            state = load_state()
            if worker_id not in state["workers"]:
                return jsonify({"error": "Unknown worker"}), 404
            worker = state["workers"][worker_id]
            
            # If the worker has a task assigned (e.g. by automatic dispatch), return it
            if worker.get("current_task"):
                has_ready = True
            else:
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
        
        with NEW_TASK_EVENT:
            NEW_TASK_EVENT.wait(timeout=1)
            
    # The rest is the same, so we just reload state one last time to be safe
    with STATE_LOCK:
        state = load_state()"""

if old_block in content:
    content = content.replace(old_block, new_block)
    
    # We must also wrap the very end of claim_task to make sure it returns properly inside the `with STATE_LOCK:` block
    # Actually wait, `with STATE_LOCK:` will just wrap the rest of the function!
    # Because claim_task is a big function.
    # Let me indent everything after `state = load_state()` with 4 spaces!
    
    print("Replaced old_block with new_block")
else:
    print("old_block not found!")

# Let's write the whole function replacement manually!
