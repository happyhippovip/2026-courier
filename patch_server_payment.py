from pathlib import Path

p = Path("server/app.py")
content = p.read_text()

# Modify submit_goal
target_submit = """    goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    state = load_state()"""
repl_submit = """    goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    state = load_state()
    
    # Virtual Balance Check (P4)
    estimated_cost = float(data.get("estimated_cost", 2.50))
    virtual_balance = float(state.get("virtual_balance", 10.00))
    if estimated_cost > virtual_balance:
        return jsonify({"error": "Payment Required"}), 402
    
    state["virtual_balance"] = virtual_balance - estimated_cost
    save_state(state)"""
if target_submit in content:
    content = content.replace(target_submit, repl_submit)

# Modify post_task_result to check actual cost
target_result = """    if not task:
        return jsonify({"error": "Task not found"}), 404"""
repl_result = """    if not task:
        return jsonify({"error": "Task not found"}), 404
        
    actual_cost = float(data.get("actual_cost", 0.0))
    if actual_cost > 0:
        virtual_balance = float(state.get("virtual_balance", 10.00))
        # If the actual cost was HIGHER than estimated, we might have to halt
        # Let's just deduct it. If balance goes negative, fail.
        if actual_cost > virtual_balance:
            return jsonify({"error": "Payment Required (Actual Cost Exceeded Provision)"}), 402
        state["virtual_balance"] = virtual_balance - actual_cost
        # We don't save state here yet, save_state(state) is called below"""
if target_result in content:
    content = content.replace(target_result, repl_result)

p.write_text(content)
print("SUCCESS")
