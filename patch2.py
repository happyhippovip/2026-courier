import os

with open("C:/Users/lol/2026-workspace/courier/server/app.py", "r") as f:
    content = f.read()

search_str = "    save_state(state)\n    return jsonify({\"task\": None})"

replace_str = """    # --- INJECTED BATCH CLAIM LOGIC ---
    import glob
    import uuid
    if os.path.exists(BATCH_QUEUE_DIR):
        for path in glob.glob(os.path.join(BATCH_QUEUE_DIR, "*.json")):
            basename = os.path.basename(path)
            batch_id = basename[:-5]
            batch = load_batch(batch_id)
            if not batch: continue
            
            completed_seqs = {item.get("sequence") for item in batch.get("items", []) if item.get("status") == "COMPLETED"}
            blocked_targets = {item.get("target_agent", "linux").lower() for item in batch.get("items", []) if item.get("status") in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT")}
            
            next_task = None
            for item in batch.get("items", []):
                if item.get("status") == "QUEUED":
                    depends_on = item.get("depends_on")
                    if depends_on is None or depends_on in completed_seqs:
                        target = item.get("target_agent", "linux").lower()
                        if target not in blocked_targets:
                            # Qualified check
                            matched = False
                            if "github" in target and "github" in worker["capabilities"]: matched = True
                            elif "mac" in target and "macos" in worker["capabilities"]: matched = True
                            elif "windows" in target and "windows" in worker["capabilities"]: matched = True
                            elif "linux" in target and "linux" in worker["capabilities"]: matched = True
                            elif "antigravity" in target and "antigravity" in worker["capabilities"]: matched = True
                            
                            if matched:
                                next_task = item
                                break
            
            if next_task:
                target = next_task.get("target_agent", "linux").lower()
                next_task["worker_id"] = worker_id
                next_task["attempts"] = next_task.get("attempts", 0) + 1
                next_task["task_id"] = next_task.get("task_id") or f"{batch_id}-seq-{next_task['sequence']}"
                next_task["attempt_id"] = f"{next_task['task_id']}:attempt:{next_task['attempts']}"
                next_task["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
                next_task["run_id"] = None
                next_task["result_id"] = None
                next_task["target_capability"] = target
                next_task["batch_id"] = batch_id
                next_task["goal_id"] = next_task.get("goal_id", batch_id)
                next_task["last_completed_step"] = next_task.get("last_completed_step")
                next_task["next_action"] = "EXECUTE"
                next_task["blocker"] = None
                next_task["artifact_refs"] = next_task.get("artifact_refs", [])
                next_task["instruction"] = next_task.get("description", "Batch item")
                
                try:
                    next_task = prepare_task(next_task)
                except ContractError as exc:
                    return jsonify({"error": str(exc)}), 400
                    
                set_task_status(next_task, "DISPATCHED")
                next_task["status"] = "DISPATCHED"
                
                for item in batch["items"]:
                    if item.get("sequence") == next_task.get("sequence"):
                        item.update(next_task)
                
                with open(path, "w") as bf:
                    json.dump(batch, bf, indent=2)
                
                worker["current_task"] = next_task["task_id"]
                worker["available"] = False
                state["tasks"][next_task["task_id"]] = next_task
                save_state(state)
                return jsonify({"task": next_task})
    
    save_state(state)
    return jsonify({"task": None})"""

content = content.replace(search_str, replace_str, 1)

sync_str = """
# --- OVERRIDE SAVE_STATE TO SYNC BATCHES ---
original_save_state = save_state
def custom_save_state(state):
    original_save_state(state)
    
    import os, json
    batches_to_sync = {}
    for task_id, task in state.get("tasks", {}).items():
        batch_id = task.get("batch_id")
        if batch_id:
            if batch_id not in batches_to_sync:
                batches_to_sync[batch_id] = load_batch(batch_id)
            
            batch = batches_to_sync[batch_id]
            if not batch: continue
            
            for item in batch.get("items", []):
                if item.get("sequence") == task.get("sequence"):
                    st = task.get("status")
                    if st == "RECONCILED":
                        item["status"] = "COMPLETED"
                    elif st in ("WAITING_PROVIDER", "BLOCKED_TRANSIENT", "HUMAN_REQUIRED", "FAILED_VERIFICATION", "FAILED_TERMINAL"):
                        item["status"] = "WAITING_PROVIDER"
                    elif st in ("DISPATCHED", "RESULT_RECEIVED", "RECONCILED_PENDING_MERGE"):
                        item["status"] = "IN_PROGRESS"
                    else:
                        item["status"] = st
                        
                    item["worker_id"] = task.get("worker_id")
                    item["result"] = task.get("result")
                    item["verification"] = task.get("verification")
                    item["blocker"] = task.get("blocker")
                    item["attempts"] = task.get("attempts")
                    item["attempt_id"] = task.get("attempt_id")

    for batch_id, batch in batches_to_sync.items():
        if batch:
            path = os.path.join(BATCH_QUEUE_DIR, f"{batch_id}.json")
            with open(path, "w") as bf:
                json.dump(batch, bf, indent=2)

save_state = custom_save_state
"""

if "OVERRIDE SAVE_STATE" not in content:
    content += sync_str

with open("C:/Users/lol/2026-workspace/courier/server/app.py", "w") as f:
    f.write(content)

