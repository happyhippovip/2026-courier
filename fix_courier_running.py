from pathlib import Path
import re

p = Path("scripts/courier_continue.py")
content = p.read_text()

# Update update_ledger definition
target_def = "def update_ledger(ledger_path, edge_name, blocker, bundle):"
repl_def = "def update_ledger(ledger_path, edge_name, blocker, bundle, running_tasks_update=None):"
if target_def in content:
    content = content.replace(target_def, repl_def)

# Apply running_tasks_update to updates
target_upd = """        if not unproven:
            updates["NEXT_EXECUTABLE_ACTION"] = "NONE"
            updates["CLEAN_IDLE"] = "YES"
            updates["STATUS"] = "CLEAN_IDLE"
        else:"""
repl_upd = """        if running_tasks_update is not None:
            updates["RUNNING_TASKS"] = running_tasks_update

        if not unproven:
            updates["NEXT_EXECUTABLE_ACTION"] = "NONE"
            updates["CLEAN_IDLE"] = "YES"
            updates["STATUS"] = "CLEAN_IDLE"
        else:"""
if target_upd in content:
    content = content.replace(target_upd, repl_upd)

# Before starting execution, update ledger with new RUNNING_TASKS
target_submit = """        # Submit new tasks
        newly_submitted = []
        for t in safe_executable_tasks:
            if t["edge_name"] not in running_tasks:
                print(f"\\n{time.time()} === SUBMITTING TASK: {t['edge_name']} ===")
                running_tasks[t["edge_name"]] = executor.submit(execute_task, t, ledger_path, record)
                task_start_times[t["edge_name"]] = time.time()
                newly_submitted.append(t["edge_name"])"""

repl_submit = """        # Submit new tasks
        newly_submitted = []
        
        # First, batch update RUNNING_TASKS in ledger before submitting
        to_submit = [t for t in safe_executable_tasks if t["edge_name"] not in running_tasks]
        if to_submit:
            try:
                branch, sha = get_git_info()
                bundle = check_freshness(ledger_path, branch, sha)
                current_running = bundle["record"].get("RUNNING_TASKS", {})
                for t in to_submit:
                    current_running[t["edge_name"]] = bundle["record"].get("RUNTIME_IDENTITY", "UNKNOWN")
                update_ledger(ledger_path, None, None, bundle, running_tasks_update=current_running)
            except Exception as e:
                print(f"Failed to record RUNNING_TASKS in ledger: {e}")
                
        for t in safe_executable_tasks:
            if t["edge_name"] not in running_tasks:
                print(f"\\n{time.time()} === SUBMITTING TASK: {t['edge_name']} ===")
                running_tasks[t["edge_name"]] = executor.submit(execute_task, t, ledger_path, record)
                task_start_times[t["edge_name"]] = time.time()
                newly_submitted.append(t["edge_name"])"""

if target_submit in content:
    content = content.replace(target_submit, repl_submit)

# When task finishes, remove it from RUNNING_TASKS
target_done = """        for edge_name in done_edges:
            del running_tasks[edge_name]"""

repl_done = """        for edge_name in done_edges:
            del running_tasks[edge_name]
            
        if done_edges:
            try:
                branch, sha = get_git_info()
                bundle = check_freshness(ledger_path, branch, sha)
                current_running = bundle["record"].get("RUNNING_TASKS", {})
                for edge_name in done_edges:
                    current_running.pop(edge_name, None)
                update_ledger(ledger_path, None, None, bundle, running_tasks_update=current_running)
            except Exception as e:
                print(f"Failed to clear RUNNING_TASKS in ledger: {e}")"""

if target_done in content:
    content = content.replace(target_done, repl_done)

# Update `compute_frontier` or skip tasks that are in RUNNING_TASKS (unless they belong to us)
target_skip = """            if t["edge_name"] in completed_this_session:
                continue"""
repl_skip = """            if t["edge_name"] in completed_this_session:
                continue
                
            # If the task is running on ANOTHER runtime, skip it
            task_runtime = record.get("RUNNING_TASKS", {}).get(t["edge_name"])
            if task_runtime and task_runtime != record.get("RUNTIME_IDENTITY"):
                continue"""

if target_skip in content:
    content = content.replace(target_skip, repl_skip)

p.write_text(content)
print("SUCCESS")
