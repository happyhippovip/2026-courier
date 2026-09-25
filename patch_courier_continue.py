import re
import sys

def run():
    with open("scripts/courier_continue.py", "r") as f:
        content = f.read()
    
    # 1. Add process_worker at the top
    worker_func = """
def process_worker(task, ledger_path, record, queue):
    try:
        res = execute_task(task, ledger_path, record)
        queue.put(res)
    except Exception as e:
        queue.put(e)
"""
    if "def process_worker" not in content:
        content = content.replace("def execute_task(", worker_func + "\ndef execute_task(")

    # 2. Replace executor init
    content = content.replace("executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)", "import multiprocessing\n    multiprocessing.set_start_method('fork', force=True)")

    # 3. Replace submission
    submission_old = """                running_tasks[t["edge_name"]] = executor.submit(execute_task, t, ledger_path, record)"""
    submission_new = """                if len(running_tasks) >= 5:
                    break
                q = multiprocessing.Queue()
                p = multiprocessing.Process(target=process_worker, args=(t, ledger_path, record, q))
                p.start()
                running_tasks[t["edge_name"]] = (p, q)"""
    content = content.replace(submission_old, submission_new)

    # 4. Replace checking logic
    check_loop_old = """        for edge_name, future in list(running_tasks.items()):
            print(f"{time.time()} DEBUG: {edge_name} running for {current_time - task_start_times[edge_name]} seconds")
            print(f"{time.time()} DEBUG: {edge_name} running for {current_time - task_start_times[edge_name]} seconds")
            if not future.done() and (current_time - task_start_times[edge_name]) > 8.0:
                print(f"Task {edge_name} hung for > 8s, abandoning.")
                done_edges.append(edge_name)
                completed_this_session.add(edge_name)
                blocked_tasks_this_run.add(edge_name)
                try:
                    branch, sha = get_git_info()
                    print(f"CHECKING FRESHNESS {branch} {sha}"); bundle = check_freshness(ledger_path, branch, sha)
                    update_ledger(ledger_path, edge_name, "TIMEOUT_HUNG_TASK", bundle)
                except Exception as e:
                    print(f"Failed to record hang for {edge_name}: {e}")
                continue

            if future.done():
                done_edges.append(edge_name)
                completed_this_session.add(edge_name)
                try:
                    task, success, new_blocker = future.result()"""
    
    check_loop_new = """        for edge_name, (p, q) in list(running_tasks.items()):
            if p.is_alive() and (current_time - task_start_times[edge_name]) > 8.0:
                print(f"Task {edge_name} hung for > 8s, abandoning.")
                p.terminate()
                p.join(timeout=1.0)
                done_edges.append(edge_name)
                completed_this_session.add(edge_name)
                blocked_tasks_this_run.add(edge_name)
                try:
                    branch, sha = get_git_info()
                    bundle = check_freshness(ledger_path, branch, sha)
                    update_ledger(ledger_path, edge_name, "TIMEOUT_HUNG_TASK", bundle)
                except Exception as e:
                    print(f"Failed to record hang for {edge_name}: {e}")
                continue

            if not q.empty() or not p.is_alive():
                done_edges.append(edge_name)
                completed_this_session.add(edge_name)
                try:
                    if not q.empty():
                        res = q.get()
                        p.join()
                    else:
                        p.join()
                        res = Exception("Process died without result")
                    
                    if isinstance(res, Exception):
                        raise res
                    
                    task, success, new_blocker = res"""

    content = content.replace(check_loop_old, check_loop_new)

    with open("scripts/courier_continue.py", "w") as f:
        f.write(content)

if __name__ == "__main__":
    run()
