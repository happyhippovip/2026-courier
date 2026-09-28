import os
import sys

def apply_patch():
    path = "scripts/courier_github_dispatcher.py"
    if not os.path.exists(path):
        print(f"{path} not found")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    old_block = """                    task_id = task.get("task_id")
                    log(f"Claimed task {task_id} for GitHub.")
                    handle_claimed_task(task)"""
                    
    new_block = """                    task_id = task.get("task_id")
                    log(f"Claimed task {task_id} for GitHub.")
                    if not handle_claimed_task(task):
                        log(f"Refused task {task_id}, posting FAILED result to free server state.")
                        try:
                            err_result = {
                                "goal_id": task.get("goal_id", "unknown"),
                                "task_id": task.get("task_id", "unknown"),
                                "attempt_id": task.get("attempt_id", "unknown"),
                                "dispatch_id": task.get("dispatch_id", "unknown"),
                                "worker_id": WORKER_ID,
                                "run_id": "failed",
                                "result_id": f"result-{task.get('dispatch_id', 'err')}",
                                "status": "FAILED",
                                "artifacts": [],
                                "stderr": "Dispatcher refused the task (invalid identity or unsafe dispatch_id)"
                            }
                            requests.post(f"{API_URL}/tasks/result", json=err_result, headers=HEADERS, timeout=10)
                        except Exception as ex:
                            log(f"Failed to post error result for {task_id}: {ex}")"""
                            
    if old_block not in content:
        if "posting FAILED result to free server state" in content:
            print("Patch already applied.")
            return
        print("Could not find the target block to patch.")
        sys.exit(1)
        
    patched = content.replace(old_block, new_block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(patched)
    print("Patch successfully applied to courier_github_dispatcher.py")

if __name__ == "__main__":
    apply_patch()
