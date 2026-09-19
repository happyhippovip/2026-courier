import re

with open("scripts/courier_continue.py", "r") as f:
    code = f.read()

# Replace TaskFuture definition with nothing
code = re.sub(r'class TaskFuture:.*?(?=def main\(\):)', '', code, flags=re.DOTALL)

# Revert imports and initialization
code = code.replace('''    import multiprocessing
    import time

    running_tasks = {} # mapping task edge_name to future
    task_start_times = {} # mapping task edge_name to start time
    completed_this_session = set()''', 
'''    import concurrent.futures
    import time
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    running_tasks = {} # mapping task edge_name to future
    task_start_times = {} # mapping task edge_name to start time
    completed_this_session = set()''')

# Fix future.done() and kill()
code = code.replace('''            if not future.done() and (current_time - task_start_times[edge_name]) > 8.0:
                print(f"Task {edge_name} hung for > 8s, abandoning.")
                try:
                    future.p.kill()
                except Exception:
                    pass''', 
'''            if not future.done() and (current_time - task_start_times[edge_name]) > 8.0:
                print(f"Task {edge_name} hung for > 8s, abandoning.")''')

# Fix future.result() unpacking. ThreadPoolExecutor returns a Future whose result is just the return value of execute_task.
# execute_task returns (task, success, new_blocker)
code = code.replace('''                    task, success, new_blocker = future.result()''', '''                    task, success, new_blocker = future.result()''')

# Fix SUBMITTING TASK
code = code.replace('''                if len(running_tasks) >= 5:
                    break
                print(f"\\n{time.time()} === SUBMITTING TASK: {t['edge_name']} ===")
                running_tasks[t["edge_name"]] = TaskFuture(t, ledger_path, record)''', 
'''                print(f"\\n{time.time()} === SUBMITTING TASK: {t['edge_name']} ===")
                running_tasks[t["edge_name"]] = executor.submit(execute_task, t, ledger_path, record)''')

with open("scripts/courier_continue.py", "w") as f:
    f.write(code)

